// FinInsight Technical Dashboard Client Logic
// Token retained strictly in JavaScript memory; never persisted to storage, URLs, or console.

(function () {
  'use strict';

  // In-memory authentication state
  let sessionToken = null;
  let currentUser = null;
  let currentEntitlements = null;

  // DOM Elements
  const screenLogin = document.getElementById('screen-login');
  const workspace = document.getElementById('workspace');
  const formLogin = document.getElementById('form-login');
  const inputEmail = document.getElementById('input-email');
  const inputPassword = document.getElementById('input-password');
  const loginError = document.getElementById('login-error');
  const btnLogout = document.getElementById('btn-logout');

  const userDisplay = document.getElementById('user-display');
  const planBadge = document.getElementById('plan-badge');
  const quotaDisplay = document.getElementById('quota-display');
  const alertBanner = document.getElementById('alert-banner');
  const alertStatus = document.getElementById('alert-status');
  const alertMessage = document.getElementById('alert-message');

  // Navigation
  const navBtns = {
    f1: document.getElementById('nav-f1'),
    f2: document.getElementById('nav-f2'),
    f3: document.getElementById('nav-f3'),
  };
  const screens = {
    f1: document.getElementById('screen-f1'),
    f2: document.getElementById('screen-f2'),
    f3: document.getElementById('screen-f3'),
  };

  // Feature 1 DOM
  const btnLoadF1 = document.getElementById('btn-load-f1');
  const f1Meta = document.getElementById('f1-meta');
  const f1Content = document.getElementById('f1-content');
  const f1Regime = document.getElementById('f1-regime');
  const f1Ar = document.getElementById('f1-ar');
  const f1ArDelta = document.getElementById('f1-ar-delta');
  const f1SigCount = document.getElementById('f1-sig-count');
  const f1MeanCorr = document.getElementById('f1-mean-corr');
  const f1Seed = document.getElementById('f1-seed');
  const f1Params = document.getElementById('f1-params');
  const f1PairsBody = document.getElementById('f1-pairs-body');

  // Feature 2 DOM
  const btnLoadF2 = document.getElementById('btn-load-f2');
  const f2Meta = document.getElementById('f2-meta');
  const f2Content = document.getElementById('f2-content');
  const f2CompaniesSummary = document.getElementById('f2-companies-summary');
  const f2RulesBody = document.getElementById('f2-rules-body');

  // Feature 3 DOM
  const formF3Upload = document.getElementById('form-f3-upload');
  const inputF3Csv = document.getElementById('input-f3-csv');
  const checkConsent = document.getElementById('check-consent');
  const f3Content = document.getElementById('f3-content');
  const f3SyntheticBanner = document.getElementById('f3-synthetic-banner');
  const f3ProcessLabel = document.getElementById('f3-process-label');
  const f3Xirr = document.getElementById('f3-xirr');
  const f3TotalCost = document.getElementById('f3-total-cost');
  const f3MarketValue = document.getElementById('f3-market-value');
  const f3RealizedPnl = document.getElementById('f3-realized-pnl');
  const f3UnrealizedPnl = document.getElementById('f3-unrealized-pnl');
  const f3BenchmarkBody = document.getElementById('f3-benchmark-body');
  const f3Hhi = document.getElementById('f3-hhi');
  const f3Turnover = document.getElementById('f3-turnover');
  const f3Mdd = document.getElementById('f3-mdd');
  const f3Disp = document.getElementById('f3-disp');
  const f3InstSection = document.getElementById('f3-inst-section');
  const f3Beta = document.getElementById('f3-beta');
  const f3Alpha = document.getElementById('f3-alpha');
  const f3Te = document.getElementById('f3-te');
  const f3Ir = document.getElementById('f3-ir');
  const f3ReviewText = document.getElementById('f3-review-text');
  const f3Disclaimer = document.getElementById('f3-disclaimer');
  const f3Params = document.getElementById('f3-params');

  function showAlert(status, message, type) {
    alertStatus.textContent = String(status);
    alertMessage.textContent = String(message);
    alertBanner.className = 'alert-box';
    if (type === 'upgrade' || status === 402) {
      alertBanner.classList.add('alert-upgrade');
    } else if (type === 'ok' || status === 200) {
      alertBanner.classList.add('alert-ok');
    }
    alertBanner.style.display = 'block';
  }

  function hideAlert() {
    alertBanner.style.display = 'none';
  }

  async function apiFetch(url, options = {}) {
    const headers = options.headers || {};
    if (sessionToken) {
      headers['Authorization'] = 'Bearer ' + sessionToken;
    }
    options.headers = headers;

    const res = await fetch(url, options);
    let payload = null;
    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      payload = await res.json();
    } else {
      payload = await res.text();
    }

    if (!res.ok) {
      handleApiError(res.status, payload);
      const err = new Error('HTTP ' + res.status);
      err.status = res.status;
      err.payload = payload;
      throw err;
    }

    return payload;
  }

  function handleApiError(status, payload) {
    let msg = 'Unexpected error';
    if (payload && payload.detail) {
      if (typeof payload.detail === 'object') {
        msg = payload.detail.message || payload.detail.code || JSON.stringify(payload.detail);
      } else {
        msg = payload.detail;
      }
    } else if (payload && payload.error && payload.error.message) {
      msg = payload.error.message;
    }

    if (status === 402) {
      showAlert(402, 'UPGRADE REQUIRED: ' + msg, 'upgrade');
    } else if (status === 403) {
      showAlert(403, 'ACCESS DENIED: ' + msg, 'error');
    } else if (status === 429) {
      let resetInfo = '';
      if (payload && payload.detail && payload.detail.reset_time) {
        resetInfo = ' (Resets at: ' + payload.detail.reset_time + ')';
      } else if (payload && payload.reset_time) {
        resetInfo = ' (Resets at: ' + payload.reset_time + ')';
      }
      showAlert(429, 'QUOTA EXCEEDED: ' + msg + resetInfo, 'upgrade');
    } else {
      showAlert(status, 'HTTP ERROR: ' + msg, 'error');
    }
  }

  // Authentication
  formLogin.addEventListener('submit', async function (e) {
    e.preventDefault();
    loginError.textContent = '';
    hideAlert();

    const email = inputEmail.value.trim();
    const password = inputPassword.value;

    try {
      const res = await fetch('/api/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, password: password }),
      });

      const data = await res.json().catch(function () { return {}; });
      if (!res.ok) {
        const msg = (data && data.detail && data.detail.message) ||
                    (data && data.error && data.error.message) ||
                    ('Authentication failed (HTTP ' + res.status + ')');
        loginError.textContent = msg;
        return;
      }

      sessionToken = data.access_token;
      inputPassword.value = '';
      await loadSession();
    } catch (err) {
      loginError.textContent = 'Network failure: unable to reach server (' + (err.message || 'connection error') + ')';
    }
  });

  btnLogout.addEventListener('click', function () {
    sessionToken = null;
    currentUser = null;
    currentEntitlements = null;
    screenLogin.classList.add('active');
    screenLogin.style.display = 'block';
    workspace.style.display = 'none';
    btnLogout.style.display = 'none';
    userDisplay.textContent = 'UNAUTHENTICATED';
    planBadge.textContent = 'PLAN: NONE';
    quotaDisplay.textContent = 'QUOTAS: --';
    hideAlert();
  });

  async function loadSession() {
    try {
      currentUser = await apiFetch('/api/auth/me');
      currentEntitlements = await apiFetch('/api/entitlements');

      userDisplay.textContent = currentUser.email + ' [' + currentUser.segment.toUpperCase() + ']';
      planBadge.textContent = 'PLAN: ' + currentUser.plan.toUpperCase();

      const quotaParts = [];
      if (currentEntitlements && currentEntitlements.features) {
        for (const [fKey, fVal] of Object.entries(currentEntitlements.features)) {
          if (fVal.remaining_quota !== null && fVal.remaining_quota !== undefined) {
            quotaParts.push(fKey.replace('feature', 'F') + ': ' + fVal.remaining_quota + ' left');
          } else if (fVal.decision === 'full') {
            quotaParts.push(fKey.replace('feature', 'F') + ': unlimited');
          } else if (fVal.status === 402 || fVal.status === 403) {
            quotaParts.push(fKey.replace('feature', 'F') + ': locked');
          }
        }
      }
      quotaDisplay.textContent = quotaParts.length > 0 ? quotaParts.join(' | ') : 'NO QUOTAS';

      screenLogin.classList.remove('active');
      screenLogin.style.display = 'none';
      workspace.style.display = 'block';
      btnLogout.style.display = 'inline-block';
      switchScreen('f1');
    } catch (err) {
      sessionToken = null;
      screenLogin.classList.add('active');
      screenLogin.style.display = 'block';
      workspace.style.display = 'none';
    }
  }

  // Screen Switching
  function switchScreen(key) {
    hideAlert();
    for (const [k, btn] of Object.entries(navBtns)) {
      if (k === key) {
        btn.classList.add('active');
        screens[k].classList.add('active');
        screens[k].style.display = 'block';
      } else {
        btn.classList.remove('active');
        screens[k].classList.remove('active');
        screens[k].style.display = 'none';
      }
    }
  }

  navBtns.f1.addEventListener('click', () => switchScreen('f1'));
  navBtns.f2.addEventListener('click', () => switchScreen('f2'));
  navBtns.f3.addEventListener('click', () => switchScreen('f3'));

  // Feature 1 Handler
  btnLoadF1.addEventListener('click', async function () {
    hideAlert();
    try {
      const data = await apiFetch('/f1/demo');
      f1Meta.textContent = 'As-of: ' + (data.as_of || '--') + ' | Code: ' + (data.code_version || '--');

      f1Regime.textContent = String(data.regime_flag || 'none').toUpperCase();
      f1Regime.className = 'm-value ' + (data.regime_flag === 'none' ? 'ok' : 'warn');

      f1Ar.textContent = typeof data.absorption_ratio === 'number' ? data.absorption_ratio.toFixed(4) : '--';
      f1ArDelta.textContent = typeof data.ar_delta_std === 'number' ? data.ar_delta_std.toFixed(4) : '--';
      f1SigCount.textContent = String(data.significant_pairs_count || 0);
      f1MeanCorr.textContent = typeof data.mean_correlation === 'number' ? data.mean_correlation.toFixed(4) : '--';
      f1Seed.textContent = String(data.seed || '--');

      f1Params.textContent = JSON.stringify(data.parameters_used || {}, null, 2);

      f1PairsBody.textContent = '';
      if (Array.isArray(data.top_shifted_pairs)) {
        for (const item of data.top_shifted_pairs) {
          const tr = document.createElement('tr');

          const tdPair = document.createElement('td');
          tdPair.textContent = item.pair;
          tr.appendChild(tdPair);

          const tdBase = document.createElement('td');
          tdBase.textContent = Number(item.baseline_corr).toFixed(4);
          tr.appendChild(tdBase);

          const tdCurr = document.createElement('td');
          tdCurr.textContent = Number(item.current_corr).toFixed(4);
          tr.appendChild(tdCurr);

          const tdFr = document.createElement('td');
          tdFr.textContent = Number(item.fr_adjusted_corr).toFixed(4);
          tr.appendChild(tdFr);

          const tdP = document.createElement('td');
          tdP.textContent = Number(item.p_value).toFixed(4);
          tr.appendChild(tdP);

          const tdQ = document.createElement('td');
          tdQ.textContent = Number(item.q_value).toFixed(4);
          tr.appendChild(tdQ);

          f1PairsBody.appendChild(tr);
        }
      }

      f1Content.style.display = 'block';
    } catch (err) {
      f1Content.style.display = 'none';
      var errDetail = (err.payload && err.payload.error && err.payload.error.message) ||
                      (err.payload && err.payload.detail && (err.payload.detail.message || err.payload.detail)) ||
                      err.message || 'Request failed';
      f1Meta.textContent = 'STATUS: ' + (err.status ? 'HTTP ' + err.status : 'FAIL') + ' - ' + errDetail;
      f1Meta.className = 'meta-label m-value fail';
    }
  });

  // Feature 2 Handler
  btnLoadF2.addEventListener('click', async function () {
    hideAlert();
    try {
      const data = await apiFetch('/f2/demo');
      f2Meta.textContent = 'Audited ' + (data.companies_audited ? data.companies_audited.length : 0) + ' companies';

      // Summary blocks
      f2CompaniesSummary.textContent = '';
      if (Array.isArray(data.companies_audited)) {
        for (const comp of data.companies_audited) {
          const div = document.createElement('div');
          div.className = 'metric-block';

          const lbl = document.createElement('span');
          lbl.className = 'm-label';
          lbl.textContent = comp.symbol;
          div.appendChild(lbl);

          const val = document.createElement('span');
          val.className = 'm-value';
          val.textContent = comp.periods_audited ? comp.periods_audited.join(', ') : 'AUDITED';
          div.appendChild(val);

          f2CompaniesSummary.appendChild(div);
        }
      }

      // Rules table
      f2RulesBody.textContent = '';
      if (Array.isArray(data.checks)) {
        for (const check of data.checks) {
          const tr = document.createElement('tr');

          const tdComp = document.createElement('td');
          tdComp.textContent = check.symbol || '--';
          tr.appendChild(tdComp);

          const tdPeriod = document.createElement('td');
          tdPeriod.textContent = check.period || '--';
          tr.appendChild(tdPeriod);

          const tdRule = document.createElement('td');
          tdRule.textContent = check.rule_id + ': ' + check.rule_name;
          tr.appendChild(tdRule);

          const tdClaim = document.createElement('td');
          tdClaim.textContent = '"' + (check.claim_text || '') + '"';
          tr.appendChild(tdClaim);

          const tdMetric = document.createElement('td');
          tdMetric.textContent = check.metric_name + ' = ' + check.metric_value;
          tr.appendChild(tdMetric);

          const tdStatus = document.createElement('td');
          tdStatus.textContent = check.status;
          tdStatus.className = check.status === 'PASS' ? 'ok' : (check.status === 'FLAG' ? 'fail' : 'warn');
          tr.appendChild(tdStatus);

          const tdEvidence = document.createElement('td');
          tdEvidence.textContent = check.evidence_summary || check.rationale || '--';
          tr.appendChild(tdEvidence);

          f2RulesBody.appendChild(tr);
        }
      }

      f2Content.style.display = 'block';
    } catch (err) {
      f2Content.style.display = 'none';
      var errDetailF2 = (err.payload && err.payload.error && err.payload.error.message) ||
                        (err.payload && err.payload.detail && (err.payload.detail.message || err.payload.detail)) ||
                        err.message || 'Request failed';
      f2Meta.textContent = 'STATUS: ' + (err.status ? 'HTTP ' + err.status : 'FAIL') + ' - ' + errDetailF2;
      f2Meta.className = 'meta-label m-value fail';
    }
  });

  // Feature 3 Handler
  formF3Upload.addEventListener('submit', async function (e) {
    e.preventDefault();
    hideAlert();

    const file = inputF3Csv.files[0];
    if (!file) {
      showAlert(400, 'Please select a real trade log CSV file.', 'error');
      return;
    }

    const reader = new FileReader();
    reader.onload = async function (evt) {
      const csvText = evt.target.result;
      const mapping = {
        date: document.getElementById('col-date').value.trim(),
        symbol: document.getElementById('col-symbol').value.trim(),
        side: document.getElementById('col-side').value.trim(),
        quantity: document.getElementById('col-qty').value.trim(),
        price: document.getElementById('col-price').value.trim(),
        fees: document.getElementById('col-fees').value.trim() || null,
      };

      const payload = {
        csv_text: csvText,
        mapping: mapping,
        consent_given: checkConsent.checked,
        benchmark_symbol: 'NSEI',
      };

      try {
        const review = await apiFetch('/f3/review', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        renderF3Review(review);
        await loadSession(); // refresh quota count
      } catch (err) {
        var errDetailF3 = (err.payload && err.payload.error && err.payload.error.message) ||
                          (err.payload && err.payload.detail && (err.payload.detail.message || err.payload.detail)) ||
                          err.message || 'Request failed';
        if (err.status === 503 && errDetailF3.includes('benchmark data is not shipped')) {
          try {
            const demoReview = await apiFetch('/f3/demo');
            renderF3Review(demoReview);
            showAlert(503, 'FEATURE 3 HOSTED DEMO: ' + errDetailF3 + '. Showing precomputed demo result.', 'warn');
            return;
          } catch (demoErr) {
            // fallback
          }
        }
        f3Content.style.display = 'none';
        showAlert(err.status || 500, 'FEATURE 3 AUDIT ERROR: ' + errDetailF3, 'error');
      }
    };
    reader.readAsText(file);
  });

  function renderF3Review(review) {
    // Synthetic Demo Notice
    if (review.is_synthetic_demo || review.synthetic_label) {
      f3SyntheticBanner.style.display = 'block';
      f3SyntheticBanner.textContent = review.synthetic_label || 'SYNTHETIC DEMO LOG, not a real investor';
    } else {
      f3SyntheticBanner.style.display = 'none';
    }

    // Process Label Notice
    if (review.process_metrics && review.process_metrics.process_label) {
      f3ProcessLabel.style.display = 'block';
      f3ProcessLabel.textContent = review.process_metrics.process_label;
    } else {
      f3ProcessLabel.style.display = 'none';
    }

    // Populate Portfolio & XIRR
    f3Xirr.textContent = review.portfolio_xirr !== null ? (review.portfolio_xirr * 100).toFixed(2) + '%' : 'NO ROOT';
    f3TotalCost.textContent = 'INR ' + Number(review.portfolio.total_cost).toLocaleString();
    f3MarketValue.textContent = 'INR ' + Number(review.portfolio.total_market_value).toLocaleString();
    f3RealizedPnl.textContent = 'INR ' + Number(review.portfolio.total_realized_pnl).toLocaleString();
    f3UnrealizedPnl.textContent = 'INR ' + Number(review.portfolio.total_unrealized_pnl).toLocaleString();

    // Benchmark table
    f3BenchmarkBody.textContent = '';
    if (Array.isArray(review.benchmark_replays)) {
      for (const b of review.benchmark_replays) {
        const tr = document.createElement('tr');

        const tdBm = document.createElement('td');
        tdBm.textContent = b.benchmark_name;
        tr.appendChild(tdBm);

        const tdTerm = document.createElement('td');
        tdTerm.textContent = Number(b.terminal_value).toLocaleString();
        tr.appendChild(tdTerm);

        const tdXirr = document.createElement('td');
        tdXirr.textContent = b.xirr !== null ? (b.xirr * 100).toFixed(2) + '%' : 'NO ROOT';
        tr.appendChild(tdXirr);

        const tdShort = document.createElement('td');
        tdShort.textContent = b.partial_shortfall ? 'YES (SHORTFALL)' : 'NO';
        tdShort.className = b.partial_shortfall ? 'warn' : 'ok';
        tr.appendChild(tdShort);

        f3BenchmarkBody.appendChild(tr);
      }
    }

    // Process Metrics
    f3Hhi.textContent = Number(review.process_metrics.concentration_hhi).toFixed(4);
    f3Turnover.textContent = Number(review.process_metrics.turnover).toFixed(4);
    f3Mdd.textContent = Number(review.process_metrics.max_drawdown).toFixed(4);

    const disp = review.process_metrics.disposition_effect || {};
    f3Disp.textContent = 'PGR: ' + (disp.pgr !== undefined ? disp.pgr.toFixed(2) : '--') + ' / PLR: ' + (disp.plr !== undefined ? disp.plr.toFixed(2) : '--');

    // Institutional Metrics
    if (review.institutional_metrics) {
      f3InstSection.style.display = 'block';
      f3Beta.textContent = Number(review.institutional_metrics.beta).toFixed(4);
      f3Alpha.textContent = Number(review.institutional_metrics.alpha).toFixed(4);
      f3Te.textContent = Number(review.institutional_metrics.tracking_error).toFixed(4);
      f3Ir.textContent = Number(review.institutional_metrics.information_ratio).toFixed(4);
    } else {
      f3InstSection.style.display = 'none';
    }

    // Qualitative text and disclaimer
    f3ReviewText.textContent = review.review_text;
    f3Disclaimer.textContent = review.disclaimer;

    // Parameters
    f3Params.textContent = JSON.stringify(review.parameters_used || {}, null, 2);

    f3Content.style.display = 'block';
  }

  // Initial App State Setup
  function initApp() {
    if (sessionToken) {
      loadSession();
    } else {
      screenLogin.classList.add('active');
      screenLogin.style.display = 'block';
      workspace.style.display = 'none';
      btnLogout.style.display = 'none';
      userDisplay.textContent = 'UNAUTHENTICATED';
      planBadge.textContent = 'PLAN: NONE';
      quotaDisplay.textContent = 'QUOTAS: --';
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
  } else {
    initApp();
  }
})();

