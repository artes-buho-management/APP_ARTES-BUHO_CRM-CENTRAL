#!/usr/bin/env python3
"""
Auditoria completa de un Google Sheet por API (Sheets + Drive).

Cobertura:
1) Estructura completa (libro, pestanas, rangos usados, filas/columnas)
2) Datos visibles relevantes y formulas (preview)
3) Formatos aplicados (preview)
4) Celdas combinadas
5) Validaciones y desplegables
6) Filtros y vistas de filtro
7) Reglas de formato condicional
8) Protecciones de hoja/rango y permisos del libro
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Auditoria completa de Google Sheets por API.")
    parser.add_argument("--service-account", required=True, help="Ruta al JSON de service account.")
    parser.add_argument("--spreadsheet-id", required=True, help="Spreadsheet ID objetivo.")
    parser.add_argument("--scope", default="MANUAL", help="Etiqueta de alcance para el reporte.")
    parser.add_argument("--out-json", required=True, help="Ruta de salida JSON.")
    parser.add_argument("--out-md", help="Ruta de salida Markdown.")
    parser.add_argument("--preview-rows", type=int, default=25, help="Filas preview por hoja.")
    parser.add_argument("--preview-cols", type=int, default=20, help="Columnas preview por hoja.")
    parser.add_argument("--timeout", type=int, default=180, help="Timeout HTTP por peticion (s).")
    return parser.parse_args()


def auth_headers(service_account_file: str, scopes: List[str]) -> Dict[str, str]:
    creds = service_account.Credentials.from_service_account_file(
        service_account_file,
        scopes=scopes,
    )
    creds.refresh(Request())
    return {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}


def col_to_a1(col_1_based: int) -> str:
    n = max(1, int(col_1_based))
    out = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def cell_a1(row_1_based: int, col_1_based: int) -> str:
    return f"{col_to_a1(col_1_based)}{row_1_based}"


def grid_range_to_a1(
    grid: Dict[str, Any] | None,
    fallback_max_rows: int = 1,
    fallback_max_cols: int = 1,
) -> str:
    if not grid:
        return ""

    start_row = int(grid.get("startRowIndex", 0)) + 1
    start_col = int(grid.get("startColumnIndex", 0)) + 1
    end_row = int(grid.get("endRowIndex", 0)) if "endRowIndex" in grid else fallback_max_rows
    end_col = int(grid.get("endColumnIndex", 0)) if "endColumnIndex" in grid else fallback_max_cols

    end_row = max(start_row, end_row)
    end_col = max(start_col, end_col)
    return f"{cell_a1(start_row, start_col)}:{cell_a1(end_row, end_col)}"


def rgb_to_hex(color: Dict[str, Any] | None) -> str:
    if not color:
        return ""
    red = max(0, min(255, round(float(color.get("red", 0.0)) * 255)))
    green = max(0, min(255, round(float(color.get("green", 0.0)) * 255)))
    blue = max(0, min(255, round(float(color.get("blue", 0.0)) * 255)))
    return f"#{red:02X}{green:02X}{blue:02X}"


def has_cell_value(cell: Dict[str, Any] | None) -> bool:
    if not cell:
        return False
    if "userEnteredValue" in cell and isinstance(cell["userEnteredValue"], dict) and cell["userEnteredValue"]:
        return True
    formatted = cell.get("formattedValue")
    return formatted not in (None, "")


def get_sheet_cell_lookup(sheet: Dict[str, Any]) -> Dict[Tuple[int, int], Dict[str, Any]]:
    lookup: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for block in sheet.get("data", []) or []:
        start_row = int(block.get("startRow", 0))
        start_col = int(block.get("startColumn", 0))
        rows = block.get("rowData", []) or []
        for r_offset, row in enumerate(rows):
            values = (row or {}).get("values", []) or []
            abs_row = start_row + r_offset + 1
            for c_offset, cell in enumerate(values):
                abs_col = start_col + c_offset + 1
                lookup[(abs_row, abs_col)] = cell or {}
    return lookup


def compute_used_range(sheet: Dict[str, Any]) -> Dict[str, Any]:
    last_row = 0
    last_col = 0
    lookup = get_sheet_cell_lookup(sheet)
    for (row, col), cell in lookup.items():
        if has_cell_value(cell):
            if row > last_row:
                last_row = row
            if col > last_col:
                last_col = col

    if last_row == 0 or last_col == 0:
        return {"lastRow": 0, "lastColumn": 0, "usedRangeA1": "", "usedRows": 0, "usedColumns": 0}

    return {
        "lastRow": last_row,
        "lastColumn": last_col,
        "usedRangeA1": f"A1:{cell_a1(last_row, last_col)}",
        "usedRows": last_row,
        "usedColumns": last_col,
    }


def inspect_visible_data_and_formulas(
    lookup: Dict[Tuple[int, int], Dict[str, Any]],
    last_row: int,
    last_col: int,
    preview_rows: int,
    preview_cols: int,
) -> Dict[str, Any]:
    if last_row < 1 or last_col < 1:
        return {"hasData": False, "previewRows": 0, "previewColumns": 0, "preview": [], "formulasPreview": []}

    rows = min(last_row, max(1, preview_rows))
    cols = min(last_col, max(1, preview_cols))
    preview: List[List[str]] = []
    formulas: List[List[str]] = []

    for r in range(1, rows + 1):
        row_values: List[str] = []
        row_formulas: List[str] = []
        for c in range(1, cols + 1):
            cell = lookup.get((r, c), {})
            row_values.append(str(cell.get("formattedValue", "")))
            formula = ""
            uev = cell.get("userEnteredValue", {}) or {}
            if isinstance(uev, dict):
                formula = str(uev.get("formulaValue", ""))
            row_formulas.append(formula)
        preview.append(row_values)
        formulas.append(row_formulas)

    return {
        "hasData": True,
        "previewRows": rows,
        "previewColumns": cols,
        "preview": preview,
        "formulasPreview": formulas,
    }


def inspect_formats(
    lookup: Dict[Tuple[int, int], Dict[str, Any]],
    last_row: int,
    last_col: int,
    preview_rows: int,
    preview_cols: int,
) -> Dict[str, Any]:
    if last_row < 1 or last_col < 1:
        return {"hasFormats": False, "previewRows": 0, "previewColumns": 0, "summary": {}}

    rows = min(last_row, max(1, preview_rows))
    cols = min(last_col, max(1, preview_cols))

    backgrounds = Counter()
    font_colors = Counter()
    font_families = Counter()
    font_sizes = Counter()
    font_weights = Counter()
    font_styles = Counter()
    horizontal_alignments = Counter()
    vertical_alignments = Counter()
    number_formats = Counter()
    wraps = Counter()
    borders = 0

    for r in range(1, rows + 1):
        for c in range(1, cols + 1):
            cell = lookup.get((r, c), {})
            uef = cell.get("userEnteredFormat", {}) or {}
            txt = uef.get("textFormat", {}) or {}

            backgrounds[rgb_to_hex(uef.get("backgroundColor")) or ""] += 1
            font_colors[rgb_to_hex(txt.get("foregroundColor")) or ""] += 1
            font_families[str(txt.get("fontFamily", ""))] += 1
            font_sizes[str(txt.get("fontSize", ""))] += 1
            font_weights["bold" if bool(txt.get("bold")) else "normal"] += 1
            font_styles["italic" if bool(txt.get("italic")) else "normal"] += 1
            horizontal_alignments[str(uef.get("horizontalAlignment", ""))] += 1
            vertical_alignments[str(uef.get("verticalAlignment", ""))] += 1

            num = uef.get("numberFormat", {}) or {}
            number_formats[f"{num.get('type', '')}|{num.get('pattern', '')}"] += 1
            wraps[str(uef.get("wrapStrategy", ""))] += 1

            b = uef.get("borders", {}) or {}
            if any((b.get(side, {}) or {}).get("style", "NONE") != "NONE" for side in ("top", "bottom", "left", "right")):
                borders += 1

    return {
        "hasFormats": True,
        "previewRows": rows,
        "previewColumns": cols,
        "summary": {
            "backgrounds": dict(backgrounds),
            "fontColors": dict(font_colors),
            "fontFamilies": dict(font_families),
            "fontSizes": dict(font_sizes),
            "fontWeights": dict(font_weights),
            "fontStyles": dict(font_styles),
            "horizontalAlignments": dict(horizontal_alignments),
            "verticalAlignments": dict(vertical_alignments),
            "numberFormats": dict(number_formats),
            "wraps": dict(wraps),
            "cellsWithBorderCount": borders,
        },
    }


def inspect_merged_cells(
    merges: List[Dict[str, Any]] | None,
    max_rows: int,
    max_cols: int,
) -> Dict[str, Any]:
    merges = merges or []
    sample = [grid_range_to_a1(m, max_rows, max_cols) for m in merges[:40]]
    return {"total": len(merges), "sampleRanges": sample}


def inspect_data_validations(
    lookup: Dict[Tuple[int, int], Dict[str, Any]],
    last_row: int,
    last_col: int,
) -> Dict[str, Any]:
    if last_row < 1 or last_col < 1:
        return {"totalCellsWithValidation": 0, "criteriaSummary": {}, "sample": []}

    total = 0
    criteria = Counter()
    sample: List[Dict[str, Any]] = []

    for r in range(1, last_row + 1):
        for c in range(1, last_col + 1):
            cell = lookup.get((r, c), {})
            rule = cell.get("dataValidation")
            if not rule:
                continue

            total += 1
            cond = rule.get("condition", {}) or {}
            ctype = str(cond.get("type", "UNKNOWN"))
            criteria[ctype] += 1

            if len(sample) < 40:
                sample.append(
                    {
                        "cell": cell_a1(r, c),
                        "criteriaType": ctype,
                        "allowInvalid": bool(rule.get("strict", False)) is False,
                        "helpText": str(rule.get("inputMessage", "")),
                    }
                )

    return {"totalCellsWithValidation": total, "criteriaSummary": dict(criteria), "sample": sample}


def inspect_filters(
    sheet: Dict[str, Any],
    max_rows: int,
    max_cols: int,
) -> Dict[str, Any]:
    basic = sheet.get("basicFilter")
    criteria_items = []

    if basic:
        for k, v in (basic.get("criteria", {}) or {}).items():
            try:
                col_index = int(k) + 1
            except (TypeError, ValueError):
                col_index = -1
            condition = (v or {}).get("condition", {}) or {}
            criteria_items.append(
                {
                    "column": col_index,
                    "criteriaType": str(condition.get("type", "CUSTOM")),
                    "hiddenValues": (v or {}).get("hiddenValues", []) or [],
                    "criteriaValues": condition.get("values", []) or [],
                }
            )

    view_items = []
    for fv in sheet.get("filterViews", []) or []:
        view_items.append(
            {
                "filterViewId": fv.get("filterViewId"),
                "title": fv.get("title", ""),
                "range": grid_range_to_a1(fv.get("range"), max_rows, max_cols),
                "criteriaColumns": list((fv.get("criteria", {}) or {}).keys()),
            }
        )

    return {
        "basicFilterActive": bool(basic),
        "range": grid_range_to_a1((basic or {}).get("range"), max_rows, max_cols) if basic else "",
        "criteria": criteria_items,
        "filterViews": view_items,
    }


def inspect_conditional_formatting(
    sheet: Dict[str, Any],
    max_rows: int,
    max_cols: int,
) -> Dict[str, Any]:
    rules = sheet.get("conditionalFormats", []) or []
    sample = []
    for rule in rules[:40]:
        ranges = [grid_range_to_a1(r, max_rows, max_cols) for r in (rule.get("ranges", []) or [])]
        if rule.get("booleanRule"):
            kind = "BOOLEAN"
            criteria_type = str(((rule.get("booleanRule", {}) or {}).get("condition", {}) or {}).get("type", ""))
        elif rule.get("gradientRule"):
            kind = "GRADIENT"
            criteria_type = ""
        else:
            kind = "UNKNOWN"
            criteria_type = ""
        sample.append({"ranges": ranges, "type": kind, "booleanCriteriaType": criteria_type})
    return {"totalRules": len(rules), "sample": sample}


def inspect_protections(
    sheet: Dict[str, Any],
    max_rows: int,
    max_cols: int,
) -> Dict[str, Any]:
    sheet_protections = []
    range_protections = []

    for pr in sheet.get("protectedRanges", []) or []:
        editors = pr.get("editors", {}) or {}
        users = [u.get("emailAddress", "") for u in (editors.get("users", []) or []) if u.get("emailAddress")]
        groups = [g for g in (editors.get("groups", []) or []) if g]
        unprotected = [
            grid_range_to_a1(rng, max_rows, max_cols) for rng in (pr.get("unprotectedRanges", []) or [])
        ]

        item = {
            "description": pr.get("description", ""),
            "range": grid_range_to_a1(pr.get("range"), max_rows, max_cols),
            "warningOnly": bool(pr.get("warningOnly", False)),
            "domainEdit": bool(editors.get("domainUsersCanEdit", False)),
            "editors": users,
            "groups": groups,
            "unprotectedRanges": unprotected,
        }

        if pr.get("range"):
            range_protections.append(item)
        else:
            sheet_protections.append(item)

    return {"sheetProtections": sheet_protections, "rangeProtections": range_protections}


def inspect_sheet(
    sheet: Dict[str, Any],
    preview_rows: int,
    preview_cols: int,
) -> Dict[str, Any]:
    props = sheet.get("properties", {}) or {}
    grid = props.get("gridProperties", {}) or {}
    lookup = get_sheet_cell_lookup(sheet)
    used = compute_used_range(sheet)

    structure = {
        "maxRows": int(grid.get("rowCount", 0)),
        "maxColumns": int(grid.get("columnCount", 0)),
        "frozenRows": int(grid.get("frozenRowCount", 0)),
        "frozenColumns": int(grid.get("frozenColumnCount", 0)),
        **used,
    }

    max_rows = max(1, structure["maxRows"])
    max_cols = max(1, structure["maxColumns"])

    return {
        "sheetName": props.get("title", ""),
        "sheetId": props.get("sheetId"),
        "isHidden": bool(props.get("hidden", False)),
        "structure": structure,
        "visibleDataAndFormulas": inspect_visible_data_and_formulas(
            lookup,
            structure["lastRow"],
            structure["lastColumn"],
            preview_rows,
            preview_cols,
        ),
        "formats": inspect_formats(
            lookup,
            structure["lastRow"],
            structure["lastColumn"],
            preview_rows,
            preview_cols,
        ),
        "mergedCells": inspect_merged_cells(sheet.get("merges"), max_rows, max_cols),
        "dataValidations": inspect_data_validations(
            lookup,
            structure["lastRow"],
            structure["lastColumn"],
        ),
        "filters": inspect_filters(sheet, max_rows, max_cols),
        "conditionalFormatting": inspect_conditional_formatting(sheet, max_rows, max_cols),
        "protections": inspect_protections(sheet, max_rows, max_cols),
    }


def inspect_workbook_permissions(
    spreadsheet_id: str,
    headers: Dict[str, str],
    timeout: int,
) -> Dict[str, Any]:
    url = f"https://www.googleapis.com/drive/v3/files/{spreadsheet_id}"
    params = {
        "fields": "id,name,owners(emailAddress),permissions(emailAddress,role,type,domain,allowFileDiscovery),shared,capabilities(canShare),writersCanShare",
        "supportsAllDrives": "true",
    }
    response = requests.get(url, headers=headers, params=params, timeout=timeout)
    if response.status_code >= 400:
        return {"error": f"Drive API error {response.status_code}: {response.text[:300]}"}

    payload = response.json()
    owners = [o.get("emailAddress", "") for o in (payload.get("owners", []) or []) if o.get("emailAddress")]
    editors = []
    viewers = []
    commenters = []
    for p in payload.get("permissions", []) or []:
        role = p.get("role", "")
        email = p.get("emailAddress") or p.get("domain") or p.get("type", "")
        if role in ("owner", "organizer", "fileOrganizer", "writer"):
            editors.append(email)
        elif role == "commenter":
            commenters.append(email)
        elif role == "reader":
            viewers.append(email)

    return {
        "owner": owners[0] if owners else "",
        "owners": owners,
        "editors": sorted(set(editors)),
        "commenters": sorted(set(commenters)),
        "viewers": sorted(set(viewers)),
        "shared": bool(payload.get("shared", False)),
        "canShare": bool((payload.get("capabilities", {}) or {}).get("canShare", False)),
        "writersCanShare": bool(payload.get("writersCanShare", False)),
    }


def collect_filter_views(report_sheets: List[Dict[str, Any]]) -> Dict[str, Any]:
    items = []
    for sheet in report_sheets:
        for fv in sheet.get("filters", {}).get("filterViews", []) or []:
            items.append(
                {
                    "sheetId": sheet.get("sheetId"),
                    "sheetTitle": sheet.get("sheetName"),
                    "filterViewId": fv.get("filterViewId"),
                    "title": fv.get("title", ""),
                    "range": fv.get("range", ""),
                    "criteriaColumns": fv.get("criteriaColumns", []),
                }
            )
    return {"available": True, "total": len(items), "items": items}


def get_spreadsheet_payload(
    spreadsheet_id: str,
    headers: Dict[str, str],
    timeout: int,
) -> Dict[str, Any]:
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
    params = {
        "includeGridData": "true",
        "fields": "spreadsheetId,properties,sheets(properties,data,merges,basicFilter,filterViews,conditionalFormats,protectedRanges)",
    }
    response = requests.get(url, headers=headers, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def build_markdown_report(report: Dict[str, Any], spreadsheet_url: str) -> str:
    lines = []
    lines.append(f"# INSPECCION HOJA CENTRAL - {datetime.now(timezone.utc).date()}")
    lines.append("")
    lines.append("Fuente inspeccionada:")
    lines.append(f"- URL: `{spreadsheet_url}`")
    lines.append("- Metodo: Google Sheets API + Drive API (service account)")
    lines.append("")
    lines.append("## 1) Estructura completa")
    lines.append(f"- Libro: `{report.get('spreadsheetName', '')}`")
    lines.append(f"- Spreadsheet ID: `{report.get('spreadsheetId', '')}`")
    lines.append(f"- Zona horaria: `{report.get('timeZone', '')}`")
    lines.append(f"- Locale: `{report.get('locale', '')}`")
    lines.append(f"- Pestanas: {len(report.get('sheets', []))}")
    for sheet in report.get("sheets", []):
        st = sheet.get("structure", {})
        lines.append(
            f"- Hoja `{sheet.get('sheetName', '')}`: rango usado `{st.get('usedRangeA1', '') or '(vacio)'}`, filas usadas `{st.get('usedRows', 0)}`, columnas usadas `{st.get('usedColumns', 0)}`."
        )
    lines.append("")
    lines.append("## 2) Datos visibles y formulas")
    for sheet in report.get("sheets", []):
        vdf = sheet.get("visibleDataAndFormulas", {})
        lines.append(
            f"- Hoja `{sheet.get('sheetName', '')}`: preview `{vdf.get('previewRows', 0)}x{vdf.get('previewColumns', 0)}`, tiene datos: `{vdf.get('hasData', False)}`."
        )
    lines.append("")
    lines.append("## 3) Formatos aplicados")
    for sheet in report.get("sheets", []):
        fmt = sheet.get("formats", {})
        borders = ((fmt.get("summary", {}) or {}).get("cellsWithBorderCount", 0) if fmt else 0)
        lines.append(
            f"- Hoja `{sheet.get('sheetName', '')}`: preview formato `{fmt.get('previewRows', 0)}x{fmt.get('previewColumns', 0)}`, celdas con borde `{borders}`."
        )
    lines.append("")
    lines.append("## 4) Celdas combinadas")
    for sheet in report.get("sheets", []):
        mc = sheet.get("mergedCells", {})
        lines.append(f"- Hoja `{sheet.get('sheetName', '')}`: combinadas `{mc.get('total', 0)}`.")
    lines.append("")
    lines.append("## 5) Validaciones y desplegables")
    for sheet in report.get("sheets", []):
        dv = sheet.get("dataValidations", {})
        lines.append(
            f"- Hoja `{sheet.get('sheetName', '')}`: celdas con validacion `{dv.get('totalCellsWithValidation', 0)}`."
        )
    lines.append("")
    lines.append("## 6) Filtros y vistas de filtro")
    fv = report.get("filterViews", {})
    lines.append(f"- Vistas de filtro (total libro): `{fv.get('total', 0)}`.")
    for sheet in report.get("sheets", []):
        flt = sheet.get("filters", {})
        lines.append(
            f"- Hoja `{sheet.get('sheetName', '')}`: filtro basico activo `{flt.get('basicFilterActive', False)}`, vistas `{len(flt.get('filterViews', []))}`."
        )
    lines.append("")
    lines.append("## 7) Formato condicional")
    for sheet in report.get("sheets", []):
        cf = sheet.get("conditionalFormatting", {})
        lines.append(f"- Hoja `{sheet.get('sheetName', '')}`: reglas `{cf.get('totalRules', 0)}`.")
    lines.append("")
    lines.append("## 8) Protecciones y permisos")
    perms = report.get("workbookPermissions", {})
    lines.append(f"- Owner: `{perms.get('owner', '')}`")
    lines.append(f"- Editores detectados: `{len(perms.get('editors', []))}`")
    lines.append(f"- Lectores detectados: `{len(perms.get('viewers', []))}`")
    lines.append(f"- Comentadores detectados: `{len(perms.get('commenters', []))}`")
    for sheet in report.get("sheets", []):
        prot = sheet.get("protections", {})
        lines.append(
            f"- Hoja `{sheet.get('sheetName', '')}`: protecciones hoja `{len(prot.get('sheetProtections', []))}`, protecciones rango `{len(prot.get('rangeProtections', []))}`."
        )
    lines.append("")
    lines.append("## Nota tecnica")
    lines.append("- El detalle completo por celda, reglas y permisos esta en el JSON de auditoria generado.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()

    sheets_headers = auth_headers(
        args.service_account,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    drive_headers = auth_headers(
        args.service_account,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )

    started = datetime.now(timezone.utc).isoformat()
    report: Dict[str, Any] = {
        "generatedAt": started,
        "scope": str(args.scope),
        "spreadsheetId": args.spreadsheet_id,
        "spreadsheetName": "",
        "timeZone": "",
        "locale": "",
        "workbookPermissions": {},
        "sheets": [],
        "filterViews": {"available": True, "total": 0, "items": []},
        "errors": [],
    }

    try:
        payload = get_spreadsheet_payload(args.spreadsheet_id, sheets_headers, args.timeout)
        report["spreadsheetName"] = (payload.get("properties", {}) or {}).get("title", "")
        report["timeZone"] = (payload.get("properties", {}) or {}).get("timeZone", "")
        report["locale"] = (payload.get("properties", {}) or {}).get("locale", "")

        for sheet in payload.get("sheets", []) or []:
            try:
                report["sheets"].append(
                    inspect_sheet(
                        sheet,
                        preview_rows=max(1, args.preview_rows),
                        preview_cols=max(1, args.preview_cols),
                    )
                )
            except Exception as err:  # noqa: BLE001
                report["errors"].append(
                    {
                        "sheetName": (sheet.get("properties", {}) or {}).get("title", ""),
                        "error": str(err),
                    }
                )
    except Exception as err:  # noqa: BLE001
        report["errors"].append({"sheetName": "", "error": f"Sheets API error: {err}"})

    report["workbookPermissions"] = inspect_workbook_permissions(
        args.spreadsheet_id,
        drive_headers,
        args.timeout,
    )
    report["filterViews"] = collect_filter_views(report.get("sheets", []))
    report["completedAt"] = datetime.now(timezone.utc).isoformat()

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")

    if args.out_md:
        out_md = Path(args.out_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(
            build_markdown_report(
                report,
                f"https://docs.google.com/spreadsheets/d/{args.spreadsheet_id}/edit",
            ),
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "ok": True,
                "spreadsheetId": args.spreadsheet_id,
                "spreadsheetName": report.get("spreadsheetName", ""),
                "sheets": len(report.get("sheets", [])),
                "errors": len(report.get("errors", [])),
                "outJson": str(out_json),
                "outMd": str(args.out_md or ""),
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
