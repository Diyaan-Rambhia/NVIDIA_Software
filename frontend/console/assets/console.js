// FinInsight Ops Console JavaScript

function setText(elementId, text) {
  const el = document.getElementById(elementId);
  if (el) {
    el.textContent = text !== null && text !== undefined ? String(text) : "-";
  }
}

function showError(elementId, errorText) {
  const el = document.getElementById(elementId);
  if (el) {
    el.textContent = errorText;
    el.style.display = "block";
  }
}

function hideError(elementId) {
  const el = document.getElementById(elementId);
  if (el) {
    el.style.display = "none";
  }
}

function updateLastUpdated() {
  const now = new Date();
  const timeStr = now.toTimeString().split(" ")[0];
  setText("last-updated", timeStr);
}

function createBadge(statusType, label) {
  const span = document.createElement("span");
  span.className = "badge badge-" + statusType;
  span.textContent = label;
  return span;
}

// ---------------------------------------------------------------------------
// Index Page Polling
// ---------------------------------------------------------------------------
async function refreshIndex() {
  hideError("index-error");
  let hasError = false;
  let errorMsg = "";

  // 1. Fetch /health
  try {
    const res = await fetch("/health");
    if (!res.ok) {
      const errBody = await res.text();
      hasError = true;
      errorMsg += "HTTP " + res.status + " on /health: " + errBody + "\n";
      const badgeContainer = document.getElementById("health-badge");
      if (badgeContainer) {
        badgeContainer.textContent = "";
        badgeContainer.appendChild(createBadge("fail", "FAIL (" + res.status + ")"));
      }
    } else {
      const data = await res.json();
      const badgeContainer = document.getElementById("health-badge");
      if (badgeContainer) {
        badgeContainer.textContent = "";
        if (data.status === "ok") {
          badgeContainer.appendChild(createBadge("ok", "OK"));
        } else {
          badgeContainer.appendChild(createBadge("warn", "WARN"));
        }
      }
    }
  } catch (err) {
    hasError = true;
    errorMsg += "Network error on /health: " + String(err) + "\n";
    const badgeContainer = document.getElementById("health-badge");
    if (badgeContainer) {
      badgeContainer.textContent = "";
      badgeContainer.appendChild(createBadge("fail", "FAIL"));
    }
  }

  // 2. Fetch /ready
  try {
    const res = await fetch("/ready");
    const data = await res.json();
    const badgeContainer = document.getElementById("ready-badge");
    if (badgeContainer) {
      badgeContainer.textContent = "";
      if (res.status === 200 && data.ready) {
        badgeContainer.appendChild(createBadge("ok", "OK"));
      } else {
        badgeContainer.appendChild(createBadge("fail", "FAIL (" + res.status + ")"));
      }
    }

    if (!res.ok) {
      hasError = true;
      errorMsg += "HTTP " + res.status + " on /ready: " + JSON.stringify(data) + "\n";
    }

    // Render checks table
    const tbody = document.getElementById("checks-table-body");
    if (tbody && data.checks) {
      tbody.textContent = "";
      // Config loaded row
      const tr1 = document.createElement("tr");
      const td1a = document.createElement("td");
      td1a.textContent = "config_loaded";
      const td1b = document.createElement("td");
      td1b.textContent = data.checks.config_loaded ? "true" : "false";
      tr1.appendChild(td1a);
      tr1.appendChild(td1b);
      tbody.appendChild(tr1);

      // Enabled groups row
      const tr2 = document.createElement("tr");
      const td2a = document.createElement("td");
      td2a.textContent = "enabled_groups";
      const td2b = document.createElement("td");
      td2b.textContent = (data.checks.enabled_groups || []).join(", ") || "(none)";
      tr2.appendChild(td2a);
      tr2.appendChild(td2b);
      tbody.appendChild(tr2);

      // Missing variables row
      const tr3 = document.createElement("tr");
      const td3a = document.createElement("td");
      td3a.textContent = "missing_variables";
      const td3b = document.createElement("td");
      const missingList = data.checks.missing || [];
      td3b.textContent = missingList.join(", ") || "(none)";
      if (missingList.length > 0) {
        td3b.style.color = "var(--status-fail)";
      }
      tr3.appendChild(td3a);
      tr3.appendChild(td3b);
      tbody.appendChild(tr3);
    }
  } catch (err) {
    hasError = true;
    errorMsg += "Network error on /ready: " + String(err) + "\n";
  }

  // 3. Fetch /ops/status
  try {
    const res = await fetch("/ops/status");
    if (!res.ok) {
      const errBody = await res.text();
      hasError = true;
      errorMsg += "HTTP " + res.status + " on /ops/status: " + errBody + "\n";
    } else {
      const data = await res.json();
      setText("status-env", data.app_env);
      setText("status-version", data.code_version);
      setText("status-python", data.python_version);
      setText("status-uptime", data.uptime_seconds + "s");
      setText("status-groups", (data.enabled_groups || []).join(", ") || "(none)");
    }
  } catch (err) {
    hasError = true;
    errorMsg += "Network error on /ops/status: " + String(err) + "\n";
  }

  if (hasError) {
    showError("index-error", errorMsg);
  }

  updateLastUpdated();
}

// ---------------------------------------------------------------------------
// Config Page Polling
// ---------------------------------------------------------------------------
async function refreshConfig() {
  hideError("config-error");
  let hasError = false;
  let errorMsg = "";

  // 1. Fetch /ops/config
  try {
    const res = await fetch("/ops/config");
    if (!res.ok) {
      const errBody = await res.text();
      hasError = true;
      errorMsg += "HTTP " + res.status + " on /ops/config: " + errBody + "\n";
    } else {
      const data = await res.json();
      setText("enabled-groups-list", (data.enabled_groups || []).join(", ") || "(none)");

      const envTbody = document.getElementById("env-table-body");
      if (envTbody && data.groups) {
        envTbody.textContent = "";
        for (const [groupName, varList] of Object.entries(data.groups)) {
          for (const item of varList) {
            const tr = document.createElement("tr");

            const tdGroup = document.createElement("td");
            tdGroup.textContent = groupName;

            const tdName = document.createElement("td");
            tdName.textContent = item.name;

            const tdReq = document.createElement("td");
            tdReq.textContent = item.required_when_enabled ? "yes" : "no";

            const tdStatus = document.createElement("td");
            if (item.present) {
              tdStatus.appendChild(createBadge("ok", "PRESENT"));
            } else if (item.group_enabled && item.required_when_enabled) {
              tdStatus.appendChild(createBadge("fail", "MISSING"));
            } else {
              tdStatus.appendChild(createBadge("warn", "ABSENT"));
            }

            tr.appendChild(tdGroup);
            tr.appendChild(tdName);
            tr.appendChild(tdReq);
            tr.appendChild(tdStatus);
            envTbody.appendChild(tr);
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
    const res = await fetch("/ops/parameters");
    if (!res.ok) {
      const errBody = await res.text();
      hasError = true;
      errorMsg += "HTTP " + res.status + " on /ops/parameters: " + errBody + "\n";
    } else {
      const data = await res.json();
      const paramsTbody = document.getElementById("params-table-body");
      if (paramsTbody && data.parameters) {
        paramsTbody.textContent = "";
        for (const [pName, pEntry] of Object.entries(data.parameters)) {
          const tr = document.createElement("tr");

          const tdName = document.createElement("td");
          tdName.textContent = pName;

          const tdType = document.createElement("td");
          tdType.textContent = pEntry.type;

          const tdDef = document.createElement("td");
          tdDef.textContent = String(pEntry.default);

          const tdMin = document.createElement("td");
          tdMin.textContent = pEntry.min !== null ? String(pEntry.min) : "-";

          const tdMax = document.createElement("td");
          tdMax.textContent = pEntry.max !== null ? String(pEntry.max) : "-";

          const tdUnit = document.createElement("td");
          tdUnit.textContent = pEntry.unit;

          const tdOver = document.createElement("td");
          tdOver.textContent = pEntry.override_allowed ? "yes" : "no";

          tr.appendChild(tdName);
          tr.appendChild(tdType);
          tr.appendChild(tdDef);
          tr.appendChild(tdMin);
          tr.appendChild(tdMax);
          tr.appendChild(tdUnit);
          tr.appendChild(tdOver);
          paramsTbody.appendChild(tr);
        }
      }
    }
  } catch (err) {
    hasError = true;
    errorMsg += "Network error on /ops/parameters: " + String(err) + "\n";
  }

  if (hasError) {
    showError("config-error", errorMsg);
  }

  updateLastUpdated();
}

function startPolling(pageType) {
  const handler = pageType === "config" ? refreshConfig : refreshIndex;
  handler();
  setInterval(handler, 5000);
}
