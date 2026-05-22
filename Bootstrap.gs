function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("Central Contactos")
    .addItem("Inicializar estructura", "initializeCentralContacts")
    .addSeparator()
    .addItem("Auditar hoja central", "runCentralSpreadsheetAudit")
    .addItem("Auditar 7 CRM base", "runProvidedCrmsAudit")
    .addSeparator()
    .addItem("IA local disponible", "setLocalAiAvailable")
    .addItem("IA local en espera", "setLocalAiUnavailable")
    .addItem("Procesar cola IA", "processPendingLocalAiTasks")
    .addSeparator()
    .addItem("Sincronizar 7 CRM base", "syncProvidedCrmsCatalog")
    .addSeparator()
    .addItem("Recargar fuentes", "apiGetSources")
    .addToUi();
}

function initializeCentralContacts() {
  var ss = getCentralSpreadsheet_();

  ensureSheetWithHeaders_(ss, CC_CONFIG.SHEETS.SOURCES, CC_CONFIG.SOURCE_HEADERS);
  ensureSheetWithHeaders_(ss, CC_CONFIG.SHEETS.RESULTS, CC_CONFIG.RESULT_HEADERS);
  ensureSheetWithHeaders_(ss, CC_CONFIG.SHEETS.LOG, CC_CONFIG.LOG_HEADERS);
  ensureSheetWithHeaders_(ss, CC_CONFIG.SHEETS.AI_QUEUE, getLocalAiQueueHeaders_());
  ensureSheetWithHeaders_(ss, CC_CONFIG.SHEETS.AUDIT, getAuditHeaders_());

  appendLog_("INFO", "Estructura inicializada", { spreadsheetId: ss.getId() });
  showToast_("Estructura lista", "Proyecto inicializado correctamente.");
}

function ensureSheetWithHeaders_(spreadsheet, sheetName, headers) {
  var sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(sheetName);
  }

  var current = sheet.getRange(1, 1, 1, headers.length).getDisplayValues()[0];
  if (!headersMatch_(current, headers)) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  }

  sheet.setFrozenRows(1);
}

function headersMatch_(left, right) {
  if (!left || !right || left.length < right.length) {
    return false;
  }

  for (var i = 0; i < right.length; i++) {
    if (String(left[i] || "").trim() !== String(right[i] || "").trim()) {
      return false;
    }
  }

  return true;
}

function showToast_(title, message) {
  try {
    getCentralSpreadsheet_().toast(message, title, 5);
  } catch (error) {
    // Si no hay contexto UI visible, ignoramos el toast.
  }
}
