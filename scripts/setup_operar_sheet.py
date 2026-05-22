#!/usr/bin/env python3
"""
Prepara la pestaña OPERAR para uso diario desde Google Sheets.

Objetivo:
- El usuario opera por hoja (no por chat).
- Campos claros para BUSCAR y ACTUALIZAR.
- Checkboxes para lanzar acciones.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account


DEFAULT_CENTRAL_ID = "REPLACE_WITH_SHEET_ID"

OPERAR_SHEET = "OPERAR"

CORP_RED = {"red": 214 / 255, "green": 40 / 255, "blue": 40 / 255}
CORP_YELLOW = {"red": 255 / 255, "green": 210 / 255, "blue": 63 / 255}
CORP_WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0}
CORP_BLACK = {"red": 0.0, "green": 0.0, "blue": 0.0}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Configurar pestaña OPERAR.")
    parser.add_argument("--service-account", required=True, help="Ruta JSON service account.")
    parser.add_argument("--spreadsheet-id", default=DEFAULT_CENTRAL_ID, help="Spreadsheet ID central.")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout HTTP en segundos.")
    return parser.parse_args()


def auth_headers(service_account_file: str) -> Dict[str, str]:
    creds = service_account.Credentials.from_service_account_file(
        service_account_file,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    creds.refresh(Request())
    return {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}


def get_spreadsheet_meta(spreadsheet_id: str, headers: Dict[str, str], timeout: int) -> Dict[str, Any]:
    fields = "sheets(properties(sheetId,title,index,gridProperties(rowCount,columnCount)))"
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
    response = requests.get(url, headers=headers, params={"fields": fields}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def find_sheet(meta: Dict[str, Any], title: str) -> Dict[str, Any] | None:
    for sheet in meta.get("sheets", []) or []:
        props = sheet.get("properties", {}) or {}
        if props.get("title") == title:
            return sheet
    return None


def batch_update(spreadsheet_id: str, requests_payload: List[Dict[str, Any]], headers: Dict[str, str], timeout: int) -> Dict[str, Any]:
    if not requests_payload:
        return {}
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}:batchUpdate"
    response = requests.post(url, headers=headers, json={"requests": requests_payload}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def values_update(
    spreadsheet_id: str,
    a1_range: str,
    values: List[List[Any]],
    headers: Dict[str, str],
    timeout: int,
) -> None:
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{a1_range}"
    params = {"valueInputOption": "RAW"}
    payload = {"range": a1_range, "majorDimension": "ROWS", "values": values}
    response = requests.put(url, headers=headers, params=params, json=payload, timeout=timeout)
    response.raise_for_status()


def main() -> None:
    args = parse_args()
    headers = auth_headers(args.service_account)

    meta = get_spreadsheet_meta(args.spreadsheet_id, headers, args.timeout)
    operar = find_sheet(meta, OPERAR_SHEET)
    if not operar:
        batch_update(
            args.spreadsheet_id,
            [{"addSheet": {"properties": {"title": OPERAR_SHEET}}}],
            headers,
            args.timeout,
        )
        meta = get_spreadsheet_meta(args.spreadsheet_id, headers, args.timeout)
        operar = find_sheet(meta, OPERAR_SHEET)
    if not operar:
        raise RuntimeError("No se pudo crear/encontrar la pestaña OPERAR.")

    props = operar.get("properties", {}) or {}
    grid = props.get("gridProperties", {}) or {}
    operar_id = int(props.get("sheetId", 0))
    row_count = int(grid.get("rowCount", 1000))
    col_count = int(grid.get("columnCount", 26))

    reqs: List[Dict[str, Any]] = []

    # Mueve OPERAR al indice 1, justo despues de GUIA.
    reqs.append(
        {
            "updateSheetProperties": {
                "properties": {"sheetId": operar_id, "index": 1, "tabColorStyle": {"rgbColor": CORP_RED}},
                "fields": "index,tabColorStyle",
            }
        }
    )

    # Limpieza base visual.
    reqs.append(
        {
            "repeatCell": {
                "range": {
                    "sheetId": operar_id,
                    "startRowIndex": 0,
                    "endRowIndex": row_count,
                    "startColumnIndex": 0,
                    "endColumnIndex": col_count,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColorStyle": {"rgbColor": CORP_WHITE},
                        "textFormat": {"foregroundColorStyle": {"rgbColor": CORP_BLACK}, "bold": False},
                        "horizontalAlignment": "LEFT",
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(backgroundColorStyle,textFormat.foregroundColorStyle,textFormat.bold,horizontalAlignment,verticalAlignment)",
            }
        }
    )

    # Cabecera.
    reqs.append(
        {
            "repeatCell": {
                "range": {
                    "sheetId": operar_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 8,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColorStyle": {"rgbColor": CORP_RED},
                        "textFormat": {"foregroundColorStyle": {"rgbColor": CORP_WHITE}, "bold": True, "fontSize": 12},
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat(backgroundColorStyle,textFormat.foregroundColorStyle,textFormat.bold,textFormat.fontSize,horizontalAlignment)",
            }
        }
    )

    # Bloque BUSCAR (amarillo).
    reqs.append(
        {
            "repeatCell": {
                "range": {"sheetId": operar_id, "startRowIndex": 2, "endRowIndex": 9, "startColumnIndex": 0, "endColumnIndex": 2},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColorStyle": {"rgbColor": CORP_YELLOW},
                        "textFormat": {"foregroundColorStyle": {"rgbColor": CORP_BLACK}, "bold": True},
                    }
                },
                "fields": "userEnteredFormat(backgroundColorStyle,textFormat.foregroundColorStyle,textFormat.bold)",
            }
        }
    )

    # Bloque ACTUALIZAR (rojo etiqueta).
    reqs.append(
        {
            "repeatCell": {
                "range": {"sheetId": operar_id, "startRowIndex": 10, "endRowIndex": 19, "startColumnIndex": 0, "endColumnIndex": 2},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColorStyle": {"rgbColor": CORP_RED},
                        "textFormat": {"foregroundColorStyle": {"rgbColor": CORP_WHITE}, "bold": True},
                    }
                },
                "fields": "userEnteredFormat(backgroundColorStyle,textFormat.foregroundColorStyle,textFormat.bold)",
            }
        }
    )

    # Congelar fila 1 y ajustar columnas.
    reqs.append(
        {
            "updateSheetProperties": {
                "properties": {"sheetId": operar_id, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }
        }
    )
    reqs.append(
        {
            "autoResizeDimensions": {
                "dimensions": {"sheetId": operar_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 8}
            }
        }
    )

    # Checkboxes.
    checkbox_rule = {"condition": {"type": "BOOLEAN"}, "strict": True}
    reqs.append(
        {
            "setDataValidation": {
                "range": {"sheetId": operar_id, "startRowIndex": 5, "endRowIndex": 6, "startColumnIndex": 1, "endColumnIndex": 2},
                "rule": checkbox_rule,
            }
        }
    )
    reqs.append(
        {
            "setDataValidation": {
                "range": {"sheetId": operar_id, "startRowIndex": 15, "endRowIndex": 17, "startColumnIndex": 1, "endColumnIndex": 2},
                "rule": checkbox_rule,
            }
        }
    )

    batch_update(args.spreadsheet_id, reqs, headers, args.timeout)

    rows = [
        ["OPERAR CONTACTOS (HOJA CENTRAL)", "ARTES BURO", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["BUSCAR EN TODOS LOS CRM", "", "", "", "", "", "", ""],
        ["TERMINO", ""],
        ["MAX_RESULTADOS", 20],
        ["EJECUTAR_BUSQUEDA (TRUE/FALSE)", False],
        ["ESTADO_BUSQUEDA", "PENDIENTE"],
        ["ULTIMO_RESULTADO", ""],
        ["", ""],
        ["ACTUALIZAR CONTACTO", ""],
        ["FILA_EN_RESULTADOS (ej:2)", 2],
        ["NUEVO_NOMBRE", ""],
        ["NUEVO_EMAIL", ""],
        ["NUEVO_TELEFONO", ""],
        ["NUEVO_ID", ""],
        ["NUEVAS_NOTAS", ""],
        ["DRY_RUN (TRUE/FALSE)", True],
        ["EJECUTAR_ACTUALIZACION (TRUE/FALSE)", False],
        ["ESTADO_ACTUALIZACION", "PENDIENTE"],
        ["ULTIMO_RESULTADO", ""],
        ["", ""],
        ["AYUDA", "1) Escribe termino en B4. 2) Pon TRUE en B6. 3) Revisa RESULTADOS."],
        ["AYUDA", "4) Para actualizar: fila resultado en B11, cambios en B12:B16, TRUE en B18."],
    ]
    values_update(args.spreadsheet_id, f"{OPERAR_SHEET}!A1", rows, headers, args.timeout)

    print(
        json.dumps(
            {
                "ok": True,
                "spreadsheetId": args.spreadsheet_id,
                "sheet": OPERAR_SHEET,
                "sheetId": operar_id,
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
