# DATA_MODEL

## Hoja: FUENTES
Cabeceras:
1. `ACTIVO`
2. `ALIAS`
3. `SPREADSHEET_ID`
4. `HOJA`
5. `HEADER_ROW`
6. `CAMPO_NOMBRE`
7. `CAMPO_EMAIL`
8. `CAMPO_TELEFONO`
9. `CAMPO_ID`
10. `CAMPO_NOTAS`

Uso:
- Configurar origenes CRM.

## Hoja: RESULTADOS
Cabeceras:
1. `FECHA_BUSQUEDA`
2. `TERMINO`
3. `SCORE`
4. `ORIGEN_ALIAS`
5. `SPREADSHEET_ID`
6. `HOJA`
7. `FILA_ORIGEN`
8. `MATCH_EN`
9. `CONTACT_ID`
10. `NOMBRE`
11. `EMAIL`
12. `TELEFONO`
13. `NOTAS`

Uso:
- Historial de busquedas y ranking de coincidencias.

## Hoja: LOG
Cabeceras:
1. `FECHA`
2. `NIVEL`
3. `MENSAJE`
4. `DETALLE_JSON`

Uso:
- Eventos y errores.

## Hoja: IA_LOCAL_COLA
Cabeceras:
1. `CREATED_AT`
2. `TASK_TYPE`
3. `STATUS`
4. `PAYLOAD_JSON`
5. `RESULT_JSON`
6. `LAST_ERROR`
7. `NEXT_RETRY_AT`
8. `ATTEMPTS`

Uso:
- Cola unica para tareas de IA local.

## Hoja: AUDITORIA_HOJA
Cabeceras:
1. `FECHA`
2. `ALCANCE`
3. `SPREADSHEET_ID`
4. `SHEET`
5. `SECCION`
6. `DETALLE_JSON`

Uso:
- Resultado estructurado de inspecciones completas.
