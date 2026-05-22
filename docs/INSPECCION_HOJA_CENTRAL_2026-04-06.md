# INSPECCION HOJA CENTRAL - 2026-04-06

Fuente inspeccionada:
- URL: `https://docs.google.com/spreadsheets/d/REPLACE_WITH_SHEET_ID/edit`
- Metodo: exportacion XLSX + analisis tecnico con `parse_xlsx.py`
- Reporte JSON: `reports/central_sheet_inspection.json`

## 1) Estructura completa
- Libro: 1 hoja.
- Hoja: `Hoja 1`.
- Estado: visible.
- Rango usado: `A1:A1`.
- Filas maximas detectadas: 1.
- Columnas maximas detectadas: 1.

## 2) Datos visibles y formulas
- Celdas no vacias: 0.
- Preview de datos: sin filas con contenido.
- Formulas detectadas: 0.

## 3) Formatos aplicados
- Sin formatos relevantes detectados sobre celdas con contenido.
- Sin bordes detectados.
- Sin anchos/altos personalizados.

## 4) Celdas combinadas
- Total combinadas: 0.

## 5) Validaciones y desplegables
- Total validaciones: 0.

## 6) Filtros y vistas de filtro
- Filtro basico: no activo.
- Vistas de filtro: no detectables de forma fiable en export XLSX.

## 7) Formato condicional
- Reglas detectadas: 0.

## 8) Protecciones y permisos
- Proteccion de hoja: desactivada.
- Permisos de archivo (editores/lectores): no disponibles en export XLSX.

## Limitaciones tecnicas
- El export XLSX no expone permisos completos de Google Sheets.
- Las vistas de filtro pueden no exportarse 1:1.
- Las protecciones de rango pueden no exportarse 1:1.

## Paso tecnico recomendado para cierre 100%
- Ejecutar en Apps Script: `runCentralSpreadsheetAudit()`.
- Esto completa filtro-vistas y permisos con APIs nativas.
