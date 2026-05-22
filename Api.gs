function apiInitializeProject() {
  try {
    initializeCentralContacts();
    return { ok: true };
  } catch (error) {
    return { ok: false, error: error.message };
  }
}

function apiSearchContacts(payload) {
  payload = payload || {};
  var term = String(payload.term || "").trim();
  var maxResults = payload.maxResults;

  if (!term) {
    return {
      ok: false,
      error: "Debes indicar un termino de busqueda.",
      total: 0,
      results: [],
    };
  }

  try {
    var results = searchContacts(term, maxResults);
    return {
      ok: true,
      error: "",
      total: results.length,
      results: results,
      localAiAvailable: isLocalAiAvailable_(),
    };
  } catch (error) {
    appendLog_("ERROR", "apiSearchContacts fallo", {
      term: term,
      error: error.message,
    });
    return {
      ok: false,
      error: error.message,
      total: 0,
      results: [],
    };
  }
}

function apiUpdateContact(payload) {
  try {
    var result = updateContact(payload || {});
    return {
      ok: true,
      error: "",
      result: result,
    };
  } catch (error) {
    appendLog_("ERROR", "apiUpdateContact fallo", {
      payload: payload,
      error: error.message,
    });
    return {
      ok: false,
      error: error.message,
    };
  }
}

function apiRegisterSource(payload) {
  try {
    var result = registerSource(payload || {});
    return {
      ok: true,
      error: "",
      row: result.row,
      source: result.source,
    };
  } catch (error) {
    appendLog_("ERROR", "apiRegisterSource fallo", {
      payload: payload,
      error: error.message,
    });
    return {
      ok: false,
      error: error.message,
    };
  }
}

function apiSyncSourceTabs(payload) {
  try {
    var result = syncSourceTabs(payload || {});
    return {
      ok: true,
      error: "",
      synced: result.synced,
      tabs: result.tabs,
    };
  } catch (error) {
    appendLog_("ERROR", "apiSyncSourceTabs fallo", {
      payload: payload,
      error: error.message,
    });
    return {
      ok: false,
      error: error.message,
      synced: 0,
      tabs: [],
    };
  }
}

function apiSyncProvidedCrmsCatalog() {
  try {
    var result = syncProvidedCrmsCatalog();
    return {
      ok: true,
      error: "",
      total: result.total,
      detail: result.detail,
    };
  } catch (error) {
    appendLog_("ERROR", "apiSyncProvidedCrmsCatalog fallo", {
      error: error.message,
    });
    return {
      ok: false,
      error: error.message,
      total: 0,
      detail: [],
    };
  }
}

function apiGetSources() {
  try {
    return {
      ok: true,
      error: "",
      total: getSources().length,
      sources: getSources(),
    };
  } catch (error) {
    return {
      ok: false,
      error: error.message,
      total: 0,
      sources: [],
    };
  }
}

function apiGetPublicConfig() {
  return {
    ok: true,
    config: {
      appTitle: CC_CONFIG.APP_TITLE,
      projectName: CC_CONFIG.PROJECT_NAME,
      brand: CC_CONFIG.BRAND,
      localAi: {
        enabled: CC_CONFIG.LOCAL_AI.ENABLED,
        mode: CC_CONFIG.LOCAL_AI.MODE,
        available: isLocalAiAvailable_(),
        retryMinutes: CC_CONFIG.LOCAL_AI.RETRY_MINUTES,
      },
    },
  };
}

function apiRunCentralAudit() {
  try {
    var report = runCentralSpreadsheetAudit();
    return {
      ok: true,
      error: "",
      report: report,
    };
  } catch (error) {
    return {
      ok: false,
      error: error.message,
    };
  }
}

function apiRunProvidedCrmsAudit() {
  try {
    var report = runProvidedCrmsAudit();
    return {
      ok: true,
      error: "",
      report: report,
    };
  } catch (error) {
    return {
      ok: false,
      error: error.message,
    };
  }
}
