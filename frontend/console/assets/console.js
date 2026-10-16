// Strict rules: no external URLs, no raw server HTML insertion, no tokens in URLs or logs.

var inMemoryToken = null;
var pollIntervalId = null;

function setText(elementId, text) {
  var el = document.getElementById(elementId);
  if (el) {
    el.textContent = text !== null && text !== undefined ? String(text) : "-";
  }
}

function showError(elementId, errorText) {
  var el = document.getElementById(elementId);
  if (el) {
    el.textContent = errorText;
    el.style.display = "block";
  }
}

function hideError(elementId) {
  var el = document.getElementById(elementId);
  if (el) {
    el.style.display = "none";
  }
}

function updateLastUpdated() {
  var now = new Date();
  var timeStr = now.toTimeString().split(" ")[0];
  setText("last-updated", timeStr);
}

function createBadge(statusType, label) {
  var span = document.createElement("span");
  span.className = "badge badge-" + statusType;
  span.textContent = label;
  return span;
}

function getAuthHeaders() {
  var headers = {};
  if (inMemoryToken) {
    headers["Authorization"] = "Bearer " + inMemoryToken;
  }
  return headers;
}

function showLogin() {
  var panel = document.getElementById("login-panel");
  if (panel) {
    panel.style.display = "block";
  }
}

function hideLogin() {
  var panel = document.getElementById("login-panel");
  if (panel) {
    panel.style.display = "none";
  }
  hideError("login-error");
}

async function handleLogin(e, pageType) {
  e.preventDefault();
  hideError("login-error");

  var emailEl = document.getElementById("login-email");
  var passEl = document.getElementById("login-password");
  if (!emailEl || !passEl) {
    return;
  }

  var email = emailEl.value.trim();
  var password = passEl.value;

  try {
    var res = await fetch("/api/auth/token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email, password: password })
    });

    if (!res.ok) {
      var errData = await res.json().catch(function() { return {}; });
      var msg = (errData && errData.error && errData.error.message) ||
                (errData && errData.detail && errData.detail.message) ||
                ("HTTP " + res.status);
      showError("login-error", "Authentication failed: " + msg);
      return;
    }

    var data = await res.json();
    inMemoryToken = data.access_token;
    passEl.value = "";
    hideLogin();

    if (pageType === "index") {
      refreshIndex();
    } else if (pageType === "config") {
      refreshConfig();
    }
  } catch (err) {
    showError("login-error", "Network error during authentication: " + String(err));
  }
}

// ---------------------------------------------------------------------------
// Index Page Refresh
// ---------------------------------------------------------------------------
async function refreshIndex() {
  hideError("index-error");
  var hasError = false;
  var errorMsg = "";

  // 1. Fetch /health (public)
  try {
    var resHealth = await fetch("/health");
    var healthBadge = document.getElementById("health-badge");
    if (!resHealth.ok) {
      hasError = true;
      errorMsg += "HTTP " + resHealth.status + " on /health\n";
      if (healthBadge) {
        healthBadge.textContent = "";
        healthBadge.appendChild(createBadge("fail", "FAIL (" + resHealth.status + ")"));
      }
    } else {
      var dataHealth = await resHealth.json();
      if (healthBadge) {
        healthBadge.textContent = "";
        if (dataHealth.status === "healthy") {
          healthBadge.appendChild(createBadge("ok", "HEALTHY"));
        } else {
          healthBadge.appendChild(createBadge("warn", String(dataHealth.status).toUpperCase()));
        }
      }
    }
  } catch (err) {
    hasError = true;
    errorMsg += "Network error on /health: " + String(err) + "\n";
  }

  // 2. Fetch /ready (public)
  try {
    var resReady = await fetch("/ready");
    var readyBadge = document.getElementById("ready-badge");
    var tbody = document.getElementById("checks-table-body");

    if (!resReady.ok) {
      hasError = true;
      errorMsg += "HTTP " + resReady.status + " on /ready\n";
      if (readyBadge) {
        readyBadge.textContent = "";
        readyBadge.appendChild(createBadge("fail", "FAIL (" + resReady.status + ")"));
      }
    } else {
      var dataReady = await resReady.json();
      if (readyBadge) {
        readyBadge.textContent = "";
        if (dataReady.status === "ready") {
          readyBadge.appendChild(createBadge("ok", "READY"));
        } else {
          readyBadge.appendChild(createBadge("warn", String(dataReady.status).toUpperCase()));
        }
      }

      if (tbody && dataReady.checks) {
        tbody.textContent = "";
        var checkKeys = Object.keys(dataReady.checks);
        for (var i = 0; i < checkKeys.length; i++) {
          var k = checkKeys[i];
          var val = dataReady.checks[k];
          var tr = document.createElement("tr");
          var tdKey = document.createElement("td");
          tdKey.textContent = k;
          var tdVal = document.createElement("td");

          if (val === true) {
            tdVal.appendChild(createBadge("ok", "PASS"));
          } else if (val === false) {
            tdVal.appendChild(createBadge("fail", "FAIL"));
          } else {
            tdVal.textContent = String(val);
          }

          tr.appendChild(tdKey);
          tr.appendChild(tdVal);
          tbody.appendChild(tr);
        }
      }
    }
  } catch (err) {
    hasError = true;
    errorMsg += "Network error on /ready: " + String(err) + "\n";
  }

  // 3. Fetch /ops/status (admin)
  try {
    var resStatus = await fetch("/ops/status", { headers: getAuthHeaders() });
    if (resStatus.status === 401 || resStatus.status === 403) {
      showLogin();
      hasError = true;
      errorMsg += "HTTP " + resStatus.status + " on /ops/status (admin authentication required)\n";
      setText("status-env", "LOGIN REQUIRED");
      setText("status-version", "LOGIN REQUIRED");
      setText("status-python", "LOGIN REQUIRED");
      setText("status-uptime", "LOGIN REQUIRED");
      setText("status-groups", "LOGIN REQUIRED");
    } else if (!resStatus.ok) {
      hasError = true;
      errorMsg += "HTTP " + resStatus.status + " on /ops/status\n";
    } else {
      var dataStatus = await resStatus.json();
      setText("status-env", dataStatus.app_env);
      setText("status-version", dataStatus.code_version);
      setText("status-python", dataStatus.python_version);
      setText("status-uptime", dataStatus.uptime_seconds + "s");

      var groupsStr = Array.isArray(dataStatus.enabled_groups)
        ? dataStatus.enabled_groups.join(", ")
        : "-";
      setText("status-groups", groupsStr);
    }
  } catch (err) {
    hasError = true;
    errorMsg += "Network error on /ops/status: " + String(err) + "\n";
  }

  // 4. Fetch /ops/activity/events (admin)
  try {
    var resEvents = await fetch("/ops/activity/events", { headers: getAuthHeaders() });
    var eventsTbody = document.getElementById("events-table-body");
    if (resEvents.status === 401 || resEvents.status === 403) {
      showLogin();
      if (eventsTbody) {
        eventsTbody.textContent = "";
        var trEEmpty = document.createElement("tr");
        var tdEEmpty = document.createElement("td");
        tdEEmpty.colSpan = 6;
        tdEEmpty.textContent = "LOGIN REQUIRED: Admin authentication required to view activity events";
        tdEEmpty.style.color = "var(--accent)";
        trEEmpty.appendChild(tdEEmpty);
        eventsTbody.appendChild(trEEmpty);
      }
    } else if (!resEvents.ok) {
      hasError = true;
      errorMsg += "HTTP " + resEvents.status + " on /ops/activity/events\n";
    } else if (eventsTbody) {
      var eventsData = await resEvents.json();
      eventsTbody.textContent = "";
      if (!eventsData || eventsData.length === 0) {
        var trEmpty = document.createElement("tr");
        var tdEmpty = document.createElement("td");
        tdEmpty.colSpan = 6;
        tdEmpty.textContent = "no rows";
        trEmpty.appendChild(tdEmpty);
        eventsTbody.appendChild(trEmpty);
      } else {
        for (var eIdx = 0; eIdx < eventsData.length; eIdx++) {
          var ev = eventsData[eIdx];
          var trEv = document.createElement("tr");

          var tdId = document.createElement("td");
          tdId.textContent = ev.id || "-";
          var tdTs = document.createElement("td");
          tdTs.textContent = ev.ts || "-";
          var tdKind = document.createElement("td");
          tdKind.textContent = ev.kind || "-";
          var tdSubj = document.createElement("td");
          tdSubj.textContent = ev.subject || "-";
          var tdStat = document.createElement("td");
          tdStat.textContent = ev.status || "-";
          var tdDur = document.createElement("td");
          tdDur.textContent = ev.duration_ms !== null && ev.duration_ms !== undefined ? String(ev.duration_ms) : "-";

          trEv.appendChild(tdId);
          trEv.appendChild(tdTs);
          trEv.appendChild(tdKind);
          trEv.appendChild(tdSubj);
          trEv.appendChild(tdStat);
          trEv.appendChild(tdDur);
          eventsTbody.appendChild(trEv);
        }
      }
    }
  } catch (err) {
    hasError = true;
    errorMsg += "Network error on /ops/activity/events: " + String(err) + "\n";
  }

  // 5. Fetch /ops/activity/llm (admin)
  try {
    var resLlm = await fetch("/ops/activity/llm", { headers: getAuthHeaders() });
    var llmTbody = document.getElementById("llm-table-body");
    if (resLlm.status === 401 || resLlm.status === 403) {
      showLogin();
      if (llmTbody) {
        llmTbody.textContent = "";
        var trLlmAuth = document.createElement("tr");
        var tdLlmAuth = document.createElement("td");
        tdLlmAuth.colSpan = 9;
        tdLlmAuth.textContent = "LOGIN REQUIRED: Admin authentication required to view LLM runtime usage";
        tdLlmAuth.style.color = "var(--accent)";
        trLlmAuth.appendChild(tdLlmAuth);
        llmTbody.appendChild(trLlmAuth);
      }
    } else if (!resLlm.ok) {
      hasError = true;
      errorMsg += "HTTP " + resLlm.status + " on /ops/activity/llm\n";
    } else if (llmTbody) {
      var llmData = await resLlm.json();
      llmTbody.textContent = "";
      if (!llmData || llmData.length === 0) {
        var trLlmEmpty = document.createElement("tr");
        var tdLlmEmpty = document.createElement("td");
        tdLlmEmpty.colSpan = 9;
        tdLlmEmpty.textContent = "no rows";
        trLlmEmpty.appendChild(tdLlmEmpty);
        llmTbody.appendChild(trLlmEmpty);
      } else {
        for (var lIdx = 0; lIdx < llmData.length; lIdx++) {
          var row = llmData[lIdx];
          var trLlm = document.createElement("tr");

          var tdLId = document.createElement("td");
          tdLId.textContent = row.id || "-";
          var tdLTs = document.createElement("td");
          tdLTs.textContent = row.ts || "-";
          var tdLRoute = document.createElement("td");
          tdLRoute.textContent = row.route || "-";
          var tdLAlias = document.createElement("td");
          tdLAlias.textContent = row.alias || "-";
          var tdLModel = document.createElement("td");
          tdLModel.textContent = row.model_id || "-";
          var tdLIn = document.createElement("td");
          tdLIn.textContent = String(row.input_tokens || 0);
          var tdLOut = document.createElement("td");
          tdLOut.textContent = String(row.output_tokens || 0);
          var tdLCost = document.createElement("td");
          tdLCost.textContent = row.est_cost_usd !== undefined ? "$" + row.est_cost_usd.toFixed(6) : "-";
          var tdLHit = document.createElement("td");
          tdLHit.textContent = row.cache_hit ? "HIT" : "MISS";

          trLlm.appendChild(tdLId);
          trLlm.appendChild(tdLTs);
          trLlm.appendChild(tdLRoute);
          trLlm.appendChild(tdLAlias);
          trLlm.appendChild(tdLModel);
          trLlm.appendChild(tdLIn);
          trLlm.appendChild(tdLOut);
          trLlm.appendChild(tdLCost);
          trLlm.appendChild(tdLHit);
          llmTbody.appendChild(trLlm);
        }
      }
    }
  } catch (err) {
    hasError = true;
    errorMsg += "Network error on /ops/activity/llm: " + String(err) + "\n";
  }

  updateLastUpdated();
  if (hasError) {
    showError("index-error", errorMsg);
  }
}

// ---------------------------------------------------------------------------
// Config Page Refresh
// ---------------------------------------------------------------------------
async function refreshConfig() {
  hideError("config-error");
  var hasError = false;
  var errorMsg = "";

  // 1. Fetch /ops/config
  try {
    var resConfig = await fetch("/ops/config", { headers: getAuthHeaders() });
    var tbodyEnv = document.getElementById("env-table-body");
    if (resConfig.status === 401 || resConfig.status === 403) {
      showLogin();
      setText("enabled-groups-list", "LOGIN REQUIRED (admin auth needed)");
      if (tbodyEnv) {
        tbodyEnv.textContent = "";
        var trEnvAuth = document.createElement("tr");
        var tdEnvAuth = document.createElement("td");
        tdEnvAuth.colSpan = 4;
        tdEnvAuth.textContent = "LOGIN REQUIRED: Admin authentication required to view environment config";
        tdEnvAuth.style.color = "var(--accent)";
        trEnvAuth.appendChild(tdEnvAuth);
        tbodyEnv.appendChild(trEnvAuth);
      }
    } else if (!resConfig.ok) {
      hasError = true;
      errorMsg += "HTTP " + resConfig.status + " on /ops/config\n";
    } else {
      var dataConfig = await resConfig.json();
      var groupsListStr = Array.isArray(dataConfig.enabled_groups)
        ? dataConfig.enabled_groups.join(", ")
        : "-";
      setText("enabled-groups-list", groupsListStr);

      var tbodyEnv = document.getElementById("env-table-body");
      if (tbodyEnv && dataConfig.groups) {
        tbodyEnv.textContent = "";
        var gKeys = Object.keys(dataConfig.groups);
        for (var gi = 0; gi < gKeys.length; gi++) {
          var groupName = gKeys[gi];
          var vars = dataConfig.groups[groupName];
          for (var vi = 0; vi < vars.length; vi++) {
            var v = vars[vi];
            var tr = document.createElement("tr");

            var tdGroup = document.createElement("td");
            tdGroup.textContent = groupName;
            var tdName = document.createElement("td");
            tdName.textContent = v.name;
            var tdReq = document.createElement("td");
            tdReq.textContent = v.required_when_enabled ? "YES" : "NO";

            var tdStatus = document.createElement("td");
            if (v.present) {
              tdStatus.appendChild(createBadge("ok", "PRESENT"));
            } else if (v.required_when_enabled && v.group_enabled) {
              tdStatus.appendChild(createBadge("fail", "MISSING"));
            } else {
              tdStatus.appendChild(createBadge("warn", "ABSENT"));
            }

            tr.appendChild(tdGroup);
            tr.appendChild(tdName);
            tr.appendChild(tdReq);
            tr.appendChild(tdStatus);
            tbodyEnv.appendChild(tr);
          }
        }
      }
    }
  } catch (err) {
    hasError = true;
    errorMsg += "Network error on /ops/config: " + String(err) + "\n";
  }

  // 2. Fetch /ops/parameters
  try {
    var resParams = await fetch("/ops/parameters", { headers: getAuthHeaders() });
    var tbodyParams = document.getElementById("params-table-body");
    if (resParams.status === 401 || resParams.status === 403) {
      showLogin();
      if (tbodyParams) {
        tbodyParams.textContent = "";
        var trParamAuth = document.createElement("tr");
        var tdParamAuth = document.createElement("td");
        tdParamAuth.colSpan = 7;
        tdParamAuth.textContent = "LOGIN REQUIRED: Admin authentication required to view system parameters";
        tdParamAuth.style.color = "var(--accent)";
        trParamAuth.appendChild(tdParamAuth);
        tbodyParams.appendChild(trParamAuth);
      }
    } else if (!resParams.ok) {
      hasError = true;
      errorMsg += "HTTP " + resParams.status + " on /ops/parameters\n";
    } else {
      var dataParams = await resParams.json();
      var tbodyParams = document.getElementById("params-table-body");
      if (tbodyParams && dataParams.parameters) {
        tbodyParams.textContent = "";
        var pKeys = Object.keys(dataParams.parameters);
        for (var pi = 0; pi < pKeys.length; pi++) {
          var paramName = pKeys[pi];
          var p = dataParams.parameters[paramName];
          var trP = document.createElement("tr");

          var tdPName = document.createElement("td");
          tdPName.textContent = paramName;
          var tdPType = document.createElement("td");
          tdPType.textContent = p.type || "-";
          var tdPDef = document.createElement("td");
          tdPDef.textContent = p.default !== undefined ? String(p.default) : "-";
          var tdPMin = document.createElement("td");
          tdPMin.textContent = p.min !== undefined && p.min !== null ? String(p.min) : "-";
          var tdPMax = document.createElement("td");
          tdPMax.textContent = p.max !== undefined && p.max !== null ? String(p.max) : "-";
          var tdPUnit = document.createElement("td");
          tdPUnit.textContent = p.unit || "-";
          var tdPOvr = document.createElement("td");
          tdPOvr.textContent = p.override_allowed ? "YES" : "NO";

          trP.appendChild(tdPName);
          trP.appendChild(tdPType);
          trP.appendChild(tdPDef);
          trP.appendChild(tdPMin);
          trP.appendChild(tdPMax);
          trP.appendChild(tdPUnit);
          trP.appendChild(tdPOvr);
          tbodyParams.appendChild(trP);
        }
      }
    }
  } catch (err) {
    hasError = true;
    errorMsg += "Network error on /ops/parameters: " + String(err) + "\n";
  }

  updateLastUpdated();
  if (hasError) {
    showError("config-error", errorMsg);
  }
}

// ---------------------------------------------------------------------------
// Console Initialization
// ---------------------------------------------------------------------------
function initConsole(pageType) {
  var form = document.getElementById("login-form");
  if (form) {
    form.addEventListener("submit", function(e) {
      handleLogin(e, pageType);
    });
  }

  if (!inMemoryToken) {
    showLogin();
  }

  if (pageType === "index") {
    refreshIndex();
  } else if (pageType === "config") {
    refreshConfig();
  }
}
