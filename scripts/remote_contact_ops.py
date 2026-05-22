#!/usr/bin/env python3
"""
Operaciones remotas de contactos (busqueda + actualizacion) por Sheets API.

No depende del despliegue Web App de Apps Script.
Usa la hoja central y las fuentes cargadas en FUENTES.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account


DEFAULT_CENTRAL_ID = "REPLACE_WITH_SHEET_ID"

SHEET_SOURCES = "FUENTES"
SHEET_RESULTS = "RESULTADOS"

SOURCE_HEADERS = [
    "ACTIVO",
    "ALIAS",
    "SPREADSHEET_ID",
    "HOJA",
    "HEADER_ROW",
    "CAMPO_NOMBRE",
    "CAMPO_EMAIL",
    "CAMPO_TELEFONO",
    "CAMPO_ID",
    "CAMPO_NOTAS",
]

RESULT_HEADERS = [
    "FECHA_BUSQUEDA",
    "TERMINO",
    "SCORE",
    "ORIGEN_ALIAS",
    "SPREADSHEET_ID",
    "HOJA",
    "FILA_ORIGEN",
    "MATCH_EN",
    "CONTACT_ID",
    "NOMBRE",
    "EMAIL",
    "TELEFONO",
    "NOTAS",
]

DEFAULT_HEADER_CANDIDATES = {
    "name": "NOMBRE|NOMBRE Y APELLIDOS|CONTACTO|CLIENTE|NOM|EMPRESA|RAZON SOCIAL",
    "email": "EMAIL|E-MAIL|CORREO|MAIL|CORREO ELECTRONICO",
    "phone": "TELEFONO|MOVIL|CELULAR|TLF|TELEFONO 1|WHATSAPP",
    "id": "ID|IDENTIFICADOR|CODIGO|ID CLIENTE|ID CONTACTO",
    "notes": "NOTAS|OBSERVACIONES|COMENTARIOS|DETALLE",
}


@dataclass
class SourceRow:
    active: bool
    alias: str
    spreadsheet_id: str
    sheet_name: str
    header_row: int
    field_name_candidates: str
    field_email_candidates: str
    field_phone_candidates: str
    field_id_candidates: str
    field_notes_candidates: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Buscador/actualizador remoto de contactos.")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--service-account", required=True, help="Ruta JSON service account.")
    common.add_argument("--central-id", default=DEFAULT_CENTRAL_ID, help="Spreadsheet ID central.")
    common.add_argument("--timeout", type=int, default=120, help="Timeout HTTP en segundos.")

    p_search = sub.add_parser("search", parents=[common], help="Buscar contacto en todas las fuentes activas.")
    p_search.add_argument("--term", required=True, help="Texto a buscar.")
    p_search.add_argument("--max-results", type=int, default=25, help="Maximo resultados.")
    p_search.add_argument("--min-score", type=float, default=0.45, help="Score minimo (0 a 1).")
    p_search.add_argument("--no-write-results", action="store_true", help="No escribir en RESULTADOS.")
    p_search.add_argument("--out-json", help="Ruta opcional para guardar salida JSON.")

    p_update = sub.add_parser("update", parents=[common], help="Actualizar un contacto en hoja origen.")
    p_update.add_argument("--spreadsheet-id", required=True, help="Spreadsheet ID origen.")
    p_update.add_argument("--sheet-name", required=True, help="Nombre pestaña origen.")
    p_update.add_argument("--row-number", required=True, type=int, help="Fila origen (1-based).")
    p_update.add_argument("--name", help="Nuevo nombre.")
    p_update.add_argument("--email", help="Nuevo email.")
    p_update.add_argument("--phone", help="Nuevo telefono.")
    p_update.add_argument("--contact-id", help="Nuevo ID contacto.")
    p_update.add_argument("--notes", help="Nuevas notas.")
    p_update.add_argument("--dry-run", action="store_true", help="No escribir, solo simular.")

    return parser.parse_args()


def auth_headers(service_account_file: str, timeout: int) -> Dict[str, str]:
    _ = timeout
    creds = service_account.Credentials.from_service_account_file(
        service_account_file,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    creds.refresh(Request())
    return {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}


def normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[\W_]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def neutralize_vowels(text: str) -> str:
    return re.sub(r"[aeiou]", "a", text)


def only_digits(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def split_candidates(candidates: str) -> List[str]:
    raw = str(candidates or "")
    parts = [normalize_text(x) for x in raw.split("|")]
    return [p for p in parts if p]


def parse_bool(value: Any) -> bool:
    s = normalize_text(value)
    return s in ("true", "1", "si", "yes", "y", "ok", "activo", "x")


def col_to_a1(col_1_based: int) -> str:
    n = max(1, int(col_1_based))
    out = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def get_values(
    spreadsheet_id: str,
    a1_range: str,
    headers: Dict[str, str],
    timeout: int,
) -> List[List[str]]:
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{a1_range}"
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json().get("values", []) or []


def clear_values(
    spreadsheet_id: str,
    a1_range: str,
    headers: Dict[str, str],
    timeout: int,
) -> None:
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{a1_range}:clear"
    response = requests.post(url, headers=headers, json={}, timeout=timeout)
    response.raise_for_status()


def update_values(
    spreadsheet_id: str,
    a1_range: str,
    values: List[List[Any]],
    headers: Dict[str, str],
    timeout: int,
    value_input_option: str = "RAW",
) -> None:
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{a1_range}"
    params = {"valueInputOption": value_input_option}
    payload = {"range": a1_range, "majorDimension": "ROWS", "values": values}
    response = requests.put(url, headers=headers, params=params, json=payload, timeout=timeout)
    response.raise_for_status()


def batch_update_values(
    spreadsheet_id: str,
    updates: List[Dict[str, Any]],
    headers: Dict[str, str],
    timeout: int,
    value_input_option: str = "RAW",
) -> None:
    if not updates:
        return
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values:batchUpdate"
    params = {"valueInputOption": value_input_option}
    payload = {"data": updates}
    response = requests.post(url, headers=headers, params=params, json=payload, timeout=timeout)
    response.raise_for_status()


def parse_source_row(row: List[str]) -> Optional[SourceRow]:
    padded = list(row) + [""] * max(0, len(SOURCE_HEADERS) - len(row))
    try:
        header_row = int(str(padded[4] or "1"))
    except ValueError:
        header_row = 1

    source = SourceRow(
        active=parse_bool(padded[0]),
        alias=str(padded[1] or "").strip(),
        spreadsheet_id=str(padded[2] or "").strip(),
        sheet_name=str(padded[3] or "").strip(),
        header_row=max(1, header_row),
        field_name_candidates=str(padded[5] or "").strip(),
        field_email_candidates=str(padded[6] or "").strip(),
        field_phone_candidates=str(padded[7] or "").strip(),
        field_id_candidates=str(padded[8] or "").strip(),
        field_notes_candidates=str(padded[9] or "").strip(),
    )

    if not source.spreadsheet_id or not source.sheet_name:
        return None
    return source


def get_sources(
    central_id: str,
    headers: Dict[str, str],
    timeout: int,
) -> List[SourceRow]:
    values = get_values(central_id, f"{SHEET_SOURCES}!A2:J", headers, timeout)
    out: List[SourceRow] = []
    for row in values:
        source = parse_source_row(row)
        if source and source.active:
            out.append(source)
    return out


def header_index_map(header_values: List[str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for idx, value in enumerate(header_values):
        key = normalize_text(value)
        if key and key not in out:
            out[key] = idx
    return out


def find_column_index(header_values: List[str], candidates_text: str) -> int:
    candidates = split_candidates(candidates_text)
    if not candidates:
        return -1
    hmap = header_index_map(header_values)

    for candidate in candidates:
        if candidate in hmap:
            return hmap[candidate]

    for candidate in candidates:
        for key, index in hmap.items():
            if candidate in key or key in candidate:
                return index

    return -1


def get_cell(row: List[str], index: int) -> str:
    if index < 0 or index >= len(row):
        return ""
    return str(row[index] or "").strip()


def field_score(term: str, value: str, value_digits: str) -> float:
    if not value:
        return 0.0

    n_term = normalize_text(term)
    n_value = normalize_text(value)
    if not n_term or not n_value:
        return 0.0

    ratio_plain = SequenceMatcher(None, n_term, n_value).ratio()
    ratio_vowels = SequenceMatcher(None, neutralize_vowels(n_term), neutralize_vowels(n_value)).ratio()

    score = max(ratio_plain * 0.78, ratio_vowels * 0.72)

    if n_term in n_value:
        score = max(score, 0.84)

    t_digits = only_digits(term)
    if t_digits and value_digits and t_digits in value_digits:
        score = max(score, 0.9)

    return min(score, 0.99)


def compute_best_match(term: str, fields: Dict[str, str]) -> Dict[str, Any]:
    candidates = [
        ("NOMBRE", fields.get("name", "")),
        ("EMAIL", fields.get("email", "")),
        ("TELEFONO", fields.get("phone", "")),
        ("NOTAS", fields.get("notes", "")),
        ("ID", fields.get("contact_id", "")),
    ]
    best_score = 0.0
    best_field = ""
    for label, value in candidates:
        score = field_score(term, value, only_digits(value))
        if score > best_score:
            best_score = score
            best_field = label
    return {"score": best_score, "field": best_field}


def search_contacts(
    term: str,
    max_results: int,
    min_score: float,
    sources: List[SourceRow],
    headers: Dict[str, str],
    timeout: int,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    for source in sources:
        try:
            values = get_values(
                source.spreadsheet_id,
                f"'{source.sheet_name}'!A1:ZZ",
                headers,
                timeout,
            )
        except Exception:
            continue

        if len(values) < source.header_row:
            continue

        header_values = values[source.header_row - 1]
        idx_name = find_column_index(
            header_values,
            source.field_name_candidates or DEFAULT_HEADER_CANDIDATES["name"],
        )
        idx_email = find_column_index(
            header_values,
            source.field_email_candidates or DEFAULT_HEADER_CANDIDATES["email"],
        )
        idx_phone = find_column_index(
            header_values,
            source.field_phone_candidates or DEFAULT_HEADER_CANDIDATES["phone"],
        )
        idx_id = find_column_index(
            header_values,
            source.field_id_candidates or DEFAULT_HEADER_CANDIDATES["id"],
        )
        idx_notes = find_column_index(
            header_values,
            source.field_notes_candidates or DEFAULT_HEADER_CANDIDATES["notes"],
        )

        start_index = source.header_row
        for i in range(start_index, len(values)):
            row = values[i]
            item = {
                "name": get_cell(row, idx_name),
                "email": get_cell(row, idx_email),
                "phone": get_cell(row, idx_phone),
                "contact_id": get_cell(row, idx_id),
                "notes": get_cell(row, idx_notes),
            }
            if not any(item.values()):
                continue

            matched = compute_best_match(term, item)
            score = float(matched["score"])
            if score < min_score:
                continue

            results.append(
                {
                    "score": round(score, 4),
                    "match_field": matched["field"],
                    "origin_alias": source.alias,
                    "spreadsheet_id": source.spreadsheet_id,
                    "sheet_name": source.sheet_name,
                    "row_number": i + 1,
                    "contact_id": item["contact_id"],
                    "name": item["name"],
                    "email": item["email"],
                    "phone": item["phone"],
                    "notes": item["notes"],
                    "header_row": source.header_row,
                    "column_map": {
                        "name": idx_name,
                        "email": idx_email,
                        "phone": idx_phone,
                        "contact_id": idx_id,
                        "notes": idx_notes,
                    },
                }
            )

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[: max(1, max_results)]


def write_results_sheet(
    central_id: str,
    term: str,
    results: List[Dict[str, Any]],
    headers: Dict[str, str],
    timeout: int,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    clear_values(central_id, f"{SHEET_RESULTS}!A2:Z", headers, timeout)
    if not results:
        return

    rows = []
    for item in results:
        rows.append(
            [
                now,
                term,
                item.get("score", ""),
                item.get("origin_alias", ""),
                item.get("spreadsheet_id", ""),
                item.get("sheet_name", ""),
                item.get("row_number", ""),
                item.get("match_field", ""),
                item.get("contact_id", ""),
                item.get("name", ""),
                item.get("email", ""),
                item.get("phone", ""),
                item.get("notes", ""),
            ]
        )
    update_values(central_id, f"{SHEET_RESULTS}!A2", rows, headers, timeout)


def ensure_result_headers(
    central_id: str,
    headers: Dict[str, str],
    timeout: int,
) -> None:
    existing = get_values(central_id, f"{SHEET_RESULTS}!A1:M1", headers, timeout)
    if not existing or existing[0] != RESULT_HEADERS:
        update_values(central_id, f"{SHEET_RESULTS}!A1", [RESULT_HEADERS], headers, timeout)


def resolve_update_columns(
    source: Optional[SourceRow],
    header_values: List[str],
) -> Dict[str, int]:
    if source:
        return {
            "name": find_column_index(header_values, source.field_name_candidates or DEFAULT_HEADER_CANDIDATES["name"]),
            "email": find_column_index(header_values, source.field_email_candidates or DEFAULT_HEADER_CANDIDATES["email"]),
            "phone": find_column_index(header_values, source.field_phone_candidates or DEFAULT_HEADER_CANDIDATES["phone"]),
            "contact_id": find_column_index(
                header_values, source.field_id_candidates or DEFAULT_HEADER_CANDIDATES["id"]
            ),
            "notes": find_column_index(header_values, source.field_notes_candidates or DEFAULT_HEADER_CANDIDATES["notes"]),
        }

    return {
        "name": find_column_index(header_values, DEFAULT_HEADER_CANDIDATES["name"]),
        "email": find_column_index(header_values, DEFAULT_HEADER_CANDIDATES["email"]),
        "phone": find_column_index(header_values, DEFAULT_HEADER_CANDIDATES["phone"]),
        "contact_id": find_column_index(header_values, DEFAULT_HEADER_CANDIDATES["id"]),
        "notes": find_column_index(header_values, DEFAULT_HEADER_CANDIDATES["notes"]),
    }


def find_source_match(
    sources: List[SourceRow],
    spreadsheet_id: str,
    sheet_name: str,
) -> Optional[SourceRow]:
    for source in sources:
        if source.spreadsheet_id == spreadsheet_id and source.sheet_name == sheet_name:
            return source
    return None


def update_contact(
    central_id: str,
    spreadsheet_id: str,
    sheet_name: str,
    row_number: int,
    new_values: Dict[str, Optional[str]],
    dry_run: bool,
    headers: Dict[str, str],
    timeout: int,
) -> Dict[str, Any]:
    sources = get_sources(central_id, headers, timeout)
    source = find_source_match(sources, spreadsheet_id, sheet_name)
    header_row = source.header_row if source else 1

    rows = get_values(spreadsheet_id, f"'{sheet_name}'!A{header_row}:ZZ{header_row}", headers, timeout)
    if not rows:
        raise RuntimeError(f"No se pudo leer cabecera en {sheet_name} fila {header_row}.")
    header_values = rows[0]
    col_map = resolve_update_columns(source, header_values)

    updates = []
    for key, text in new_values.items():
        if text is None:
            continue
        col_index = col_map.get(key, -1)
        if col_index < 0:
            continue
        col_letter = col_to_a1(col_index + 1)
        updates.append({"range": f"'{sheet_name}'!{col_letter}{row_number}", "values": [[text]]})

    if not updates:
        return {"ok": True, "dry_run": dry_run, "updated_cells": 0, "message": "Sin campos para actualizar."}

    if not dry_run:
        batch_update_values(spreadsheet_id, updates, headers, timeout)

    return {
        "ok": True,
        "dry_run": dry_run,
        "updated_cells": len(updates),
        "spreadsheet_id": spreadsheet_id,
        "sheet_name": sheet_name,
        "row_number": row_number,
        "updates": updates,
    }


def run_search(args: argparse.Namespace) -> Dict[str, Any]:
    headers = auth_headers(args.service_account, args.timeout)
    sources = get_sources(args.central_id, headers, args.timeout)
    ensure_result_headers(args.central_id, headers, args.timeout)

    results = search_contacts(
        term=args.term,
        max_results=args.max_results,
        min_score=args.min_score,
        sources=sources,
        headers=headers,
        timeout=args.timeout,
    )

    if not args.no_write_results:
        write_results_sheet(args.central_id, args.term, results, headers, args.timeout)

    payload = {
        "ok": True,
        "term": args.term,
        "sources_checked": len(sources),
        "results_count": len(results),
        "results": results,
    }

    if args.out_json:
        out = Path(args.out_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    return payload


def run_update(args: argparse.Namespace) -> Dict[str, Any]:
    headers = auth_headers(args.service_account, args.timeout)
    payload = update_contact(
        central_id=args.central_id,
        spreadsheet_id=args.spreadsheet_id,
        sheet_name=args.sheet_name,
        row_number=args.row_number,
        new_values={
            "name": args.name,
            "email": args.email,
            "phone": args.phone,
            "contact_id": args.contact_id,
            "notes": args.notes,
        },
        dry_run=bool(args.dry_run),
        headers=headers,
        timeout=args.timeout,
    )
    return payload


def main() -> None:
    args = parse_args()
    if args.command == "search":
        result = run_search(args)
    elif args.command == "update":
        result = run_update(args)
    else:
        raise RuntimeError(f"Comando no soportado: {args.command}")

    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
