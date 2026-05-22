$ErrorActionPreference = 'Stop'

$repo = "C:\Users\elrub\Desktop\CARPETA CODEX\APP_ARTES-BUHO_CRM-CENTRAL"
$serviceAccount = "C:\Users\elrub\Desktop\CARPETA CODEX\secrets\robot-codex-key-20260308-220232.json"
$spreadsheetId = "REPLACE_WITH_ID"

Set-Location -LiteralPath $repo
python "scripts/operate_sheet_bridge.py" run-once --service-account $serviceAccount --central-id $spreadsheetId
