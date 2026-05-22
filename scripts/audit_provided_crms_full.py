#!/usr/bin/env python3
"""
Auditoria completa por API de los 7 CRM proporcionados.

Genera:
- reports/crm_inspection/YYYY-MM-DD/*.inspection.json
- docs/INSPECCION_CRM_YYYY-MM-DD.md
- reports/crm_inspection/YYYY-MM-DD/crm_summary_live.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class CrmItem:
    alias: str
    spreadsheet_id: str


CATALOG: List[CrmItem] = [
    CrmItem("CRM_01", "REPLACE_WITH_SHEET_ID"),
    CrmItem("CRM_02", "REPLACE_WITH_SHEET_ID"),
    CrmItem("CRM_03", "REPLACE_WITH_SHEET_ID"),
    CrmItem("CRM_04", "REPLACE_WITH_SHEET_ID"),
    CrmItem("CRM_05", "REPLACE_WITH_SHEET_ID"),
    CrmItem("CRM_06", "REPLACE_WITH_SHEET_ID"),
    CrmItem("CRM_07", "REPLACE_WITH_SHEET_ID"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Auditar los 7 CRM proporcionados por API.")
    parser.add_argument("--service-account", required=True, help="Ruta al JSON de service account.")
    parser.add_argument(
        "--date",
        default=str(date.today()),
        help="Fecha para carpeta de salida (YYYY-MM-DD). Por defecto: hoy.",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Raiz del proyecto APP_ARTES-BUHO_CRM-CENTRAL.",
    )
    return parser.parse_args()


def run_cmd(command: List[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )


def safe_name(text: str) -> str:
    return "".join(ch for ch in text if ch.isalnum() or ch in ("_", "-", ".")) or "unknown"


def to_ascii(text: str) -> str:
    return str(text or "").encode("ascii", "replace").decode("ascii")


def build_summary_item(alias: str, spreadsheet_id: str, json_path: Path) -> Dict[str, object]:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    sheets = payload.get("sheets", []) or []
    permissions = payload.get("workbookPermissions", {}) or {}
    errors = payload.get("errors", []) or []
    first_error = ""
    if errors:
        first = errors[0] or {}
        first_error = str(first.get("error", ""))[:500]
    return {
        "alias": alias,
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_name": payload.get("spreadsheetName", ""),
        "sheet_count": len(sheets),
        "sheet_names": [s.get("sheetName", "") for s in sheets],
        "filter_views_total": (payload.get("filterViews", {}) or {}).get("total", 0),
        "errors_count": len(errors),
        "first_error": first_error,
        "owner": permissions.get("owner", ""),
        "editors_count": len(permissions.get("editors", []) or []),
    }


def build_markdown(date_label: str, summary: Dict[str, object], reports_dir: Path) -> str:
    lines: List[str] = []
    lines.append(f"# INSPECCION CRM - {date_label}")
    lines.append("")
    lines.append("Metodo:")
    lines.append("- Google Sheets API + Drive API (service account)")
    lines.append("- Cobertura completa: estructura, datos, formatos, combinadas, validaciones, filtros, condicional, protecciones, permisos")
    lines.append("")
    lines.append("## Resumen")
    lines.append(f"- Total CRM: {summary.get('total_crms', 0)}")
    lines.append(f"- Exitos: {summary.get('ok_crms', 0)}")
    lines.append(f"- Fallos: {summary.get('error_crms', 0)}")
    lines.append("")
    lines.append("## Detalle por CRM")
    for item in summary.get("crms", []) or []:
        alias = item.get("alias", "")
        spreadsheet_id = item.get("spreadsheet_id", "")
        ok = bool(item.get("ok", False))
        icon = "OK" if ok else "ERROR"
        lines.append(f"- {alias} [{icon}]")
        lines.append(f"  - Spreadsheet ID: `{spreadsheet_id}`")
        if ok:
            lines.append(f"  - Nombre: `{to_ascii(item.get('spreadsheet_name', ''))}`")
            lines.append(f"  - Pestanas: {item.get('sheet_count', 0)}")
            lines.append(f"  - Filter views: {item.get('filter_views_total', 0)}")
            lines.append(f"  - Errores de auditoria: {item.get('errors_count', 0)}")
            lines.append(f"  - Propietario: `{item.get('owner', '')}`")
            lines.append(f"  - Editores detectados: {item.get('editors_count', 0)}")
            lines.append(f"  - JSON: `reports/crm_inspection/{date_label}/{spreadsheet_id}.inspection.json`")
            report_file = reports_dir / f"{spreadsheet_id}.inspection.md"
            if report_file.exists():
                lines.append(f"  - MD: `reports/crm_inspection/{date_label}/{report_file.name}`")
        else:
            lines.append(f"  - Error: `{to_ascii(item.get('error', ''))}`")
    lines.append("")
    lines.append("## Nota")
    lines.append("- El detalle tecnico completo esta en los JSON de cada CRM.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = Path(args.project_root).resolve()
    date_label = args.date

    reports_dir = root / "reports" / "crm_inspection" / date_label
    reports_dir.mkdir(parents=True, exist_ok=True)

    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    audit_script = root / "scripts" / "audit_google_sheet_full.py"
    if not audit_script.exists():
        raise FileNotFoundError(f"No se encuentra script base: {audit_script}")

    summary: Dict[str, object] = {
        "generated_at": date_label,
        "method": "google_api_full",
        "total_crms": len(CATALOG),
        "ok_crms": 0,
        "error_crms": 0,
        "crms": [],
    }

    for crm in CATALOG:
        out_json = reports_dir / f"{crm.spreadsheet_id}.inspection.json"
        out_md = reports_dir / f"{crm.spreadsheet_id}.inspection.md"
        scope = f"CRM_FULL_{crm.alias}_{date_label}"

        cmd = [
            sys.executable,
            str(audit_script),
            "--service-account",
            args.service_account,
            "--spreadsheet-id",
            crm.spreadsheet_id,
            "--scope",
            scope,
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
        result = run_cmd(cmd, cwd=root)
        if result.returncode != 0:
            summary["error_crms"] = int(summary["error_crms"]) + 1
            (summary["crms"]).append(  # type: ignore[arg-type]
                {
                    "alias": crm.alias,
                    "spreadsheet_id": crm.spreadsheet_id,
                    "ok": False,
                    "error": result.stderr.strip() or result.stdout.strip() or "Unknown error",
                }
            )
            continue

        try:
            item = build_summary_item(crm.alias, crm.spreadsheet_id, out_json)
            ok_item = int(item.get("errors_count", 0)) == 0 and int(item.get("sheet_count", 0)) > 0
            item["ok"] = ok_item
            if not ok_item and not item.get("first_error"):
                item["first_error"] = "Sin pestanas detectadas o con errores de auditoria."
            if not ok_item:
                item["error"] = item.get("first_error", "")
            (summary["crms"]).append(item)  # type: ignore[arg-type]
            if ok_item:
                summary["ok_crms"] = int(summary["ok_crms"]) + 1
            else:
                summary["error_crms"] = int(summary["error_crms"]) + 1
        except Exception as err:  # noqa: BLE001
            summary["error_crms"] = int(summary["error_crms"]) + 1
            (summary["crms"]).append(  # type: ignore[arg-type]
                {
                    "alias": crm.alias,
                    "spreadsheet_id": crm.spreadsheet_id,
                    "ok": False,
                    "error": str(err),
                }
            )

    summary_path = reports_dir / "crm_summary_live.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")

    md_content = build_markdown(date_label, summary, reports_dir)
    doc_path = docs_dir / f"INSPECCION_CRM_{safe_name(date_label)}.md"
    doc_path.write_text(md_content, encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "date": date_label,
                "summary_json": str(summary_path),
                "summary_md": str(doc_path),
                "ok_crms": summary.get("ok_crms", 0),
                "error_crms": summary.get("error_crms", 0),
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
