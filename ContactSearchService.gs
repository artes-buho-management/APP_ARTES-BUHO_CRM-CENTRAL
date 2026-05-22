function searchContacts(term, maxResults) {
  var normalizedTerm = normalizeText_(term);
  if (!normalizedTerm) {
    return [];
  }

  var limit = limitNumber_(maxResults, 1, 500, CC_CONFIG.DEFAULT_MAX_RESULTS);
  var sources = getSources().filter(function (source) {
    return source.activo;
  });
  var results = [];

  for (var i = 0; i < sources.length; i++) {
    if (results.length >= limit) {
      break;
    }

    var sourceResults = searchInSource_(sources[i], term, normalizedTerm, limit - results.length);
    for (var j = 0; j < sourceResults.length; j++) {
      results.push(sourceResults[j]);
      if (results.length >= limit) {
        break;
      }
    }
  }

  results = dedupeAndSortResults_(results).slice(0, limit);
  writeResultsSheet_(term, results);

  var bestScore = results.length ? results[0].score : 0;
  var aiQueue = maybeQueueLocalAiForSearch_(term, {
    totalResults: results.length,
    bestScore: bestScore,
    minExpectedScore: CC_CONFIG.MATCHING.HIGH_CONFIDENCE_SCORE,
  });

  appendLog_("INFO", "Busqueda ejecutada", {
    term: term,
    total: results.length,
    fuentesActivas: sources.length,
    bestScore: bestScore,
    aiQueued: !!aiQueue.queued,
  });

  return results;
}

function searchInSource_(source, rawTerm, normalizedTerm, availableSlots) {
  var results = [];

  try {
    var spreadsheet = SpreadsheetApp.openById(source.spreadsheetId);
    var sheet = spreadsheet.getSheetByName(source.hoja);
    if (!sheet) {
      appendLog_("WARN", "Hoja origen no encontrada", source);
      return results;
    }

    var lastRow = sheet.getLastRow();
    var lastColumn = sheet.getLastColumn();
    if (lastRow <= source.headerRow || lastColumn === 0) {
      return results;
    }

    var headers = sheet
      .getRange(source.headerRow, 1, 1, lastColumn)
      .getDisplayValues()[0];
    var rowCount = lastRow - source.headerRow;
    var rows = sheet.getRange(source.headerRow + 1, 1, rowCount, lastColumn).getDisplayValues();

    var idxName = findColumnByHeader_(
      headers,
      source.campoNombre,
      CC_CONFIG.HEADER_CANDIDATES.NAME
    );
    var idxEmail = findColumnByHeader_(
      headers,
      source.campoEmail,
      CC_CONFIG.HEADER_CANDIDATES.EMAIL
    );
    var idxPhone = findColumnByHeader_(
      headers,
      source.campoTelefono,
      CC_CONFIG.HEADER_CANDIDATES.PHONE
    );
    var idxId = findColumnByHeader_(headers, source.campoId, CC_CONFIG.HEADER_CANDIDATES.ID);
    var idxNotes = findColumnByHeader_(
      headers,
      source.campoNotas,
      CC_CONFIG.HEADER_CANDIDATES.NOTES
    );

    for (var i = 0; i < rows.length; i++) {
      if (results.length >= availableSlots) {
        break;
      }

      var row = rows[i];
      var fields = {
        NOMBRE: safeCellValue_(row, idxName),
        EMAIL: safeCellValue_(row, idxEmail),
        TELEFONO: safeCellValue_(row, idxPhone),
        ID: safeCellValue_(row, idxId),
        NOTAS: safeCellValue_(row, idxNotes),
      };

      var best = computeBestMatchForFields_(rawTerm, normalizedTerm, fields);
      if (!best.isMatch) {
        continue;
      }

      results.push({
        sourceAlias: source.alias,
        spreadsheetId: source.spreadsheetId,
        sheetName: source.hoja,
        rowNumber: source.headerRow + 1 + i,
        matchedBy: best.field,
        score: best.score,
        confidence: best.score >= CC_CONFIG.MATCHING.HIGH_CONFIDENCE_SCORE ? "ALTA" : "MEDIA",
        contactId: fields.ID,
        name: fields.NOMBRE,
        email: fields.EMAIL,
        phone: fields.TELEFONO,
        notes: fields.NOTAS,
      });
    }
  } catch (error) {
    appendLog_("ERROR", "Error leyendo fuente", {
      source: source,
      error: error.message,
    });
  }

  return results;
}

function updateContact(payload) {
  payload = payload || {};
  var spreadsheetId = String(payload.spreadsheetId || "").trim();
  var sheetName = String(payload.sheetName || "").trim();
  var rowNumber = limitNumber_(payload.rowNumber, 1, 2000000, 0);

  if (!spreadsheetId || !sheetName || !rowNumber) {
    throw new Error("Faltan datos minimos para actualizar contacto.");
  }

  var source = findSourceForRecord_(spreadsheetId, sheetName);
  if (!source) {
    throw new Error("No existe una fuente registrada para ese contacto.");
  }

  var spreadsheet = SpreadsheetApp.openById(spreadsheetId);
  var sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) {
    throw new Error("No se encontro la hoja destino para actualizar.");
  }

  var lastColumn = sheet.getLastColumn();
  if (lastColumn < 1) {
    throw new Error("La hoja destino no tiene columnas.");
  }

  var headers = sheet
    .getRange(source.headerRow, 1, 1, lastColumn)
    .getDisplayValues()[0];

  var idxName = findColumnByHeader_(
    headers,
    source.campoNombre,
    CC_CONFIG.HEADER_CANDIDATES.NAME
  );
  var idxEmail = findColumnByHeader_(
    headers,
    source.campoEmail,
    CC_CONFIG.HEADER_CANDIDATES.EMAIL
  );
  var idxPhone = findColumnByHeader_(
    headers,
    source.campoTelefono,
    CC_CONFIG.HEADER_CANDIDATES.PHONE
  );
  var idxId = findColumnByHeader_(headers, source.campoId, CC_CONFIG.HEADER_CANDIDATES.ID);
  var idxNotes = findColumnByHeader_(
    headers,
    source.campoNotas,
    CC_CONFIG.HEADER_CANDIDATES.NOTES
  );

  var rowValues = sheet.getRange(rowNumber, 1, 1, lastColumn).getValues()[0];
  var changed = {};

  updateCellIfProvided_(rowValues, idxName, payload.name, "name", changed);
  updateCellIfProvided_(rowValues, idxEmail, payload.email, "email", changed);
  updateCellIfProvided_(rowValues, idxPhone, payload.phone, "phone", changed);
  updateCellIfProvided_(rowValues, idxId, payload.contactId, "contactId", changed);
  updateCellIfProvided_(rowValues, idxNotes, payload.notes, "notes", changed);

  sheet.getRange(rowNumber, 1, 1, lastColumn).setValues([rowValues]);

  appendLog_("INFO", "Contacto actualizado", {
    spreadsheetId: spreadsheetId,
    sheetName: sheetName,
    rowNumber: rowNumber,
    changed: changed,
  });

  return {
    ok: true,
    spreadsheetId: spreadsheetId,
    sheetName: sheetName,
    rowNumber: rowNumber,
    changed: changed,
    record: {
      sourceAlias: source.alias,
      spreadsheetId: spreadsheetId,
      sheetName: sheetName,
      rowNumber: rowNumber,
      matchedBy: "MANUAL",
      score: 1,
      confidence: "ALTA",
      contactId: safeCellValue_(rowValues, idxId),
      name: safeCellValue_(rowValues, idxName),
      email: safeCellValue_(rowValues, idxEmail),
      phone: safeCellValue_(rowValues, idxPhone),
      notes: safeCellValue_(rowValues, idxNotes),
    },
  };
}

function updateCellIfProvided_(rowValues, index, nextValue, fieldName, changed) {
  if (index < 0 || typeof nextValue === "undefined" || nextValue === null) {
    return;
  }
  var sanitized = String(nextValue).trim();
  rowValues[index] = sanitized;
  changed[fieldName] = sanitized;
}

function findSourceForRecord_(spreadsheetId, sheetName) {
  var sources = getSources();
  for (var i = 0; i < sources.length; i++) {
    if (sources[i].spreadsheetId === spreadsheetId && sources[i].hoja === sheetName) {
      return sources[i];
    }
  }
  return null;
}

function dedupeAndSortResults_(results) {
  var map = {};
  for (var i = 0; i < results.length; i++) {
    var item = results[i];
    var key = item.spreadsheetId + "|" + item.sheetName + "|" + item.rowNumber;
    if (!map[key] || map[key].score < item.score) {
      map[key] = item;
    }
  }

  var out = Object.keys(map).map(function (key) {
    return map[key];
  });

  out.sort(function (a, b) {
    if (b.score !== a.score) {
      return b.score - a.score;
    }
    return a.rowNumber - b.rowNumber;
  });

  return out;
}

function computeBestMatchForFields_(rawTerm, normalizedTerm, fields) {
  var keys = Object.keys(fields);
  var bestScore = 0;
  var bestField = "DESCONOCIDO";

  for (var i = 0; i < keys.length; i++) {
    var field = keys[i];
    var value = fields[field];
    var score = scoreFieldMatch_(rawTerm, normalizedTerm, value, field);
    if (score > bestScore) {
      bestScore = score;
      bestField = field;
    }
  }

  return {
    field: bestField,
    score: roundScore_(bestScore),
    isMatch: bestScore >= CC_CONFIG.MATCHING.MIN_SCORE,
  };
}

function scoreFieldMatch_(rawTerm, normalizedTerm, value, field) {
  var normalizedValue = normalizeText_(value);
  if (!normalizedValue) {
    return 0;
  }

  var score = 0;

  if (normalizedValue === normalizedTerm) {
    score = 1;
  } else if (normalizedValue.indexOf(normalizedTerm) >= 0) {
    score = Math.max(score, 0.95);
  }

  if (field === "TELEFONO") {
    var pTerm = normalizePhone_(rawTerm);
    var pValue = normalizePhone_(value);
    if (pTerm && pValue) {
      if (pValue === pTerm) {
        score = Math.max(score, 1);
      } else if (pValue.indexOf(pTerm) >= 0 || pTerm.indexOf(pValue) >= 0) {
        score = Math.max(score, 0.97);
      }
    }
  }

  if (field === "EMAIL") {
    var emailTerm = sanitizeAlnum_(normalizedTerm);
    var emailValue = sanitizeAlnum_(normalizedValue);
    if (emailTerm && emailValue) {
      if (emailValue === emailTerm) {
        score = Math.max(score, 1);
      } else if (emailValue.indexOf(emailTerm) >= 0) {
        score = Math.max(score, 0.96);
      }
    }
  }

  var tokenScore = getBestTokenSimilarity_(normalizedTerm, normalizedValue);
  score = Math.max(score, tokenScore);

  var compactTerm = sanitizeAlnum_(normalizedTerm);
  var compactValue = sanitizeAlnum_(normalizedValue);
  if (compactTerm && compactValue) {
    score = Math.max(score, getStringSimilarity_(compactTerm, compactValue));
  }

  var vowelTerm = neutralizeVowels_(compactTerm || normalizedTerm);
  var vowelValue = neutralizeVowels_(compactValue || normalizedValue);
  if (vowelTerm && vowelValue) {
    if (vowelValue.indexOf(vowelTerm) >= 0 || vowelTerm.indexOf(vowelValue) >= 0) {
      score = Math.max(score, 0.83);
    } else {
      score = Math.max(score, getStringSimilarity_(vowelTerm, vowelValue) * 0.9);
    }
  }

  return Math.min(score, 1);
}

function getBestTokenSimilarity_(normalizedTerm, normalizedValue) {
  var tokens = normalizedValue.split(/\s+/).filter(Boolean);
  var best = 0;

  for (var i = 0; i < tokens.length; i++) {
    best = Math.max(best, getStringSimilarity_(normalizedTerm, tokens[i]));
    if (best >= 0.95) {
      break;
    }
  }

  return best;
}

function getStringSimilarity_(a, b) {
  if (!a || !b) {
    return 0;
  }
  if (a === b) {
    return 1;
  }

  var distance = levenshteinDistance_(a, b);
  var maxLen = Math.max(a.length, b.length);
  if (!maxLen) {
    return 0;
  }
  return 1 - distance / maxLen;
}

function levenshteinDistance_(a, b) {
  var rows = a.length + 1;
  var cols = b.length + 1;
  var dp = [];

  for (var r = 0; r < rows; r++) {
    dp[r] = [];
    dp[r][0] = r;
  }
  for (var c = 0; c < cols; c++) {
    dp[0][c] = c;
  }

  for (var i = 1; i < rows; i++) {
    for (var j = 1; j < cols; j++) {
      var cost = a.charAt(i - 1) === b.charAt(j - 1) ? 0 : 1;
      dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost);
    }
  }

  return dp[rows - 1][cols - 1];
}

function neutralizeVowels_(value) {
  return String(value || "").replace(/[eiou]/g, "a");
}

function sanitizeAlnum_(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

function normalizePhone_(value) {
  return String(value || "").replace(/[^0-9]/g, "");
}

function writeResultsSheet_(term, results) {
  var sheet = getRequiredSheet_(CC_CONFIG.SHEETS.RESULTS);
  var width = CC_CONFIG.RESULT_HEADERS.length;

  if (sheet.getLastRow() > 1) {
    sheet.getRange(2, 1, sheet.getLastRow() - 1, width).clearContent();
  }

  if (!results.length) {
    return;
  }

  var now = new Date();
  var rows = [];
  for (var i = 0; i < results.length; i++) {
    var item = results[i];
    rows.push([
      now,
      term,
      item.score,
      item.sourceAlias,
      item.spreadsheetId,
      item.sheetName,
      item.rowNumber,
      item.matchedBy,
      item.contactId,
      item.name,
      item.email,
      item.phone,
      item.notes,
    ]);
  }

  sheet.getRange(2, 1, rows.length, width).setValues(rows);
}

function appendLog_(level, message, payload) {
  try {
    var sheet = getRequiredSheet_(CC_CONFIG.SHEETS.LOG);
    sheet.appendRow([
      new Date(),
      String(level || "INFO"),
      String(message || ""),
      JSON.stringify(payload || {}),
    ]);
  } catch (error) {
    // Evita cortar operaciones principales por fallo de log.
  }
}

function findColumnByHeader_(headers, expectedHeader, fallbackCandidates) {
  var candidates = [];
  if (expectedHeader) {
    candidates = candidates.concat(
      String(expectedHeader)
        .split("|")
        .map(function (x) {
          return String(x || "").trim();
        })
        .filter(Boolean)
    );
  }
  if (fallbackCandidates && fallbackCandidates.length) {
    candidates = candidates.concat(fallbackCandidates);
  }

  if (!candidates.length) {
    return -1;
  }

  var normalizedHeaders = headers.map(function (h) {
    return normalizeText_(h);
  });
  var compactHeaders = headers.map(function (h) {
    return sanitizeAlnum_(normalizeText_(h));
  });

  for (var c = 0; c < candidates.length; c++) {
    var target = normalizeText_(candidates[c]);
    if (!target) {
      continue;
    }
    for (var i = 0; i < normalizedHeaders.length; i++) {
      if (normalizedHeaders[i] === target) {
        return i;
      }
    }
  }

  for (var c2 = 0; c2 < candidates.length; c2++) {
    var compactTarget = sanitizeAlnum_(normalizeText_(candidates[c2]));
    if (!compactTarget) {
      continue;
    }
    for (var j = 0; j < compactHeaders.length; j++) {
      if (compactHeaders[j] === compactTarget) {
        return j;
      }
    }
  }

  return -1;
}

function safeCellValue_(row, index) {
  if (index < 0 || index >= row.length) {
    return "";
  }
  return String(row[index] || "").trim();
}

function normalizeText_(value) {
  var text = String(value || "").trim().toLowerCase();
  if (!text) {
    return "";
  }

  try {
    return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  } catch (error) {
    return text;
  }
}

function roundScore_(value) {
  return Math.round(value * 1000) / 1000;
}

function limitNumber_(value, min, max, fallback) {
  var parsed = parseInt(String(value), 10);
  if (isNaN(parsed)) {
    return fallback;
  }
  if (parsed < min) {
    return min;
  }
  if (parsed > max) {
    return max;
  }
  return parsed;
}
