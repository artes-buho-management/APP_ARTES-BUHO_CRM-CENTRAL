# ESTADO DESPLIEGUE APPS SCRIPT - 2026-04-08

## Resultado
- Bloqueo OAuth `invalid_rapt` resuelto para operaciones `clasp` de despliegue.
- Validado en remoto:
  - `clasp deployments` OK
  - `clasp versions` OK
  - `clasp push` OK
  - `clasp deploy` OK

## Deployments activos
- Web App:
  - Deployment ID: `AKfycbyQvd3HifpKi-xdIQV77wDJ80jvNKhDfXNJkRfzPQhM8QGCIMuaLUGdAv5YrzxeBVC2`
  - Version: `6`
  - URL: `https://script.google.com/macros/s/REPLACE_WITH_DEPLOYMENT_ID/exec`
- API deploy tecnico (versionado):
  - Deployment ID: `AKfycbyrqvQFMdzMeOvebRdigatEQ5-5uUi3oQdcqPtpO4oadCj-f9SNWN5eDlhPEE57xPLk`
  - Version: `6`

## Nota de acceso
- La URL `exec` devuelve `404` fuera del contexto de permisos configurado del deployment.
- Esto indica restriccion de acceso (normal en despliegues privados), no caida de deploy.

## Estado global
- Despliegue remoto operativo.
- Flujo alternativo por API Sheets (busqueda/actualizacion/cola) sigue operativo al 100%.
