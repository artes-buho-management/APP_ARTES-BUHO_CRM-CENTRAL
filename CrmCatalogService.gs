function getProvidedCrmCatalog_() {
  return [
    {
      alias: "CRM_01",
      spreadsheetId: "REPLACE_WITH_SHEET_ID",
      url: "https://docs.google.com/spreadsheets/d/REPLACE_WITH_SHEET_ID/edit",
    },
    {
      alias: "CRM_02",
      spreadsheetId: "REPLACE_WITH_SHEET_ID",
      url: "https://docs.google.com/spreadsheets/d/REPLACE_WITH_SHEET_ID/edit",
    },
    {
      alias: "CRM_03",
      spreadsheetId: "REPLACE_WITH_SHEET_ID",
      url: "https://docs.google.com/spreadsheets/d/REPLACE_WITH_SHEET_ID/edit",
    },
    {
      alias: "CRM_04",
      spreadsheetId: "REPLACE_WITH_SHEET_ID",
      url: "https://docs.google.com/spreadsheets/d/REPLACE_WITH_SHEET_ID/edit",
    },
    {
      alias: "CRM_05",
      spreadsheetId: "REPLACE_WITH_SHEET_ID",
      url: "https://docs.google.com/spreadsheets/d/REPLACE_WITH_SHEET_ID/edit",
    },
    {
      alias: "CRM_06",
      spreadsheetId: "REPLACE_WITH_SHEET_ID",
      url: "https://docs.google.com/spreadsheets/d/REPLACE_WITH_SHEET_ID/edit",
    },
    {
      alias: "CRM_07",
      spreadsheetId: "REPLACE_WITH_SHEET_ID",
      url: "https://docs.google.com/spreadsheets/d/REPLACE_WITH_SHEET_ID/edit",
    },
  ];
}

function getDefaultHeaderCandidates_() {
  return {
    campoNombre: CC_CONFIG.HEADER_CANDIDATES.NAME.join("|"),
    campoEmail: CC_CONFIG.HEADER_CANDIDATES.EMAIL.join("|"),
    campoTelefono: CC_CONFIG.HEADER_CANDIDATES.PHONE.join("|"),
    campoId: CC_CONFIG.HEADER_CANDIDATES.ID.join("|"),
    campoNotas: CC_CONFIG.HEADER_CANDIDATES.NOTES.join("|"),
  };
}

function syncProvidedCrmsCatalog() {
  var catalog = getProvidedCrmCatalog_();
  var defaults = getDefaultHeaderCandidates_();
  var output = [];

  for (var i = 0; i < catalog.length; i++) {
    var item = catalog[i];
    var base = {
      activo: true,
      alias: item.alias,
      spreadsheetId: item.spreadsheetId,
      headerRow: 1,
      campoNombre: defaults.campoNombre,
      campoEmail: defaults.campoEmail,
      campoTelefono: defaults.campoTelefono,
      campoId: defaults.campoId,
      campoNotas: defaults.campoNotas,
    };

    try {
      var sync = syncSourceTabs(base);
      output.push({
        alias: item.alias,
        spreadsheetId: item.spreadsheetId,
        ok: true,
        synced: sync.synced,
      });
    } catch (error) {
      output.push({
        alias: item.alias,
        spreadsheetId: item.spreadsheetId,
        ok: false,
        synced: 0,
        error: error.message,
      });
    }
  }

  appendLog_("INFO", "Catalogo CRM sincronizado", {
    total: output.length,
    detail: output,
  });

  return {
    ok: true,
    total: output.length,
    detail: output,
  };
}
