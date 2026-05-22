# APP_ARTES-BUHO_CRM-CENTRAL

Buscador y actualizador de contactos para multiples CRM en Google Sheets.

## Datos corporativos
- Empresa: `ARTES BURO`
- Desarrollador: `RUBEN COTTON`
- Colores corporativos:
  - Amarillo: `#FFD23F`
  - Rojo: `#D62828`
  - Blanco: `#FFFFFF`

## Hoja central del proyecto
- URL: `https://docs.google.com/spreadsheets/d/REPLACE_WITH_SHEET_ID/edit`
- Spreadsheet ID: `1gNg71eDZefbx_8leQ8ij7pOaBXdsWIFnNK_QhXjv8W0`
- Estado: fijada por configuracion en `Config.gs`.

## Objetivo
- Buscar contactos entre muchos CRM sin abrir archivo por archivo.
- Encontrar resultados aunque haya errores de escritura.
- Actualizar el contacto directamente en su hoja origen.

## Stack
- Google Apps Script (V8)
- Google Sheets
- HTMLService
- Git + GitHub

## Funcionalidades clave
- Busqueda central multi-CRM.
- Match inteligente:
  - texto parcial
  - similitud por distancia de edicion
  - tolerancia de variaciones de vocales
  - prioridad por email y telefono
- Actualizacion directa de contacto en hoja origen.
- Registro de fuentes CRM configurable por cabeceras.
- Sincronizacion masiva de pestaÃ±as por CRM.
- Carga directa del catalogo inicial de 7 CRM proporcionados.
- IA local unica con cola:
  - modo `LOCAL_ONLY`
  - en espera si no esta disponible
  - reintento automatico
- Auditoria completa de hoja:
  - estructura
  - datos y formulas
  - formatos
  - combinadas
  - validaciones
  - filtros y vistas de filtro
  - formato condicional
  - protecciones y permisos

## Estructura

```text
APP_ARTES-BUHO_CRM-CENTRAL/
  README.md
  CHANGELOG.md
  AGENTS.md
  .gitignore
  .claspignore
  .clasp.json.example
  appsscript.json
  Code.gs
  Config.gs
  Bootstrap.gs
  SourceRegistryService.gs
  ContactSearchService.gs
  LocalAiQueueService.gs
  SpreadsheetAuditService.gs
  Api.gs
  Index.html
  App.html
  Styles.html
  Client.html
  BrandLogo.html
  docs/
    ARCHITECTURE.md
    DEPLOY.md
    DATA_MODEL.md
  PROMPTS/
    NEXT_STEPS.md
  .github/
    pull_request_template.md
    ISSUE_TEMPLATE/
      bug_report.md
      feature_request.md
```

## Hojas internas creadas por el sistema
- `GUIA`
- `OPERAR`
- `FUENTES`
- `RESULTADOS`
- `LOG`
- `IA_LOCAL_COLA`
- `AUDITORIA_HOJA`

## Puesta en marcha rapida
1. Copia `.clasp.json.example` a `.clasp.json`.
2. Completa `scriptId`.
3. Ejecuta `clasp push`.
4. Ejecuta `initializeCentralContacts`.
5. Ejecuta `runCentralSpreadsheetAudit`.
6. Registra fuentes en `FUENTES`.

## Evidencia de inspeccion inicial
- Resumen: `docs/INSPECCION_HOJA_CENTRAL_2026-04-06.md`
- Resumen actualizado remoto: `docs/INSPECCION_HOJA_CENTRAL_2026-04-07.md`
- Reporte tecnico: `reports/central_sheet_inspection.json`
- Inspeccion CRM masiva: `docs/INSPECCION_CRM_2026-04-06.md`
- Inspeccion CRM masiva actualizada: `docs/INSPECCION_CRM_2026-04-07.md`
- Resumen tecnico CRM: `reports/crm_inspection/2026-04-06/crm_summary.json`
- Resumen tecnico CRM actualizado: `reports/crm_inspection/2026-04-07/crm_summary_live.json`
- Estado de conexion remota: `docs/ESTADO_CONEXION_REMOTA_2026-04-06.md`
- Estado despliegue Apps Script: `docs/ESTADO_DESPLIEGUE_APPS_SCRIPT_2026-04-07.md`
- Estado despliegue Apps Script actualizado: `docs/ESTADO_DESPLIEGUE_APPS_SCRIPT_2026-04-08.md`

## Setup remoto reutilizable
- Script: `scripts/setup_remote_central.py`
- Ejecuta conexion + carga de auditoria en hoja central sin pasos manuales en UI.
- Auditoria profunda por API: `scripts/audit_google_sheet_full.py`
- Auditoria completa lote 7 CRM: `scripts/audit_provided_crms_full.py`
- Operador remoto de contactos: `scripts/remote_contact_ops.py`
  - busqueda multi-CRM por API
  - escritura de top resultados en `RESULTADOS`
  - actualizacion directa en fila origen
- Worker de cola IA local remota: `scripts/ia_local_queue_worker.py`
  - procesa `IA_LOCAL_COLA`
  - estados `PENDING/PROCESSING/DONE/RETRY/WAITING_AI/FAILED`
  - espera automatica cuando IA local no esta disponible
- Organizador visual hoja central: `scripts/organize_central_sheet_branding.py`
  - elimina hoja vacia innecesaria
  - ordena pestaÃ±as
  - aplica estilo corporativo rojo/amarillo/blanco
  - crea pestaÃ±a `GUIA` con uso rapido

## Operativa remota diaria
- Guia: `docs/OPERACION_REMOTA_CONTACTOS.md`
- Guia cola IA local: `docs/COLA_IA_LOCAL_REMOTA.md`

## Operar desde hoja (sin chat)
- Todo se hace en la pestana `OPERAR` de la hoja central.
- No necesitas tocar Apps Script para el trabajo diario.

### Buscar contacto en todos los CRM
1. Escribe el texto en `OPERAR!B4` (nombre, telefono o email).
2. Define limite en `OPERAR!B5` (ejemplo: `20`).
3. Pon `TRUE` en `OPERAR!B6`.
4. Espera 5-60 segundos y revisa `RESULTADOS`.
5. Estado tecnico en `OPERAR!B7` y `OPERAR!B8`.

### Actualizar contacto encontrado
1. Pon la fila de `RESULTADOS` en `OPERAR!B11` (ejemplo: `2`).
2. Completa solo los campos a cambiar en `B12:B16`.
3. Recomendado: deja `OPERAR!B17 = TRUE` para prueba sin escribir.
4. Pon `TRUE` en `OPERAR!B18` para ejecutar.
5. Revisa estado en `OPERAR!B19` y detalle JSON en `OPERAR!B20`.

### Automatizacion activa
- Tarea programada: `CRM_CENTRAL_OPERAR_BRIDGE`.
- Frecuencia: cada `1` minuto.
- Modo: oculto (`WindowStyle Hidden`).
- Ultimo resultado correcto: `0` (ejecucion OK).

## Inspecciones de organizacion (2026-04-08)
- Pre: `docs/INSPECCION_HOJA_CENTRAL_PRE_ORGANIZE_2026-04-08.md`
- Post: `docs/INSPECCION_HOJA_CENTRAL_POST_ORGANIZE_2026-04-08.md`
- Final: `docs/INSPECCION_HOJA_CENTRAL_FINAL_ORGANIZE_2026-04-08.md`

## API interna (Apps Script)
- `apiSearchContacts({ term, maxResults })`
- `apiUpdateContact({ spreadsheetId, sheetName, rowNumber, ...campos })`
- `apiRegisterSource(source)`
- `apiSyncSourceTabs(sourceBase)`
- `apiSyncProvidedCrmsCatalog()`
- `apiGetSources()`
- `apiGetPublicConfig()`
- `apiRunCentralAudit()`
- `apiRunProvidedCrmsAudit()`

## CIERRE MIGRACION CLOUD

- Fecha: 2026-04-08
- Estado: preparado para retomar desde nuevo sistema


## CIERRE CLOUD 2026-04-08
- Estado: sincronizado para migracion a nuevo PC/sistema.
- Preparado para retomar desde GitHub.
- Ultima revision: 2026-04-08 15:26:05 +02:00

<!-- MIGRACION_CLOUD_START -->
## ESTADO MIGRACION CLOUD
- Revisado: 2026-04-08
- Repo listo para continuar en otro sistema.
- Estado Git al cerrar: sincronizado en GitHub.
<!-- MIGRACION_CLOUD_END -->
