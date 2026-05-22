#!/usr/bin/env python3
"""
Puente OPERAR <-> motor CRM.

Lee comandos desde pestaña OPERAR y ejecuta:
- Busqueda global en CRM (escribe en RESULTADOS)
- Actualizacion de contacto seleccionando fila de RESULTADOS
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from remote_contact_ops import (
    DEFAULT_CENTRAL_ID,
    auth_headers,
    ensure_result_headers,
    get_sources,
    get_values,
    search_contacts,
    update_contact,
    update_values,
    write_results_sheet,
)


SHEET_OPERAR = "OPERAR"
SHEET_RESULTS = "RESULTADOS"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Procesador remoto de la pestaña OPERAR.")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--service-account", required=True, help="Ruta JSON service account.")
    common.add_argument("--central-id", default=DEFAULT_CENTRAL_ID, help="Spreadsheet ID central.")
    common.add_argument("--timeout", type=int, default=120, help="Timeout HTTP (segundos).")

    p_once = sub.add_parser("run-once", parents=[common], help="Procesar una vez.")
    p_loop = sub.add_parser("run-loop", parents=[common], help="Procesar en bucle.")
    p_loop.add_argument("--interval-seconds", type=int, default=30, help="Intervalo entre ciclos.")
    p_loop.add_argument("--max-cycles", type=int, default=0, help="0 = infinito.")

    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in ("true", "1", "si", "yes", "x")


def to_int(value: Any, default: int) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return default


def safe_cell(matrix: List[List[str]], row_idx: int, col_idx: int, default: str = "") -> str:
    if row_idx < 0 or row_idx >= len(matrix):
        return default
    row = matrix[row_idx]
    if col_idx < 0 or col_idx >= len(row):
        return default
    return str(row[col_idx] or default)


def set_operar_cell(
    central_id: str,
    a1: str,
    value: Any,
    headers: Dict[str, str],
    timeout: int,
) -> None:
    update_values(central_id, f"{SHEET_OPERAR}!{a1}", [[value]], headers, timeout)


def read_operar_matrix(
    central_id: str,
    headers: Dict[str, str],
    timeout: int,
) -> List[List[str]]:
    return get_values(central_id, f"{SHEET_OPERAR}!A1:B40", headers, timeout)


def read_result_row(
    central_id: str,
    row_number: int,
    headers: Dict[str, str],
    timeout: int,
) -> List[str]:
    values = get_values(central_id, f"{SHEET_RESULTS}!A{row_number}:M{row_number}", headers, timeout)
    return values[0] if values else []


def process_search(
    central_id: str,
    matrix: List[List[str]],
    headers: Dict[str, str],
    timeout: int,
) -> Dict[str, Any]:
    term = safe_cell(matrix, 3, 1).strip()  # B4
    max_results = to_int(safe_cell(matrix, 4, 1), 20)  # B5
    trigger = to_bool(safe_cell(matrix, 5, 1))  # B6

    if not trigger:
        return {"executed": False, "reason": "trigger_false"}

    if not term:
        set_operar_cell(central_id, "B7", f"{now_iso()} | ERROR: falta termino en B4", headers, timeout)
        set_operar_cell(central_id, "B6", False, headers, timeout)
        return {"executed": True, "ok": False, "error": "falta termino"}

    ensure_result_headers(central_id, headers, timeout)
    sources = get_sources(central_id, headers, timeout)
    results = search_contacts(
        term=term,
        max_results=max(1, min(max_results, 500)),
        min_score=0.45,
        sources=sources,
        headers=headers,
        timeout=timeout,
    )
    write_results_sheet(central_id, term, results, headers, timeout)

    set_operar_cell(
        central_id,
        "B7",
        f"{now_iso()} | OK: {len(results)} resultados | term='{term}'",
        headers,
        timeout,
    )
    set_operar_cell(
        central_id,
        "B8",
        json.dumps({"term": term, "total": len(results)}, ensure_ascii=True),
        headers,
        timeout,
    )
    set_operar_cell(central_id, "B6", False, headers, timeout)

    return {"executed": True, "ok": True, "results_count": len(results), "term": term}


def process_update(
    central_id: str,
    matrix: List[List[str]],
    headers: Dict[str, str],
    timeout: int,
) -> Dict[str, Any]:
    result_row_number = to_int(safe_cell(matrix, 10, 1), 2)  # B11
    new_name = safe_cell(matrix, 11, 1).strip() or None  # B12
    new_email = safe_cell(matrix, 12, 1).strip() or None  # B13
    new_phone = safe_cell(matrix, 13, 1).strip() or None  # B14
    new_id = safe_cell(matrix, 14, 1).strip() or None  # B15
    new_notes = safe_cell(matrix, 15, 1).strip() or None  # B16
    dry_run = to_bool(safe_cell(matrix, 16, 1))  # B17
    trigger = to_bool(safe_cell(matrix, 17, 1))  # B18

    if not trigger:
        return {"executed": False, "reason": "trigger_false"}

    result_row = read_result_row(central_id, result_row_number, headers, timeout)
    if not result_row or len(result_row) < 8:
        set_operar_cell(
            central_id,
            "B19",
            f"{now_iso()} | ERROR: fila RESULTADOS invalida ({result_row_number})",
            headers,
            timeout,
        )
        set_operar_cell(central_id, "B18", False, headers, timeout)
        return {"executed": True, "ok": False, "error": "fila resultados invalida"}

    spreadsheet_id = str(result_row[4] if len(result_row) > 4 else "").strip()
    sheet_name = str(result_row[5] if len(result_row) > 5 else "").strip()
    row_origen = to_int(result_row[6] if len(result_row) > 6 else "", 0)

    if not spreadsheet_id or not sheet_name or row_origen <= 0:
        set_operar_cell(
            central_id,
            "B19",
            f"{now_iso()} | ERROR: fila RESULTADOS sin destino valido",
            headers,
            timeout,
        )
        set_operar_cell(central_id, "B18", False, headers, timeout)
        return {"executed": True, "ok": False, "error": "destino invalido"}

    result = update_contact(
        central_id=central_id,
        spreadsheet_id=spreadsheet_id,
        sheet_name=sheet_name,
        row_number=row_origen,
        new_values={
            "name": new_name,
            "email": new_email,
            "phone": new_phone,
            "contact_id": new_id,
            "notes": new_notes,
        },
        dry_run=dry_run,
        headers=headers,
        timeout=timeout,
    )

    set_operar_cell(
        central_id,
        "B19",
        f"{now_iso()} | OK: actualizacion {'simulada' if dry_run else 'aplicada'}",
        headers,
        timeout,
    )
    set_operar_cell(central_id, "B20", json.dumps(result, ensure_ascii=True), headers, timeout)
    set_operar_cell(central_id, "B18", False, headers, timeout)

    return {"executed": True, "ok": True, "result": result}


def run_once(args: argparse.Namespace) -> Dict[str, Any]:
    headers = auth_headers(args.service_account, args.timeout)
    matrix = read_operar_matrix(args.central_id, headers, args.timeout)

    search_result = process_search(args.central_id, matrix, headers, args.timeout)
    # Relee por si cambian celdas y triggers durante la busqueda.
    matrix2 = read_operar_matrix(args.central_id, headers, args.timeout)
    update_result = process_update(args.central_id, matrix2, headers, args.timeout)

    return {"ok": True, "search": search_result, "update": update_result}


def run_loop(args: argparse.Namespace) -> Dict[str, Any]:
    cycles = 0
    executed_search = 0
    executed_update = 0
    while True:
        cycles += 1
        res = run_once(args)
        if res.get("search", {}).get("executed"):
            executed_search += 1
        if res.get("update", {}).get("executed"):
            executed_update += 1
        if args.max_cycles > 0 and cycles >= args.max_cycles:
            break
        time.sleep(max(3, args.interval_seconds))
    return {
        "ok": True,
        "cycles": cycles,
        "executed_search": executed_search,
        "executed_update": executed_update,
    }


def main() -> None:
    args = parse_args()
    if args.command == "run-once":
        result = run_once(args)
    elif args.command == "run-loop":
        result = run_loop(args)
    else:
        raise RuntimeError(f"Comando no soportado: {args.command}")
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
