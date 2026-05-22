#!/usr/bin/env python3
"""
Setup remoto de hoja central para APP_ARTES-BUHO_CRM-CENTRAL.

Que hace:
1) Crea (si faltan) hojas internas: FUENTES, RESULTADOS, LOG, IA_LOCAL_COLA, AUDITORIA_HOJA.
2) Escribe cabeceras estandar.
3) Sincroniza fuentes desde catalogo CRM (todas las pestanas visibles).
4) Vuelca resumen de auditoria en AUDITORIA_HOJA.
5) Deja registro operativo en LOG.

Uso:
  python scripts/setup_remote_central.py ^
    --service-account C:\\ruta\\service-account.json ^
    --summary-json reports\\crm_inspection\\2026-04-06\\crm_summary.json
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account


CENTRAL_ID = "REPLACE_WITH_SHEET_ID"

CRM_CATALOG = [
    ("CRM_01", "REPLACE_WITH_SHEET_ID"),
    ("CRM_02", "REPLACE_WITH_SHEET_ID"),
    ("CRM_03", "REPLACE_WITH_SHEET_ID"),
    ("CRM_04", "REPLACE_WITH_SHEET_ID"),
    ("CRM_05", "REPLACE_WITH_SHEET_ID"),
    ("CRM_06", "REPLACE_WITH_SHEET_ID"),
    ("CRM_07", "REPLACE_WITH_SHEET_ID"),
]

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

LOG_HEADERS = ["FECHA", "NIVEL", "MENSAJE", "DETALLE_JSON"]
AI_QUEUE_HEADERS = [
    "CREATED_AT",
    "TASK_TYPE",
    "STATUS",
    "PAYLOAD_JSON",
    "RESULT_JSON",
    "LAST_ERROR",
    "NEXT_RETRY_AT",
    "ATTEMPTS",
]
AUDIT_HEADERS = ["FECHA", "ALCANCE", "SPREADSHEET_ID", "SHEET", "SECCION", "DETALLE_JSON"]

HEADER_CANDIDATES = {
    "CAMPO_NOMBRE": "NOMBRE|NOMBRE Y APELLIDOS|CONTACTO|CLIENTE|NOM|EMPRESA|RAZON SOCIAL",
    "CAMPO_EMAIL": "EMAIL|E-MAIL|CORREO|MAIL|CORREO ELECTRONICO",
    "CAMPO_TELEFONO": "TELEFONO|MOVIL|CELULAR|TLF|TELEFONO 1|WHATSAPP",
    "CAMPO_ID": "ID|IDENTIFICADOR|CODIGO|ID CLIENTE|ID CONTACTO",
    "CAMPO_NOTAS": "NOTAS|OBSERVACIONES|COMENTARIOS|DETALLE",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Setup remoto de hoja central CRM.")
    parser.add_argument("--service-account", required=True, help="Ruta JSON de service account.")
    parser.add_argument(
        "--summary-json",
        required=True,
        help="Ruta a crm_summary.json para volcado de auditoria.",
    )
    return parser.parse_args()


def get_headers(service_account_file):
    creds = service_account.Credentials.from_service_account_file(
        service_account_file,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    creds.refresh(Request())
    return {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}


def get_spreadsheet_meta(spreadsheet_id, headers):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
    params = {"fields": "properties.title,sheets(properties(sheetId,title,hidden,index,gridProperties))"}
    r = requests.get(url, headers=headers, params=params, timeout=90)
    r.raise_for_status()
    return r.json()


def batch_update(spreadsheet_id, requests_payload, headers):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}:batchUpdate"
    r = requests.post(url, headers=headers, json={"requests": requests_payload}, timeout=120)
    r.raise_for_status()


def values_clear(spreadsheet_id, a1_range, headers):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{a1_range}:clear"
    r = requests.post(url, headers=headers, json={}, timeout=60)
    r.raise_for_status()


def values_update(spreadsheet_id, a1_range, values, headers):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{a1_range}"
    params = {"valueInputOption": "RAW"}
    r = requests.put(
        url,
        headers=headers,
        params=params,
        json={"range": a1_range, "majorDimension": "ROWS", "values": values},
        timeout=120,
    )
    r.raise_for_status()


def main():
    args = parse_args()
    headers = get_headers(args.service_account)
    summary = json.loads(Path(args.summary_json).read_text(encoding="utf-8"))

    central_meta = get_spreadsheet_meta(CENTRAL_ID, headers)
    existing = {s["properties"]["title"] for s in central_meta.get("sheets", [])}
    needed = ["FUENTES", "RESULTADOS", "LOG", "IA_LOCAL_COLA", "AUDITORIA_HOJA"]
    add_reqs = []
    for title in needed:
        if title not in existing:
            add_reqs.append({"addSheet": {"properties": {"title": title}}})
    if add_reqs:
        batch_update(CENTRAL_ID, add_reqs, headers)

    values_update(CENTRAL_ID, "FUENTES!A1", [SOURCE_HEADERS], headers)
    values_update(CENTRAL_ID, "RESULTADOS!A1", [RESULT_HEADERS], headers)
    values_update(CENTRAL_ID, "LOG!A1", [LOG_HEADERS], headers)
    values_update(CENTRAL_ID, "IA_LOCAL_COLA!A1", [AI_QUEUE_HEADERS], headers)
    values_update(CENTRAL_ID, "AUDITORIA_HOJA!A1", [AUDIT_HEADERS], headers)

    source_rows = []
    source_summary = []
    source_errors = []
    for alias, spreadsheet_id in CRM_CATALOG:
        try:
            meta = get_spreadsheet_meta(spreadsheet_id, headers)
            tabs = [
                s["properties"]["title"]
                for s in meta.get("sheets", [])
                if not s["properties"].get("hidden", False)
            ]
            for tab in tabs:
                source_rows.append(
                    [
                        True,
                        alias,
                        spreadsheet_id,
                        tab,
                        1,
                        HEADER_CANDIDATES["CAMPO_NOMBRE"],
                        HEADER_CANDIDATES["CAMPO_EMAIL"],
                        HEADER_CANDIDATES["CAMPO_TELEFONO"],
                        HEADER_CANDIDATES["CAMPO_ID"],
                        HEADER_CANDIDATES["CAMPO_NOTAS"],
                    ]
                )
            source_summary.append(
                {"alias": alias, "spreadsheetId": spreadsheet_id, "tabs": len(tabs), "ok": True}
            )
        except Exception as error:  # noqa: BLE001
            source_errors.append(
                {"alias": alias, "spreadsheetId": spreadsheet_id, "error": str(error)}
            )
            source_summary.append(
                {"alias": alias, "spreadsheetId": spreadsheet_id, "tabs": 0, "ok": False}
            )

    values_clear(CENTRAL_ID, "FUENTES!A2:Z", headers)
    if source_rows:
        values_update(CENTRAL_ID, "FUENTES!A2", source_rows, headers)

    now = datetime.utcnow().isoformat() + "Z"
    audit_rows = []
    for crm in summary.get("crms", []):
        audit_rows.append(
            [
                now,
                "CRM_XLSX_EXPORT",
                crm.get("spreadsheet_id", ""),
                "",
                "SUMMARY",
                json.dumps(crm, ensure_ascii=True),
            ]
        )

    values_clear(CENTRAL_ID, "AUDITORIA_HOJA!A2:Z", headers)
    if audit_rows:
        values_update(CENTRAL_ID, "AUDITORIA_HOJA!A2", audit_rows, headers)

    log_detail = {
        "connectedSources": len(source_rows),
        "crmCount": len(CRM_CATALOG),
        "sourceSummary": source_summary,
        "sourceErrors": source_errors,
        "auditRows": len(audit_rows),
    }
    values_clear(CENTRAL_ID, "LOG!A2:Z", headers)
    values_update(
        CENTRAL_ID,
        "LOG!A2",
        [[now, "INFO", "Setup remoto completado", json.dumps(log_detail, ensure_ascii=True)]],
        headers,
    )

    print(
        json.dumps(
            {
                "ok": True,
                "centralSpreadsheetId": CENTRAL_ID,
                "connectedSourceRows": len(source_rows),
                "sourceErrors": source_errors,
                "auditRows": len(audit_rows),
            },
            ensure_ascii=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
