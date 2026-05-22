# DEPLOY

## Requisitos
- Cuenta Google con acceso a las hojas CRM.
- `clasp` instalado.
- Script ID creado en Apps Script.
- Acceso de edicion a la hoja central:
  - `https://docs.google.com/spreadsheets/d/REPLACE_WITH_SHEET_ID/edit`

## Pasos
1. Clonar repo.
2. Crear `.clasp.json` desde `.clasp.json.example`.
3. Poner `scriptId` real.
4. Subir codigo:
   - `clasp push`
5. Abrir proyecto Apps Script y revisar permisos.
6. (Opcional recomendado) Activar servicio avanzado `Google Sheets API`.
7. Ejecutar:
   - `initializeCentralContacts`
8. Ejecutar auditoria inicial:
   - `runCentralSpreadsheetAudit`
   - `runProvidedCrmsAudit`
9. Definir estado IA local:
   - `setLocalAiAvailable` o `setLocalAiUnavailable`

## Despliegue web app
1. Apps Script -> `Deploy` -> `New deployment`.
2. Tipo: `Web app`.
3. Ejecutar como: `Me`.
4. Acceso: segun necesidad.
5. Guardar URL de despliegue.

## Checklist de validacion
- [ ] Se crean hojas `FUENTES`, `RESULTADOS`, `LOG`, `IA_LOCAL_COLA`, `AUDITORIA_HOJA`.
- [ ] Se puede guardar fuente.
- [ ] Se puede buscar y ver resultados.
- [ ] Se puede editar y guardar contacto en hoja origen.
- [ ] `LOG` guarda errores si una fuente falla.
- [ ] `AUDITORIA_HOJA` recibe inspeccion completa.
