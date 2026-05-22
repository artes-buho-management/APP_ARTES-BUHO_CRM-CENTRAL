# AGENTS.md

## Contexto del proyecto
- Proyecto: `APP_ARTES-BUHO_CRM-CENTRAL`.
- Objetivo: buscar y localizar contactos entre varios CRM en Google Sheets.

## Reglas de colaboracion
1. Mantener codigo simple y legible.
2. Evitar dependencias innecesarias.
3. Documentar cada cambio en `CHANGELOG.md`.
4. Proteger los datos: no exponer IDs o informacion sensible en commits.
5. Antes de tocar logica de hojas, validar estructura de origen y destino.

## Flujo recomendado
1. Crear rama para cada cambio.
2. Hacer cambios pequenos y verificables.
3. Probar manualmente:
   - inicializacion
   - registro de fuente
   - busqueda
4. Actualizar README/docs cuando cambie comportamiento.
