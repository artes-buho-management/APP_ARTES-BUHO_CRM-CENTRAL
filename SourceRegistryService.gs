function registerSource(source) {
  var normalized = normalizeSourcePayload_(source || {});
  validateSourcePayload_(normalized);

  var sheet = getRequiredSheet_(CC_CONFIG.SHEETS.SOURCES);
  var targetRow = findSourceRow_(sheet, normalized.alias, normalized.spreadsheetId, normalized.hoja);
  var rowData = buildSourceRow_(normalized);

  if (targetRow > 0) {
    sheet.getRange(targetRow, 1, 1, rowData.length).setValues([rowData]);
  } else {
    sheet.appendRow(rowData);
    targetRow = sheet.getLastRow();
  }

  appendLog_("INFO", "Fuente registrada", {
    alias: normalized.alias,
    spreadsheetId: normalized.spreadsheetId,
    hoja: normalized.hoja,
    row: targetRow,
  });

  return {
    ok: true,
    row: targetRow,
    source: normalized,
  };
}

function syncSourceTabs(sourceBase) {
  var normalized = normalizeSourcePayload_(sourceBase || {});
  if (!normalized.alias) {
    throw new Error("Para sincronizar pestañas necesitas ALIAS.");
  }
  if (!normalized.spreadsheetId) {
    throw new Error("Para sincronizar pestañas necesitas SPREADSHEET_ID.");
  }

  var spreadsheet = SpreadsheetApp.openById(normalized.spreadsheetId);
  var tabs = spreadsheet.getSheets();
  var synced = 0;
  var tabNames = [];

  for (var i = 0; i < tabs.length; i++) {
    var tab = tabs[i];
    if (tab.isSheetHidden()) {
      continue;
    }

    var payload = {
      activo: normalized.activo,
      alias: normalized.alias,
      spreadsheetId: normalized.spreadsheetId,
      hoja: tab.getName(),
      headerRow: normalized.headerRow,
      campoNombre: normalized.campoNombre,
      campoEmail: normalized.campoEmail,
      campoTelefono: normalized.campoTelefono,
      campoId: normalized.campoId,
      campoNotas: normalized.campoNotas,
    };
    registerSource(payload);
    synced++;
    tabNames.push(tab.getName());
  }

  appendLog_("INFO", "Sincronizacion de pestañas completada", {
    alias: normalized.alias,
    spreadsheetId: normalized.spreadsheetId,
    synced: synced,
    tabs: tabNames,
  });

  return {
    ok: true,
    synced: synced,
    tabs: tabNames,
  };
}

function getSources() {
  var sheet = getRequiredSheet_(CC_CONFIG.SHEETS.SOURCES);
  var lastRow = sheet.getLastRow();

  if (lastRow <= 1) {
    return [];
  }

  var rows = sheet.getRange(2, 1, lastRow - 1, CC_CONFIG.SOURCE_HEADERS.length).getValues();
  var sources = [];

  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    if (!String(row[1] || "").trim() && !String(row[2] || "").trim()) {
      continue;
    }

    sources.push({
      activo: toBoolean_(row[0]),
      alias: String(row[1] || "").trim(),
      spreadsheetId: String(row[2] || "").trim(),
      hoja: String(row[3] || "").trim(),
      headerRow: toInteger_(row[4], 1),
      campoNombre: String(row[5] || "").trim(),
      campoEmail: String(row[6] || "").trim(),
      campoTelefono: String(row[7] || "").trim(),
      campoId: String(row[8] || "").trim(),
      campoNotas: String(row[9] || "").trim(),
    });
  }

  return sources;
}

function getRequiredSheet_(sheetName) {
  var sheet = getCentralSpreadsheet_().getSheetByName(sheetName);
  if (!sheet) {
    throw new Error(
      "No existe la hoja '" +
        sheetName +
        "'. Ejecuta primero initializeCentralContacts()."
    );
  }
  return sheet;
}

function getCentralSpreadsheet_() {
  var spreadsheetId = String(CC_CONFIG.CENTRAL_SPREADSHEET_ID || "").trim();

  if (spreadsheetId) {
    return SpreadsheetApp.openById(spreadsheetId);
  }

  var active = SpreadsheetApp.getActiveSpreadsheet();
  if (!active) {
    throw new Error(
      "No hay hoja central configurada. Define CC_CONFIG.CENTRAL_SPREADSHEET_ID."
    );
  }

  return active;
}

function normalizeSourcePayload_(source) {
  return {
    activo: source.activo !== false,
    alias: String(source.alias || "").trim(),
    spreadsheetId: String(source.spreadsheetId || "").trim(),
    hoja: String(source.hoja || "").trim(),
    headerRow: toInteger_(source.headerRow, 1),
    campoNombre: String(source.campoNombre || "").trim(),
    campoEmail: String(source.campoEmail || "").trim(),
    campoTelefono: String(source.campoTelefono || "").trim(),
    campoId: String(source.campoId || "").trim(),
    campoNotas: String(source.campoNotas || "").trim(),
  };
}

function validateSourcePayload_(source) {
  if (!source.alias) {
    throw new Error("La fuente necesita ALIAS.");
  }
  if (!source.spreadsheetId) {
    throw new Error("La fuente necesita SPREADSHEET_ID.");
  }
  if (!source.hoja) {
    throw new Error("La fuente necesita HOJA.");
  }
  if (!source.campoNombre && !source.campoEmail && !source.campoTelefono) {
    throw new Error(
      "Define al menos CAMPO_NOMBRE o CAMPO_EMAIL o CAMPO_TELEFONO."
    );
  }
}

function buildSourceRow_(source) {
  return [
    source.activo,
    source.alias,
    source.spreadsheetId,
    source.hoja,
    source.headerRow,
    source.campoNombre,
    source.campoEmail,
    source.campoTelefono,
    source.campoId,
    source.campoNotas,
  ];
}

function findSourceRow_(sheet, alias, spreadsheetId, hoja) {
  var lastRow = sheet.getLastRow();
  if (lastRow <= 1) {
    return -1;
  }

  var rows = sheet.getRange(2, 1, lastRow - 1, CC_CONFIG.SOURCE_HEADERS.length).getValues();
  for (var i = 0; i < rows.length; i++) {
    var rowAlias = String(rows[i][1] || "").trim();
    var rowSpreadsheetId = String(rows[i][2] || "").trim();
    var rowHoja = String(rows[i][3] || "").trim();
    if (rowAlias === alias && rowSpreadsheetId === spreadsheetId && rowHoja === hoja) {
      return i + 2;
    }
  }

  return -1;
}

function toBoolean_(value) {
  if (typeof value === "boolean") {
    return value;
  }
  var normalized = String(value || "").trim().toLowerCase();
  return normalized === "true" || normalized === "1" || normalized === "si";
}

function toInteger_(value, fallback) {
  var num = parseInt(String(value), 10);
  return isNaN(num) || num <= 0 ? fallback : num;
}
