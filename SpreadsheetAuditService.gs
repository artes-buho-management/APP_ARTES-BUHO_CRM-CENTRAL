function getAuditHeaders_() {
  return ["FECHA", "ALCANCE", "SPREADSHEET_ID", "SHEET", "SECCION", "DETALLE_JSON"];
}

function runCentralSpreadsheetAudit() {
  var report = inspectSpreadsheet_(CC_CONFIG.CENTRAL_SPREADSHEET_ID, "CENTRAL");
  writeAuditReport_(report, { clear: true });
  appendLog_("INFO", "Auditoria central completada", {
    spreadsheetId: CC_CONFIG.CENTRAL_SPREADSHEET_ID,
    sheets: report.sheets.length,
  });
  showToast_("Auditoria", "Auditoria de hoja central completada.");
  return report;
}

function inspectSpreadsheetById(spreadsheetId, scope) {
  var report = inspectSpreadsheet_(spreadsheetId, scope || "MANUAL");
  writeAuditReport_(report, { clear: false });
  return report;
}

function runProvidedCrmsAudit() {
  var catalog = getProvidedCrmCatalog_();
  var summary = [];

  clearAuditSheet_();

  for (var i = 0; i < catalog.length; i++) {
    var item = catalog[i];
    try {
      var scope = "CRM_BATCH_" + item.alias;
      var report = inspectSpreadsheet_(item.spreadsheetId, scope);
      writeAuditReport_(report, { clear: false });
      summary.push({
        alias: item.alias,
        spreadsheetId: item.spreadsheetId,
        ok: true,
        sheets: report.sheets.length,
      });
    } catch (error) {
      summary.push({
        alias: item.alias,
        spreadsheetId: item.spreadsheetId,
        ok: false,
        error: serializeError_(error),
      });
    }
  }

  appendLog_("INFO", "Auditoria lote CRM completada", {
    total: summary.length,
    detail: summary,
  });

  return {
    ok: true,
    total: summary.length,
    detail: summary,
  };
}

function inspectSpreadsheet_(spreadsheetId, scope) {
  var startedAt = new Date();
  var spreadsheet = SpreadsheetApp.openById(spreadsheetId);
  var sheets = spreadsheet.getSheets();

  var report = {
    generatedAt: startedAt,
    scope: String(scope || "MANUAL"),
    spreadsheetId: spreadsheetId,
    spreadsheetName: spreadsheet.getName(),
    timeZone: spreadsheet.getSpreadsheetTimeZone(),
    workbookPermissions: inspectWorkbookPermissions_(spreadsheetId),
    sheets: [],
    errors: [],
  };

  for (var i = 0; i < sheets.length; i++) {
    var sheet = sheets[i];
    try {
      report.sheets.push(inspectSheet_(spreadsheet, sheet));
    } catch (error) {
      report.errors.push({
        sheetName: sheet.getName(),
        error: serializeError_(error),
      });
    }
  }

  report.filterViews = inspectFilterViews_(spreadsheetId);
  report.completedAt = new Date();
  return report;
}

function inspectSheet_(spreadsheet, sheet) {
  var usedRange = getUsedRange_(sheet);
  var usedRows = usedRange ? usedRange.getNumRows() : 0;
  var usedCols = usedRange ? usedRange.getNumColumns() : 0;

  return {
    sheetName: sheet.getName(),
    sheetId: sheet.getSheetId(),
    isHidden: sheet.isSheetHidden(),
    structure: {
      maxRows: sheet.getMaxRows(),
      maxColumns: sheet.getMaxColumns(),
      frozenRows: sheet.getFrozenRows(),
      frozenColumns: sheet.getFrozenColumns(),
      lastRow: sheet.getLastRow(),
      lastColumn: sheet.getLastColumn(),
      usedRangeA1: usedRange ? usedRange.getA1Notation() : "",
      usedRows: usedRows,
      usedColumns: usedCols,
    },
    visibleDataAndFormulas: inspectVisibleDataAndFormulas_(sheet),
    formats: inspectFormats_(sheet),
    mergedCells: inspectMergedCells_(sheet),
    dataValidations: inspectDataValidations_(sheet),
    filters: inspectSheetFilters_(sheet),
    conditionalFormatting: inspectConditionalFormatting_(sheet),
    protections: inspectSheetProtections_(spreadsheet, sheet),
  };
}

function inspectVisibleDataAndFormulas_(sheet) {
  var range = getUsedRange_(sheet);
  if (!range) {
    return {
      hasData: false,
      preview: [],
      formulasPreview: [],
    };
  }

  var maxRows = Math.min(range.getNumRows(), 25);
  var maxCols = Math.min(range.getNumColumns(), 20);
  var previewRange = sheet.getRange(range.getRow(), range.getColumn(), maxRows, maxCols);

  return {
    hasData: true,
    previewRows: maxRows,
    previewColumns: maxCols,
    preview: previewRange.getDisplayValues(),
    formulasPreview: previewRange.getFormulas(),
  };
}

function inspectFormats_(sheet) {
  var range = getUsedRange_(sheet);
  if (!range) {
    return {
      hasFormats: false,
      summary: {},
    };
  }

  var maxRows = Math.min(range.getNumRows(), 25);
  var maxCols = Math.min(range.getNumColumns(), 20);
  var r = sheet.getRange(range.getRow(), range.getColumn(), maxRows, maxCols);

  return {
    hasFormats: true,
    previewRows: maxRows,
    previewColumns: maxCols,
    summary: {
      backgrounds: summarizeUniqueValues_(r.getBackgrounds()),
      fontColors: summarizeUniqueValues_(r.getFontColors()),
      fontFamilies: summarizeUniqueValues_(r.getFontFamilies()),
      fontSizes: summarizeUniqueValues_(r.getFontSizes()),
      fontWeights: summarizeUniqueValues_(r.getFontWeights()),
      fontStyles: summarizeUniqueValues_(r.getFontStyles()),
      horizontalAlignments: summarizeUniqueValues_(r.getHorizontalAlignments()),
      verticalAlignments: summarizeUniqueValues_(r.getVerticalAlignments()),
      numberFormats: summarizeUniqueValues_(r.getNumberFormats()),
      wraps: summarizeUniqueValues_(r.getWraps()),
    },
  };
}

function inspectMergedCells_(sheet) {
  var range = getUsedRange_(sheet);
  if (!range) {
    return {
      total: 0,
      sampleRanges: [],
    };
  }

  var merged = range.getMergedRanges();
  var sample = [];
  for (var i = 0; i < merged.length && i < 40; i++) {
    sample.push(merged[i].getA1Notation());
  }

  return {
    total: merged.length,
    sampleRanges: sample,
  };
}

function inspectDataValidations_(sheet) {
  var range = getUsedRange_(sheet);
  if (!range) {
    return {
      totalCellsWithValidation: 0,
      criteriaSummary: {},
      sample: [],
    };
  }

  var validations = range.getDataValidations();
  var total = 0;
  var criteriaSummary = {};
  var sample = [];

  for (var r = 0; r < validations.length; r++) {
    for (var c = 0; c < validations[r].length; c++) {
      var rule = validations[r][c];
      if (!rule) {
        continue;
      }

      total++;
      var criteriaType = String(rule.getCriteriaType() || "UNKNOWN");
      criteriaSummary[criteriaType] = (criteriaSummary[criteriaType] || 0) + 1;

      if (sample.length < 40) {
        sample.push({
          cell: sheet.getRange(range.getRow() + r, range.getColumn() + c).getA1Notation(),
          criteriaType: criteriaType,
          allowInvalid: rule.getAllowInvalid(),
          helpText: rule.getHelpText(),
        });
      }
    }
  }

  return {
    totalCellsWithValidation: total,
    criteriaSummary: criteriaSummary,
    sample: sample,
  };
}

function inspectSheetFilters_(sheet) {
  var filter = sheet.getFilter();
  if (!filter) {
    return {
      basicFilterActive: false,
      range: "",
      criteria: [],
    };
  }

  var range = filter.getRange();
  var startColumn = range.getColumn();
  var endColumn = startColumn + range.getNumColumns() - 1;
  var criteria = [];

  for (var col = startColumn; col <= endColumn; col++) {
    var columnCriteria = filter.getColumnFilterCriteria(col);
    if (!columnCriteria) {
      continue;
    }

    criteria.push({
      column: col,
      criteriaType: String(columnCriteria.getCriteriaType() || "CUSTOM"),
      hiddenValues: columnCriteria.getHiddenValues(),
      criteriaValues: columnCriteria.getCriteriaValues(),
    });
  }

  return {
    basicFilterActive: true,
    range: range.getA1Notation(),
    criteria: criteria,
  };
}

function inspectFilterViews_(spreadsheetId) {
  try {
    if (typeof Sheets === "undefined" || !Sheets.Spreadsheets) {
      return {
        available: false,
        reason: "Advanced Sheets API no habilitada",
      };
    }

    var response = Sheets.Spreadsheets.get(spreadsheetId, {
      fields:
        "sheets(properties(sheetId,title),filterViews(filterViewId,title,range,criteria))",
    });

    var items = [];
    var sheets = response.sheets || [];
    for (var i = 0; i < sheets.length; i++) {
      var sheet = sheets[i];
      var filterViews = sheet.filterViews || [];
      for (var j = 0; j < filterViews.length; j++) {
        var fv = filterViews[j];
        items.push({
          sheetId: sheet.properties ? sheet.properties.sheetId : null,
          sheetTitle: sheet.properties ? sheet.properties.title : "",
          filterViewId: fv.filterViewId,
          title: fv.title || "",
          range: fv.range || {},
          criteria: fv.criteria || {},
        });
      }
    }

    return {
      available: true,
      total: items.length,
      items: items,
    };
  } catch (error) {
    return {
      available: false,
      reason: serializeError_(error),
    };
  }
}

function inspectConditionalFormatting_(sheet) {
  var rules = sheet.getConditionalFormatRules();
  var sample = [];

  for (var i = 0; i < rules.length && i < 40; i++) {
    var rule = rules[i];
    var ranges = rule.getRanges();
    var a1Ranges = [];
    for (var j = 0; j < ranges.length; j++) {
      a1Ranges.push(ranges[j].getA1Notation());
    }

    var booleanCondition = rule.getBooleanCondition();
    var gradientCondition = rule.getGradientCondition();

    sample.push({
      ranges: a1Ranges,
      type: booleanCondition ? "BOOLEAN" : gradientCondition ? "GRADIENT" : "UNKNOWN",
      booleanCriteriaType: booleanCondition
        ? String(booleanCondition.getCriteriaType() || "")
        : "",
    });
  }

  return {
    totalRules: rules.length,
    sample: sample,
  };
}

function inspectSheetProtections_(spreadsheet, sheet) {
  var result = {
    sheetProtections: [],
    rangeProtections: [],
  };

  var sheetProtections = sheet.getProtections(SpreadsheetApp.ProtectionType.SHEET);
  for (var i = 0; i < sheetProtections.length; i++) {
    result.sheetProtections.push(serializeProtection_(sheetProtections[i], ""));
  }

  var rangeProtections = sheet.getProtections(SpreadsheetApp.ProtectionType.RANGE);
  for (var j = 0; j < rangeProtections.length; j++) {
    var range = rangeProtections[j].getRange();
    result.rangeProtections.push(
      serializeProtection_(rangeProtections[j], range ? range.getA1Notation() : "")
    );
  }

  return result;
}

function inspectWorkbookPermissions_(spreadsheetId) {
  try {
    var file = DriveApp.getFileById(spreadsheetId);
    var owner = file.getOwner();
    var editors = file.getEditors();
    var viewers = file.getViewers();

    return {
      owner: owner ? owner.getEmail() : "",
      editors: mapUsersToEmails_(editors),
      viewers: mapUsersToEmails_(viewers),
      sharingAccess: String(file.getSharingAccess()),
      sharingPermission: String(file.getSharingPermission()),
    };
  } catch (error) {
    return {
      error: serializeError_(error),
    };
  }
}

function writeAuditReport_(report, options) {
  options = options || {};
  var shouldClear = !!options.clear;
  var sheet = getRequiredSheet_(CC_CONFIG.SHEETS.AUDIT);
  if (shouldClear || sheet.getLastRow() < 1) {
    sheet.clearContents();
    sheet.getRange(1, 1, 1, getAuditHeaders_().length).setValues([getAuditHeaders_()]);
  }

  var rows = [];
  for (var i = 0; i < report.sheets.length; i++) {
    var item = report.sheets[i];
    rows.push([new Date(), report.scope, report.spreadsheetId, item.sheetName, "STRUCTURE", jsonStringify_(item.structure)]);
    rows.push([
      new Date(),
      report.scope,
      report.spreadsheetId,
      item.sheetName,
      "VISIBLE_DATA_AND_FORMULAS",
      jsonStringify_(item.visibleDataAndFormulas),
    ]);
    rows.push([new Date(), report.scope, report.spreadsheetId, item.sheetName, "FORMATS", jsonStringify_(item.formats)]);
    rows.push([
      new Date(),
      report.scope,
      report.spreadsheetId,
      item.sheetName,
      "MERGED_CELLS",
      jsonStringify_(item.mergedCells),
    ]);
    rows.push([
      new Date(),
      report.scope,
      report.spreadsheetId,
      item.sheetName,
      "DATA_VALIDATIONS",
      jsonStringify_(item.dataValidations),
    ]);
    rows.push([new Date(), report.scope, report.spreadsheetId, item.sheetName, "FILTERS", jsonStringify_(item.filters)]);
    rows.push([
      new Date(),
      report.scope,
      report.spreadsheetId,
      item.sheetName,
      "CONDITIONAL_FORMATTING",
      jsonStringify_(item.conditionalFormatting),
    ]);
    rows.push([
      new Date(),
      report.scope,
      report.spreadsheetId,
      item.sheetName,
      "PROTECTIONS",
      jsonStringify_(item.protections),
    ]);
  }

  rows.push([
    new Date(),
    report.scope,
    report.spreadsheetId,
    "",
    "WORKBOOK_PERMISSIONS",
    jsonStringify_(report.workbookPermissions),
  ]);
  rows.push([
    new Date(),
    report.scope,
    report.spreadsheetId,
    "",
    "FILTER_VIEWS",
    jsonStringify_(report.filterViews),
  ]);
  rows.push([
    new Date(),
    report.scope,
    report.spreadsheetId,
    "",
    "ERRORS",
    jsonStringify_(report.errors),
  ]);

  if (rows.length) {
    var start = Math.max(sheet.getLastRow() + 1, 2);
    sheet.getRange(start, 1, rows.length, getAuditHeaders_().length).setValues(rows);
  }
}

function clearAuditSheet_() {
  var sheet = getRequiredSheet_(CC_CONFIG.SHEETS.AUDIT);
  sheet.clearContents();
  sheet.getRange(1, 1, 1, getAuditHeaders_().length).setValues([getAuditHeaders_()]);
}

function serializeProtection_(protection, rangeA1) {
  var editors = [];
  try {
    editors = mapUsersToEmails_(protection.getEditors());
  } catch (error) {
    editors = [];
  }

  return {
    description: protection.getDescription(),
    range: rangeA1,
    warningOnly: protection.isWarningOnly(),
    domainEdit: protection.canDomainEdit(),
    editors: editors,
    unprotectedRanges: mapRangesToA1_(protection.getUnprotectedRanges()),
  };
}

function summarizeUniqueValues_(matrix) {
  var map = {};
  for (var i = 0; i < matrix.length; i++) {
    for (var j = 0; j < matrix[i].length; j++) {
      var key = String(matrix[i][j]);
      map[key] = (map[key] || 0) + 1;
    }
  }
  return map;
}

function getUsedRange_(sheet) {
  var lastRow = sheet.getLastRow();
  var lastCol = sheet.getLastColumn();
  if (lastRow < 1 || lastCol < 1) {
    return null;
  }
  return sheet.getRange(1, 1, lastRow, lastCol);
}

function mapUsersToEmails_(users) {
  var out = [];
  for (var i = 0; i < users.length; i++) {
    out.push(users[i].getEmail());
  }
  return out;
}

function mapRangesToA1_(ranges) {
  var out = [];
  if (!ranges) {
    return out;
  }
  for (var i = 0; i < ranges.length; i++) {
    out.push(ranges[i].getA1Notation());
  }
  return out;
}

function jsonStringify_(value) {
  try {
    return JSON.stringify(value || {});
  } catch (error) {
    return "{}";
  }
}

function serializeError_(error) {
  if (!error) {
    return "Unknown error";
  }
  return String(error.message || error);
}
