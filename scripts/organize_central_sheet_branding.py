#!/usr/bin/env python3
"""
Organiza y aplica estilo corporativo a la hoja central CRM.

Acciones:
- Elimina "Hoja 1" si existe.
- Reordena pestañas operativas.
- Aplica colores corporativos (rojo/amarillo/blanco) en cabeceras y pestañas.
- Congela primera fila.
- Activa filtro basico en hojas clave.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account


DEFAULT_CENTRAL_ID = "REPLACE_WITH_SHEET_ID"

CORP_RED = {"red": 214 / 255, "green": 40 / 255, "blue": 40 / 255}
CORP_YELLOW = {"red": 255 / 255, "green": 210 / 255, "blue": 63 / 255}
CORP_WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0}
CORP_BLACK = {"red": 0.0, "green": 0.0, "blue": 0.0}


@dataclass
class SheetInfo:
    sheet_id: int
    title: str
    index: int
    row_count: int
    column_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Organizar hoja central CRM con branding corporativo.")
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


def get_spreadsheet_meta(
    spreadsheet_id: str,
    headers: Dict[str, str],
    timeout: int,
) -> List[SheetInfo]:
    fields = "sheets(properties(sheetId,title,index,gridProperties(rowCount,columnCount)))"
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
    response = requests.get(url, headers=headers, params={"fields": fields}, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    out: List[SheetInfo] = []
    for sheet in payload.get("sheets", []) or []:
        props = sheet.get("properties", {}) or {}
        grid = props.get("gridProperties", {}) or {}
        out.append(
            SheetInfo(
                sheet_id=int(props.get("sheetId", 0)),
                title=str(props.get("title", "")),
                index=int(props.get("index", 0)),
                row_count=int(grid.get("rowCount", 1000)),
                column_count=int(grid.get("columnCount", 26)),
            )
        )
    return out


def batch_update(
    spreadsheet_id: str,
    requests_payload: List[Dict[str, Any]],
    headers: Dict[str, str],
    timeout: int,
) -> Dict[str, Any]:
    if not requests_payload:
        return {}
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}:batchUpdate"
    response = requests.post(url, headers=headers, json={"requests": requests_payload}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def find_sheet(sheets: List[SheetInfo], title: str) -> Optional[SheetInfo]:
    for sheet in sheets:
        if sheet.title == title:
            return sheet
    return None


def build_style_requests(sheets: List[SheetInfo]) -> List[Dict[str, Any]]:
    requests_payload: List[Dict[str, Any]] = []

    style_map = {
        "GUIA": {"tab": CORP_YELLOW, "header_bg": CORP_RED, "header_fg": CORP_WHITE},
        "FUENTES": {"tab": CORP_RED, "header_bg": CORP_RED, "header_fg": CORP_WHITE},
        "RESULTADOS": {"tab": CORP_YELLOW, "header_bg": CORP_YELLOW, "header_fg": CORP_BLACK},
        "IA_LOCAL_COLA": {"tab": CORP_WHITE, "header_bg": CORP_RED, "header_fg": CORP_WHITE},
        "LOG": {"tab": CORP_RED, "header_bg": CORP_YELLOW, "header_fg": CORP_BLACK},
        "AUDITORIA_HOJA": {"tab": CORP_YELLOW, "header_bg": CORP_RED, "header_fg": CORP_WHITE},
    }

    for sheet in sheets:
        if sheet.title not in style_map:
            continue
        style = style_map[sheet.title]

        requests_payload.append(
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": sheet.sheet_id, "tabColorStyle": {"rgbColor": style["tab"]}},
                    "fields": "tabColorStyle",
                }
            }
        )

        requests_payload.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet.sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": sheet.row_count,
                        "startColumnIndex": 0,
                        "endColumnIndex": sheet.column_count,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColorStyle": {"rgbColor": CORP_WHITE},
                            "textFormat": {"foregroundColorStyle": {"rgbColor": CORP_BLACK}, "bold": False},
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColorStyle,textFormat.foregroundColorStyle,textFormat.bold)",
                }
            }
        )

        requests_payload.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet.sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": sheet.column_count,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColorStyle": {"rgbColor": style["header_bg"]},
                            "textFormat": {"foregroundColorStyle": {"rgbColor": style["header_fg"]}, "bold": True},
                            "horizontalAlignment": "CENTER",
                            "verticalAlignment": "MIDDLE",
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColorStyle,textFormat.foregroundColorStyle,textFormat.bold,horizontalAlignment,verticalAlignment)",
                }
            }
        )

        requests_payload.append(
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet.sheet_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            }
        )

        requests_payload.append(
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": sheet.sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": sheet.column_count,
                    }
                }
            }
        )

        if sheet.title in ("FUENTES", "RESULTADOS", "IA_LOCAL_COLA"):
            requests_payload.append(
                {
                    "setBasicFilter": {
                        "filter": {
                            "range": {
                                "sheetId": sheet.sheet_id,
                                "startRowIndex": 0,
                                "endRowIndex": sheet.row_count,
                                "startColumnIndex": 0,
                                "endColumnIndex": sheet.column_count,
                            }
                        }
                    }
                }
            )

    return requests_payload


def update_values(
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

    before = get_spreadsheet_meta(args.spreadsheet_id, headers, args.timeout)
    delete_requests: List[Dict[str, Any]] = []
    hoja1 = find_sheet(before, "Hoja 1")
    if hoja1:
        delete_requests.append({"deleteSheet": {"sheetId": hoja1.sheet_id}})
    if delete_requests:
        batch_update(args.spreadsheet_id, delete_requests, headers, args.timeout)

    sheets = get_spreadsheet_meta(args.spreadsheet_id, headers, args.timeout)
    if not find_sheet(sheets, "GUIA"):
        batch_update(
            args.spreadsheet_id,
            [{"addSheet": {"properties": {"title": "GUIA"}}}],
            headers,
            args.timeout,
        )
        sheets = get_spreadsheet_meta(args.spreadsheet_id, headers, args.timeout)

    desired_order = ["GUIA", "FUENTES", "RESULTADOS", "IA_LOCAL_COLA", "LOG", "AUDITORIA_HOJA"]
    order_requests: List[Dict[str, Any]] = []
    for target_index, title in enumerate(desired_order):
        sheet = find_sheet(sheets, title)
        if not sheet:
            continue
        if sheet.index != target_index:
            order_requests.append(
                {
                    "updateSheetProperties": {
                        "properties": {"sheetId": sheet.sheet_id, "index": target_index},
                        "fields": "index",
                    }
                }
            )
    if order_requests:
        batch_update(args.spreadsheet_id, order_requests, headers, args.timeout)

    sheets = get_spreadsheet_meta(args.spreadsheet_id, headers, args.timeout)
    style_requests = build_style_requests(sheets)
    batch_update(args.spreadsheet_id, style_requests, headers, args.timeout)

    guia_rows = [
        ["APP_ARTES-BUHO_CRM-CENTRAL", "GUIA RAPIDA"],
        ["PASO 1", "Ve a FUENTES y deja activas solo las fuentes que quieras usar (ACTIVO=TRUE)."],
        ["PASO 2", "Lanza la busqueda remota y revisa coincidencias en RESULTADOS."],
        ["PASO 3", "Elige la fila correcta y actualiza el contacto en su hoja origen."],
        ["PASO 4", "Si usas automatizacion, revisa IA_LOCAL_COLA para estado de tareas."],
        ["PASO 5", "LOG muestra incidencias. AUDITORIA_HOJA guarda evidencia tecnica."],
        ["COLORES", "Rojo = accion/configuracion. Amarillo = salida/seguimiento. Blanco = base de lectura."],
    ]
    update_values(args.spreadsheet_id, "GUIA!A1", guia_rows, headers, args.timeout)

    after = get_spreadsheet_meta(args.spreadsheet_id, headers, args.timeout)
    ordered = sorted(after, key=lambda s: s.index)
    print(
        json.dumps(
            {
                "ok": True,
                "spreadsheetId": args.spreadsheet_id,
                "deletedHoja1": bool(hoja1),
                "tabs": [{"index": s.index, "title": s.title, "sheetId": s.sheet_id} for s in ordered],
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
