function getLocalAiQueueHeaders_() {
  return [
    "CREATED_AT",
    "TASK_TYPE",
    "STATUS",
    "PAYLOAD_JSON",
    "RESULT_JSON",
    "LAST_ERROR",
    "NEXT_RETRY_AT",
    "ATTEMPTS",
  ];
}

function setLocalAiAvailable() {
  setLocalAiAvailability_(true);
  showToast_("IA local", "IA local marcada como disponible.");
}

function setLocalAiUnavailable() {
  setLocalAiAvailability_(false);
  showToast_("IA local", "IA local marcada como en espera.");
}

function setLocalAiAvailability_(isAvailable) {
  PropertiesService.getScriptProperties().setProperty(
    CC_CONFIG.LOCAL_AI.AVAILABILITY_PROPERTY,
    isAvailable ? "1" : "0"
  );

  appendLog_("INFO", "Estado IA local actualizado", {
    available: !!isAvailable,
  });
}

function isLocalAiAvailable_() {
  if (!CC_CONFIG.LOCAL_AI.ENABLED) {
    return false;
  }

  var raw = PropertiesService.getScriptProperties().getProperty(
    CC_CONFIG.LOCAL_AI.AVAILABILITY_PROPERTY
  );
  return raw === "1";
}

function enqueueLocalAiTask_(taskType, payload) {
  var queueSheet = getRequiredSheet_(CC_CONFIG.SHEETS.AI_QUEUE);
  var pendingRows = Math.max(queueSheet.getLastRow() - 1, 0);

  if (pendingRows >= CC_CONFIG.LOCAL_AI.QUEUE_MAX_ITEMS) {
    appendLog_("WARN", "Cola IA llena", { max: CC_CONFIG.LOCAL_AI.QUEUE_MAX_ITEMS });
    return {
      ok: false,
      queued: false,
      error: "Cola IA llena",
    };
  }

  var now = new Date();
  queueSheet.appendRow([
    now,
    String(taskType || "UNKNOWN"),
    "PENDING",
    JSON.stringify(payload || {}),
    "",
    "",
    now,
    0,
  ]);

  var row = queueSheet.getLastRow();
  appendLog_("INFO", "Tarea IA en cola", {
    taskType: taskType,
    row: row,
  });

  return {
    ok: true,
    queued: true,
    row: row,
  };
}

function processPendingLocalAiTasks() {
  var queueSheet = getRequiredSheet_(CC_CONFIG.SHEETS.AI_QUEUE);

  if (!isLocalAiAvailable_()) {
    appendLog_("INFO", "Proceso cola IA omitido", { reason: "IA no disponible" });
    showToast_("IA local", "Sigue en espera. Cola no procesada.");
    return {
      ok: true,
      processed: 0,
      pending: Math.max(queueSheet.getLastRow() - 1, 0),
    };
  }

  var lastRow = queueSheet.getLastRow();
  if (lastRow <= 1) {
    return { ok: true, processed: 0, pending: 0 };
  }

  var rows = queueSheet.getRange(2, 1, lastRow - 1, getLocalAiQueueHeaders_().length).getValues();
  var processed = 0;
  var now = new Date();

  for (var i = 0; i < rows.length; i++) {
    var rowIndex = i + 2;
    var row = rows[i];
    var status = String(row[2] || "");
    var nextRetryAt = row[6] instanceof Date ? row[6] : new Date(0);

    if (status !== "PENDING" && status !== "RETRY") {
      continue;
    }
    if (nextRetryAt.getTime() > now.getTime()) {
      continue;
    }

    var attempts = parseInt(String(row[7] || "0"), 10);
    var payload = safeJsonParse_(row[3]);
    var result = runLocalAiTask_(String(row[1] || ""), payload);
    attempts = isNaN(attempts) ? 1 : attempts + 1;

    if (result.ok) {
      queueSheet
        .getRange(rowIndex, 3, 1, 6)
        .setValues([["DONE", row[3], JSON.stringify(result.data || {}), "", now, attempts]]);
    } else {
      var nextRetry = new Date(now.getTime() + CC_CONFIG.LOCAL_AI.RETRY_MINUTES * 60 * 1000);
      queueSheet
        .getRange(rowIndex, 3, 1, 6)
        .setValues([["RETRY", row[3], "", String(result.error || "Error IA"), nextRetry, attempts]]);
    }

    processed++;
    if (processed >= 25) {
      break;
    }
  }

  appendLog_("INFO", "Cola IA procesada", { processed: processed });
  return {
    ok: true,
    processed: processed,
    pending: Math.max(queueSheet.getLastRow() - 1 - processed, 0),
  };
}

function runLocalAiTask_(taskType, payload) {
  // Punto unico para conectar tu IA local real.
  // Ahora devuelve respuesta neutra para no romper el flujo.
  return {
    ok: true,
    data: {
      taskType: taskType,
      handledAt: new Date(),
      note: "Task registrada en IA local unica.",
      payload: payload || {},
    },
  };
}

function maybeQueueLocalAiForSearch_(term, context) {
  if (!CC_CONFIG.LOCAL_AI.ENABLED) {
    return { queued: false, reason: "disabled" };
  }

  if (isLocalAiAvailable_()) {
    return { queued: false, reason: "available" };
  }

  return enqueueLocalAiTask_("FUZZY_CONTACT_SEARCH", {
    term: term,
    context: context || {},
  });
}

function safeJsonParse_(value) {
  try {
    if (!value) {
      return {};
    }
    return JSON.parse(String(value));
  } catch (error) {
    return {};
  }
}
