# ARCHITECTURE

## Resumen
`APP_ARTES-BUHO_CRM-CENTRAL` centraliza busqueda y actualizacion de contactos entre varios CRM en Google Sheets.

## Marca
- Empresa: `ARTES BURO`
- Desarrollador: `RUBEN COTTON`
- Paleta: amarillo, rojo y blanco.

## Capas
1. Capa de datos (Google Sheets)
   - `FUENTES`
   - `RESULTADOS`
   - `LOG`
   - `IA_LOCAL_COLA`
   - `AUDITORIA_HOJA`
2. Capa de servicios (Apps Script)
   - `SourceRegistryService.gs`
   - `ContactSearchService.gs`
   - `LocalAiQueueService.gs`
   - `SpreadsheetAuditService.gs`
   - `Api.gs`
3. Capa de interfaz (HTMLService)
   - `App.html`
   - `Styles.html`
   - `Client.html`
   - `BrandLogo.html`

## Flujo principal
1. Registrar fuentes CRM (ID hoja + pestana + cabeceras).
   - opcion de sincronizar todas las pestañas del archivo.
2. Buscar contacto desde UI.
3. Motor fuzzy puntua coincidencias.
4. Mostrar resultados ordenados por score.
5. Seleccionar resultado.
6. Editar y guardar contacto en hoja origen.

## IA local unica
- Modo fijo: `LOCAL_ONLY`.
- Si no esta disponible:
  - tarea a cola `IA_LOCAL_COLA`
  - reintentos por tiempo
- No hay duplicacion de motores IA en esta arquitectura.

## Auditoria de hojas
- `runCentralSpreadsheetAudit` inspecciona:
  - estructura
  - datos/formulas
  - formatos
  - combinadas
  - validaciones
  - filtros
  - formato condicional
  - protecciones/permisos
- Resultado en `AUDITORIA_HOJA`.
