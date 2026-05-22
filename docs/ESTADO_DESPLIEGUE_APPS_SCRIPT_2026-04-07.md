# ESTADO DESPLIEGUE APPS SCRIPT - 2026-04-07

## Resultado
- Despliegue automatico bloqueado por seguridad de Google OAuth.
- Error devuelto por `clasp`:
  - `invalid_grant`
  - `invalid_rapt`

## Que significa
- La cuenta Google necesita reautenticacion reforzada.
- Sin esa reautenticacion, Google no permite:
  - listar deployments
  - crear deployment nuevo
  - ejecutar funciones remotas por Execution API

## Estado remoto confirmado (si operativo)
- Conexion central activa:
  - Spreadsheet central: `1gNg71eDZefbx_8leQ8ij7pOaBXdsWIFnNK_QhXjv8W0`
  - Fuentes cargadas: `87`
  - Errores de fuente: `0`
- Auditoria central completa por API generada:
  - `reports/central_sheet_inspection.json`
  - `docs/INSPECCION_HOJA_CENTRAL_2026-04-07.md`

## Siguiente desbloqueo tecnico (minimo)
- Reautenticar `clasp` con la cuenta propietaria del script.
- Tras eso, el despliegue web app se completa en remoto en segundos.
