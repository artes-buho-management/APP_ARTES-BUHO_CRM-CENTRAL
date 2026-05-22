# COLA IA LOCAL REMOTA

## Objetivo
- Procesar tareas en `IA_LOCAL_COLA` sin interfaz manual.
- Mantener estado y reintentos.
- Respetar regla:
  - si IA local no esta disponible, la tarea queda en espera.

## Script
- `scripts/ia_local_queue_worker.py`

## Tipos de tarea soportados
- `CONTACT_SEARCH`
- `CONTACT_UPDATE`
- `PARSE_UPDATE_MESSAGE`

## Estados
- `PENDING`
- `PROCESSING`
- `DONE`
- `RETRY`
- `WAITING_AI`
- `FAILED`

## 1) Encolar busqueda

```bash
python scripts/ia_local_queue_worker.py enqueue-search ^
  --service-account "C:\ruta\service-account.json" ^
  --term "trato producciones" ^
  --max-results 5
```

## 2) Encolar actualizacion

```bash
python scripts/ia_local_queue_worker.py enqueue-update ^
  --service-account "C:\ruta\service-account.json" ^
  --spreadsheet-id "REPLACE_WITH_SHEET_ID" ^
  --sheet-name "MANAGEMENT" ^
  --row-number 390 ^
  --phone "+34-963393650" ^
  --dry-run
```

## 3) Encolar parseo de mensaje

```bash
python scripts/ia_local_queue_worker.py enqueue-parse-message ^
  --service-account "C:\ruta\service-account.json" ^
  --message "Actualizar contacto Tratos Producciones telefono +34 6XX XXX XXX"
```

## 4) Ejecutar cola una vez

```bash
python scripts/ia_local_queue_worker.py run-once ^
  --service-account "C:\ruta\service-account.json" ^
  --max-tasks 10 ^
  --retry-minutes 3
```

## 5) Ejecutar cola en bucle

```bash
python scripts/ia_local_queue_worker.py run-loop ^
  --service-account "C:\ruta\service-account.json" ^
  --interval-seconds 30 ^
  --max-cycles 0
```

## IA local
- Si quieres parseo con IA local real:
  - usar `--ai-endpoint "http://127.0.0.1:PORT/..."`
- Si IA local no responde:
  - `PARSE_UPDATE_MESSAGE` pasa a `WAITING_AI`
  - se programa `NEXT_RETRY_AT`

## Resultado operativo
- `CONTACT_SEARCH`:
  - escribe top resultados en `RESULTADOS`
  - guarda detalle JSON en `RESULT_JSON`
- `CONTACT_UPDATE`:
  - actualiza fila origen (o simula con `dry-run`)
  - deja rastro en `RESULT_JSON`
