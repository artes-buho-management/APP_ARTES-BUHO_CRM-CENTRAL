# OPERACION REMOTA DE CONTACTOS

## Objetivo
- Buscar contactos en todos los CRM conectados.
- Actualizar contacto en hoja origen.
- Todo por API, sin depender de desplegar Web App.

## Script
- `scripts/remote_contact_ops.py`

## Requisitos
- Service account con acceso a:
  - hoja central
  - hojas CRM origen
- Python con `requests` y `google-auth`

## 1) Buscar contacto (y guardar en RESULTADOS)

```bash
python scripts/remote_contact_ops.py search ^
  --service-account "C:\ruta\service-account.json" ^
  --central-id "REPLACE_WITH_SHEET_ID" ^
  --term "trato producciones" ^
  --max-results 10 ^
  --out-json "reports/search_runs/2026-04-07-trato-producciones.json"
```

Resultado:
- Lee `FUENTES` activas.
- Busca por similitud (incluye tolerancia de escritura).
- Escribe top resultados en `RESULTADOS`.

## 2) Buscar sin escribir en RESULTADOS

```bash
python scripts/remote_contact_ops.py search ^
  --service-account "C:\ruta\service-account.json" ^
  --term "javiera" ^
  --no-write-results
```

## 3) Actualizar contacto (simulacion segura)

```bash
python scripts/remote_contact_ops.py update ^
  --service-account "C:\ruta\service-account.json" ^
  --spreadsheet-id "REPLACE_WITH_SHEET_ID" ^
  --sheet-name "MANAGEMENT" ^
  --row-number 390 ^
  --phone "+34-963393650" ^
  --dry-run
```

Resultado:
- No escribe cambios.
- Devuelve exactamente la celda que tocaria.

## 4) Actualizar contacto real

```bash
python scripts/remote_contact_ops.py update ^
  --service-account "C:\ruta\service-account.json" ^
  --spreadsheet-id "REPLACE_WITH_SHEET_ID" ^
  --sheet-name "MANAGEMENT" ^
  --row-number 390 ^
  --phone "+34 6XX XXX XXX"
```

Resultado:
- Escribe directamente en la fila origen.

## Nota
- El bloqueo OAuth `invalid_rapt` afecta al despliegue `clasp`.
- Este operador remoto evita ese bloqueo para busqueda/edicion diaria.
