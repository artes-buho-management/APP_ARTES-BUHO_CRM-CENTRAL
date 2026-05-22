#!/usr/bin/env python3
"""
Worker remoto para IA_LOCAL_COLA.

Funciones:
- Encolar tareas (search/update/parse_message)
- Ejecutar cola una vez (run-once)
- Ejecutar en bucle (run-loop)

Estados:
- PENDING
- PROCESSING
- DONE
- RETRY
- WAITING_AI
- FAILED
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from remote_contact_ops import (
    DEFAULT_CENTRAL_ID,
    auth_headers,
    ensure_result_headers,
    get_values,
    search_contacts,
    update_contact,
    update_values,
    write_results_sheet,
    get_sources,
)


QUEUE_SHEET = "IA_LOCAL_COLA"
QUEUE_HEADERS = [
    "CREATED_AT",
    "TASK_TYPE",
    "STATUS",
    "PAYLOAD_JSON",
    "RESULT_JSON",
    "LAST_ERROR",
    "NEXT_RETRY_AT",
    "ATTEMPTS",
]

STATUS_PENDING = "PENDING"
STATUS_PROCESSING = "PROCESSING"
STATUS_DONE = "DONE"
STATUS_RETRY = "RETRY"
STATUS_WAITING_AI = "WAITING_AI"
STATUS_FAILED = "FAILED"

PROCESSABLE = {STATUS_PENDING, STATUS_RETRY, STATUS_WAITING_AI}


@dataclass
class QueueRow:
    row_number: int
    created_at: str
    task_type: str
    status: str
    payload_json: str
    result_json: str
    last_error: str
    next_retry_at: str
    attempts: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Worker remoto de IA_LOCAL_COLA.")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--service-account", required=True, help="Ruta JSON service account.")
    common.add_argument("--central-id", default=DEFAULT_CENTRAL_ID, help="Spreadsheet ID central.")
    common.add_argument("--timeout", type=int, default=120, help="Timeout HTTP (segundos).")

    p_run_once = sub.add_parser("run-once", parents=[common], help="Procesar cola una sola vez.")
    p_run_once.add_argument("--max-tasks", type=int, default=25, help="Maximo tareas por ejecucion.")
    p_run_once.add_argument("--max-attempts", type=int, default=5, help="Maximo intentos por tarea.")
    p_run_once.add_argument(
        "--retry-minutes",
        type=int,
        default=5,
        help="Minutos para siguiente reintento en RETRY/WAITING_AI.",
    )
    p_run_once.add_argument("--ai-endpoint", help="Endpoint HTTP local de IA (opcional).")

    p_run_loop = sub.add_parser("run-loop", parents=[common], help="Procesar cola en bucle.")
    p_run_loop.add_argument("--interval-seconds", type=int, default=30, help="Intervalo entre ciclos.")
    p_run_loop.add_argument("--max-cycles", type=int, default=0, help="0 = infinito.")
    p_run_loop.add_argument("--max-tasks", type=int, default=25, help="Maximo tareas por ciclo.")
    p_run_loop.add_argument("--max-attempts", type=int, default=5, help="Maximo intentos por tarea.")
    p_run_loop.add_argument("--retry-minutes", type=int, default=5, help="Minutos de reintento.")
    p_run_loop.add_argument("--ai-endpoint", help="Endpoint HTTP local de IA (opcional).")

    p_enqueue_search = sub.add_parser("enqueue-search", parents=[common], help="Encolar busqueda.")
    p_enqueue_search.add_argument("--term", required=True, help="Texto de busqueda.")
    p_enqueue_search.add_argument("--max-results", type=int, default=25, help="Max resultados.")
    p_enqueue_search.add_argument("--min-score", type=float, default=0.45, help="Score minimo.")

    p_enqueue_update = sub.add_parser("enqueue-update", parents=[common], help="Encolar actualizacion.")
    p_enqueue_update.add_argument("--spreadsheet-id", required=True)
    p_enqueue_update.add_argument("--sheet-name", required=True)
    p_enqueue_update.add_argument("--row-number", required=True, type=int)
    p_enqueue_update.add_argument("--name")
    p_enqueue_update.add_argument("--email")
    p_enqueue_update.add_argument("--phone")
    p_enqueue_update.add_argument("--contact-id")
    p_enqueue_update.add_argument("--notes")
    p_enqueue_update.add_argument("--dry-run", action="store_true")

    p_enqueue_parse = sub.add_parser("enqueue-parse-message", parents=[common], help="Encolar parseo de mensaje.")
    p_enqueue_parse.add_argument("--message", help="Texto completo mensaje.")
    p_enqueue_parse.add_argument("--message-file", help="Ruta a archivo de texto.")

    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_iso_after(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=max(1, minutes))).isoformat()


def parse_iso(value: str) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except ValueError:
        return default


def ensure_headers(central_id: str, headers: Dict[str, str], timeout: int) -> None:
    existing = get_values(central_id, f"{QUEUE_SHEET}!A1:H1", headers, timeout)
    if not existing or existing[0] != QUEUE_HEADERS:
        update_values(central_id, f"{QUEUE_SHEET}!A1", [QUEUE_HEADERS], headers, timeout)


def parse_rows(values: List[List[str]]) -> List[QueueRow]:
    out: List[QueueRow] = []
    for idx, row in enumerate(values, start=2):
        padded = list(row) + [""] * max(0, 8 - len(row))
        out.append(
            QueueRow(
                row_number=idx,
                created_at=str(padded[0] or ""),
                task_type=str(padded[1] or ""),
                status=str(padded[2] or ""),
                payload_json=str(padded[3] or ""),
                result_json=str(padded[4] or ""),
                last_error=str(padded[5] or ""),
                next_retry_at=str(padded[6] or ""),
                attempts=parse_int(padded[7], 0),
            )
        )
    return out


def get_queue_rows(central_id: str, headers: Dict[str, str], timeout: int) -> List[QueueRow]:
    values = get_values(central_id, f"{QUEUE_SHEET}!A2:H", headers, timeout)
    return parse_rows(values)


def write_row_cells(
    central_id: str,
    row_number: int,
    updates: Dict[str, Any],
    headers: Dict[str, str],
    timeout: int,
) -> None:
    col_map = {
        "CREATED_AT": "A",
        "TASK_TYPE": "B",
        "STATUS": "C",
        "PAYLOAD_JSON": "D",
        "RESULT_JSON": "E",
        "LAST_ERROR": "F",
        "NEXT_RETRY_AT": "G",
        "ATTEMPTS": "H",
    }
    data = []
    for key, value in updates.items():
        if key not in col_map:
            continue
        data.append(
            {
                "range": f"{QUEUE_SHEET}!{col_map[key]}{row_number}",
                "values": [[value]],
            }
        )
    if not data:
        return

    url = f"https://sheets.googleapis.com/v4/spreadsheets/{central_id}/values:batchUpdate"
    params = {"valueInputOption": "RAW"}
    payload = {"data": data}
    response = requests.post(url, headers=headers, params=params, json=payload, timeout=timeout)
    response.raise_for_status()


def append_queue_task(
    central_id: str,
    task_type: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    timeout: int,
) -> Dict[str, Any]:
    ensure_headers(central_id, headers, timeout)
    created = now_iso()
    row = [
        created,
        task_type,
        STATUS_PENDING,
        json.dumps(payload, ensure_ascii=True),
        "",
        "",
        "",
        0,
    ]
    values = get_values(central_id, f"{QUEUE_SHEET}!A:A", headers, timeout)
    next_row = max(2, len(values) + 1)
    update_values(central_id, f"{QUEUE_SHEET}!A{next_row}", [row], headers, timeout)
    return {"ok": True, "row_number": next_row, "task_type": task_type}


def ai_available(ai_endpoint: Optional[str], timeout: int) -> bool:
    if not ai_endpoint:
        return False
    try:
        response = requests.get(ai_endpoint, timeout=max(3, min(timeout, 15)))
        return 200 <= response.status_code < 500
    except Exception:
        return False


def parse_message_with_local_ai(ai_endpoint: str, message: str, timeout: int) -> Dict[str, Any]:
    payload = {
        "task": "extract_contact_updates",
        "message": message,
        "format": "json",
    }
    response = requests.post(ai_endpoint, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {"raw": data}


def parse_message_fallback(message: str) -> Dict[str, Any]:
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", message or "")
    phones = re.findall(r"(?:\+?\d[\d\s().-]{6,}\d)", message or "")
    lines = [ln.strip() for ln in (message or "").splitlines() if ln.strip()]
    possible_names = []
    for ln in lines:
        if "@" in ln:
            continue
        if re.search(r"\d", ln):
            continue
        if len(ln.split()) >= 2:
            possible_names.append(ln)
    return {
        "mode": "fallback_regex",
        "emails": list(dict.fromkeys(emails)),
        "phones": list(dict.fromkeys([p.strip() for p in phones])),
        "possible_names": possible_names[:20],
    }


def process_contact_search(
    central_id: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    timeout: int,
) -> Dict[str, Any]:
    term = str(payload.get("term", "")).strip()
    max_results = parse_int(payload.get("max_results", 25), 25)
    min_score = float(payload.get("min_score", 0.45))
    if not term:
        raise RuntimeError("Payload invalido: falta term.")

    ensure_result_headers(central_id, headers, timeout)
    sources = get_sources(central_id, headers, timeout)
    results = search_contacts(
        term=term,
        max_results=max_results,
        min_score=min_score,
        sources=sources,
        headers=headers,
        timeout=timeout,
    )
    write_results_sheet(central_id, term, results, headers, timeout)
    return {"ok": True, "term": term, "sources_checked": len(sources), "results_count": len(results), "results": results}


def process_contact_update(
    central_id: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    timeout: int,
) -> Dict[str, Any]:
    return update_contact(
        central_id=central_id,
        spreadsheet_id=str(payload.get("spreadsheet_id", "")).strip(),
        sheet_name=str(payload.get("sheet_name", "")).strip(),
        row_number=parse_int(payload.get("row_number", 0), 0),
        new_values={
            "name": payload.get("name"),
            "email": payload.get("email"),
            "phone": payload.get("phone"),
            "contact_id": payload.get("contact_id"),
            "notes": payload.get("notes"),
        },
        dry_run=bool(payload.get("dry_run", False)),
        headers=headers,
        timeout=timeout,
    )


def process_parse_message(
    payload: Dict[str, Any],
    ai_endpoint: Optional[str],
    timeout: int,
) -> Dict[str, Any]:
    message = str(payload.get("message", "")).strip()
    if not message:
        raise RuntimeError("Payload invalido: falta message.")
    if ai_endpoint:
        return {"mode": "local_ai", "parsed": parse_message_with_local_ai(ai_endpoint, message, timeout)}
    return {"mode": "fallback", "parsed": parse_message_fallback(message)}


def process_task(
    task: QueueRow,
    central_id: str,
    headers: Dict[str, str],
    timeout: int,
    ai_endpoint: Optional[str],
) -> Dict[str, Any]:
    payload = json.loads(task.payload_json or "{}")
    task_type = (task.task_type or "").strip().upper()

    if task_type == "CONTACT_SEARCH":
        return process_contact_search(central_id, payload, headers, timeout)
    if task_type == "CONTACT_UPDATE":
        return process_contact_update(central_id, payload, headers, timeout)
    if task_type == "PARSE_UPDATE_MESSAGE":
        return process_parse_message(payload, ai_endpoint, timeout)

    raise RuntimeError(f"TASK_TYPE no soportado: {task.task_type}")


def should_run_now(task: QueueRow) -> bool:
    if task.status not in PROCESSABLE:
        return False
    next_retry = parse_iso(task.next_retry_at)
    if not next_retry:
        return True
    return datetime.now(timezone.utc) >= next_retry.astimezone(timezone.utc)


def run_once(args: argparse.Namespace) -> Dict[str, Any]:
    headers = auth_headers(args.service_account, args.timeout)
    ensure_headers(args.central_id, headers, args.timeout)

    rows = get_queue_rows(args.central_id, headers, args.timeout)
    processable = [r for r in rows if should_run_now(r)]
    processable = processable[: max(1, args.max_tasks)]

    ai_is_available = ai_available(args.ai_endpoint, args.timeout)
    processed = 0
    done = 0
    retry = 0
    waiting = 0
    failed = 0

    for task in processable:
        processed += 1
        attempts = task.attempts + 1
        write_row_cells(
            args.central_id,
            task.row_number,
            {
                "STATUS": STATUS_PROCESSING,
                "LAST_ERROR": "",
                "ATTEMPTS": attempts,
                "NEXT_RETRY_AT": "",
            },
            headers,
            args.timeout,
        )

        try:
            task_type = (task.task_type or "").strip().upper()
            if task_type == "PARSE_UPDATE_MESSAGE" and not ai_is_available:
                write_row_cells(
                    args.central_id,
                    task.row_number,
                    {
                        "STATUS": STATUS_WAITING_AI,
                        "LAST_ERROR": "IA local no disponible. En espera.",
                        "NEXT_RETRY_AT": to_iso_after(args.retry_minutes),
                    },
                    headers,
                    args.timeout,
                )
                waiting += 1
                continue

            result = process_task(
                task=task,
                central_id=args.central_id,
                headers=headers,
                timeout=args.timeout,
                ai_endpoint=args.ai_endpoint,
            )
            write_row_cells(
                args.central_id,
                task.row_number,
                {
                    "STATUS": STATUS_DONE,
                    "RESULT_JSON": json.dumps(result, ensure_ascii=True),
                    "LAST_ERROR": "",
                    "NEXT_RETRY_AT": "",
                },
                headers,
                args.timeout,
            )
            done += 1
        except Exception as err:  # noqa: BLE001
            error_text = str(err)
            if attempts >= max(1, args.max_attempts):
                write_row_cells(
                    args.central_id,
                    task.row_number,
                    {
                        "STATUS": STATUS_FAILED,
                        "LAST_ERROR": error_text[:4000],
                        "NEXT_RETRY_AT": "",
                    },
                    headers,
                    args.timeout,
                )
                failed += 1
            else:
                write_row_cells(
                    args.central_id,
                    task.row_number,
                    {
                        "STATUS": STATUS_RETRY,
                        "LAST_ERROR": error_text[:4000],
                        "NEXT_RETRY_AT": to_iso_after(args.retry_minutes),
                    },
                    headers,
                    args.timeout,
                )
                retry += 1

    return {
        "ok": True,
        "ai_available": ai_is_available,
        "processable_found": len(processable),
        "processed": processed,
        "done": done,
        "retry": retry,
        "waiting_ai": waiting,
        "failed": failed,
    }


def run_loop(args: argparse.Namespace) -> Dict[str, Any]:
    cycles = 0
    agg = {"done": 0, "retry": 0, "waiting_ai": 0, "failed": 0, "processed": 0}
    while True:
        cycles += 1
        once_args = argparse.Namespace(
            service_account=args.service_account,
            central_id=args.central_id,
            timeout=args.timeout,
            max_tasks=args.max_tasks,
            max_attempts=args.max_attempts,
            retry_minutes=args.retry_minutes,
            ai_endpoint=args.ai_endpoint,
        )
        result = run_once(once_args)
        for key in agg:
            agg[key] += int(result.get(key, 0))

        if args.max_cycles > 0 and cycles >= args.max_cycles:
            break
        time.sleep(max(3, args.interval_seconds))

    return {"ok": True, "cycles": cycles, **agg}


def enqueue_search(args: argparse.Namespace) -> Dict[str, Any]:
    headers = auth_headers(args.service_account, args.timeout)
    payload = {
        "term": args.term,
        "max_results": args.max_results,
        "min_score": args.min_score,
    }
    return append_queue_task(args.central_id, "CONTACT_SEARCH", payload, headers, args.timeout)


def enqueue_update(args: argparse.Namespace) -> Dict[str, Any]:
    headers = auth_headers(args.service_account, args.timeout)
    payload = {
        "spreadsheet_id": args.spreadsheet_id,
        "sheet_name": args.sheet_name,
        "row_number": args.row_number,
        "name": args.name,
        "email": args.email,
        "phone": args.phone,
        "contact_id": args.contact_id,
        "notes": args.notes,
        "dry_run": bool(args.dry_run),
    }
    return append_queue_task(args.central_id, "CONTACT_UPDATE", payload, headers, args.timeout)


def enqueue_parse_message(args: argparse.Namespace) -> Dict[str, Any]:
    headers = auth_headers(args.service_account, args.timeout)
    message = args.message
    if not message and args.message_file:
        message = Path(args.message_file).read_text(encoding="utf-8")
    if not message:
        raise RuntimeError("Debes indicar --message o --message-file.")
    payload = {"message": message}
    return append_queue_task(args.central_id, "PARSE_UPDATE_MESSAGE", payload, headers, args.timeout)


def main() -> None:
    args = parse_args()
    if args.command == "run-once":
        result = run_once(args)
    elif args.command == "run-loop":
        result = run_loop(args)
    elif args.command == "enqueue-search":
        result = enqueue_search(args)
    elif args.command == "enqueue-update":
        result = enqueue_update(args)
    elif args.command == "enqueue-parse-message":
        result = enqueue_parse_message(args)
    else:
        raise RuntimeError(f"Comando no soportado: {args.command}")

    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
