(function () {

  function errorMessage(value, fallback = 'The request could not be completed.') {
    if (value == null) return fallback;
    if (typeof value === 'string') return value.trim() || fallback;
    if (value instanceof Error) return errorMessage(value.message, fallback);
    if (Array.isArray(value)) {
      const messages = value.map(item => errorMessage(item, '')).filter(Boolean);
      return messages.length ? messages.join('; ') : fallback;
    }
    if (typeof value === 'object') {
      if (typeof value.msg === 'string') {
        const location = Array.isArray(value.loc) ? value.loc.filter(x => x !== 'body').join(' → ') : '';
        return `${location ? `${location}: ` : ''}${value.msg}`;
      }
      for (const key of ['message', 'detail', 'error', 'reason', 'description', 'errors']) {
        if (value[key] != null) {
          const message = errorMessage(value[key], '');
          if (message) return message;
        }
      }
      try {
        const serialised = JSON.stringify(value);
        if (serialised && serialised !== '{}') return serialised;
      } catch (_) {}
    }
    const text = String(value || '').trim();
    return text && text !== '[object Object]' ? text : fallback;
  }
  async function readResponse(response) {
    const text = await response.text();
    if (!text) return {};
    try { return JSON.parse(text); } catch (_) { return {detail: text}; }
  }
  const STORAGE_KEY = 'articleready_paid_access_v1';
  const DEVELOPER_STORAGE_KEY = 'articleready_developer_access_v1';
  const PLAN_NAMES = {
    article_ideas: 'Article Ideas',
    stage1_article: 'Stage 1 Article Builder',
    standard_full_article: 'Standard Full Article',
    long_article_plus: 'Long Article Plus',
    review_conceptual_scoping: 'Review / Conceptual / Scoping Article',
    article_revision: 'Article Polishing and Revision',
    reviewer_comment_revision: 'Reviewer Comment Revision',
    extra_revision_pass: 'Extra Revision Pass',
  };


  function readDeveloperAccess() {
    try {
      const value = JSON.parse(localStorage.getItem(DEVELOPER_STORAGE_KEY) || '{}') || {};
      if (!value.developer_token || !value.expires_at || Number(value.expires_at) * 1000 <= Date.now()) {
        localStorage.removeItem(DEVELOPER_STORAGE_KEY);
        return null;
      }
      return value;
    } catch (_) {
      localStorage.removeItem(DEVELOPER_STORAGE_KEY);
      return null;
    }
  }
  function rememberDeveloperAccess(access) {
    if (!access?.developer_token || !access?.expires_at) return;
    localStorage.setItem(DEVELOPER_STORAGE_KEY, JSON.stringify({
      developer_token: access.developer_token,
      expires_at: access.expires_at,
      email: access.email || '',
      saved_at: new Date().toISOString(),
    }));
  }
  function clearDeveloperAccess() { localStorage.removeItem(DEVELOPER_STORAGE_KEY); }
  async function developerStatus() {
    const record = readDeveloperAccess();
    if (!record) return {ok: false, active: false, message: 'Developer access is inactive.'};
    const response = await fetch('/api/developer/status', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', Accept: 'application/json'},
      credentials: 'same-origin',
      cache: 'no-store',
      body: JSON.stringify({developer_token: record.developer_token}),
    });
    const data = await readResponse(response);
    if (!response.ok || !data.active) {
      clearDeveloperAccess();
      return {ok: false, active: false, message: errorMessage(data.detail ?? data, 'Developer access is inactive or expired.')};
    }
    return data;
  }

  function readStore() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') || {}; } catch (_) { return {}; }
  }
  function writeStore(store) { localStorage.setItem(STORAGE_KEY, JSON.stringify(store || {})); }
  function remember(access) {
    if (!access || !access.purchase_id || !access.access_token) return;
    const store = readStore();
    const planKey = access.plan_key || access.plan?.plan_key || 'latest';
    const record = {
      purchase_id: access.purchase_id,
      access_token: access.access_token,
      plan_key: planKey,
      provider: access.provider || '',
      saved_at: new Date().toISOString(),
    };
    store.latest = record;
    store[planKey] = record;
    writeStore(store);
  }
  function credentials(preferredPlan) {
    const store = readStore();
    if (preferredPlan) return store[preferredPlan] || null;
    return store.latest || null;
  }
  function credentialsByPurchaseId(purchaseId) {
    const wanted = String(purchaseId || '').trim();
    if (!wanted) return null;
    const store = readStore();
    for (const record of Object.values(store)) {
      if (record && typeof record === 'object' && String(record.purchase_id || '') === wanted && record.access_token) return record;
    }
    return null;
  }
  async function entitlementStatus(record) {
    if (!record?.purchase_id || !record?.access_token) return {ok: false, active: false, message: 'Paid access credentials are unavailable on this device.'};
    const response = await fetch('/api/payments/entitlement-status', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({purchase_id: record.purchase_id, access_token: record.access_token}),
    });
    const data = await readResponse(response);
    if (!response.ok) return {ok: false, active: false, message: errorMessage(data.detail ?? data, 'Paid access could not be checked.')};
    return data;
  }
  function paymentHeaders(preferredPlan) {
    const headers = {};
    const developer = readDeveloperAccess();
    if (developer?.developer_token) headers['x-articleready-developer-token'] = developer.developer_token;
    const c = credentials(preferredPlan);
    if (c) {
      headers['x-articleready-purchase-id'] = c.purchase_id;
      headers['x-articleready-access-token'] = c.access_token;
    }
    return headers;
  }
  async function authorisedFetch(input, init = {}, preferredPlan = '') {
    const headers = new Headers(init.headers || {});
    const accessHeaders = paymentHeaders(preferredPlan);
    Object.entries(accessHeaders).forEach(([name, value]) => {
      if (value) headers.set(name, value);
    });
    return fetch(input, {
      ...init,
      headers,
      credentials: init.credentials || 'same-origin',
      cache: init.cache || 'no-store',
    });
  }
  function workIdFromPage() {
    const title = document.getElementById('articleTitle')?.value || document.getElementById('researchArea')?.value || document.title || 'general';
    return String(title).trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 80) || 'general';
  }
  function ensureModal() {
    let modal = document.getElementById('arPaymentModal');
    if (modal) return modal;
    modal = document.createElement('div');
    modal.id = 'arPaymentModal';
    modal.className = 'ar-payment-modal';
    modal.hidden = true;
    modal.innerHTML = `
      <div class="ar-payment-backdrop" data-close="1"></div>
      <div class="ar-payment-dialog" role="dialog" aria-modal="true" aria-labelledby="arPaymentTitle">
        <button type="button" class="ar-payment-close" aria-label="Close payment dialog" data-close="1">×</button>
        <p class="ar-payment-eyebrow">Secure checkout</p>
        <h2 id="arPaymentTitle">Unlock ArticleReady AI</h2>
        <p id="arPaymentPlan" class="ar-payment-plan"></p>
        <p class="muted">African billing countries use Paystack. Other billing countries use Stripe.</p>
        <label><span class="field-label">Email for access *</span><input id="arPaymentEmail" type="email" placeholder="you@example.com" required></label>
        <label><span class="field-label">Billing country *</span><select id="arPaymentCountry"><option value="GH">Ghana</option><option value="NG">Nigeria</option><option value="KE">Kenya</option><option value="ZA">South Africa</option><option value="GB">United Kingdom</option><option value="US">United States</option><option value="CA">Canada</option><option value="AU">Australia</option><option value="DE">Germany</option><option value="FR">France</option></select></label>
        <div class="actions"><button id="arStartCheckoutBtn" class="btn" type="button">Continue to payment</button><button class="btn secondary" type="button" data-close="1">Cancel</button></div>
        <p id="arPaymentStatus" class="status"></p>
      </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', (event) => { if (event.target && event.target.dataset && event.target.dataset.close) closeModal(); });
    return modal;
  }
  let pendingPlan = 'standard_full_article';
  let pendingModule = 'article_writer';
  function openCheckout(planKey, opts = {}) {
    pendingPlan = planKey || 'standard_full_article';
    pendingModule = opts.moduleKey || opts.module || planModule(pendingPlan);
    const modal = ensureModal();
    document.getElementById('arPaymentTitle').textContent = `Unlock ${PLAN_NAMES[pendingPlan] || 'ArticleReady AI'}`;
    document.getElementById('arPaymentPlan').textContent = opts.message || `${PLAN_NAMES[pendingPlan] || pendingPlan} is required to continue.`;
    document.getElementById('arPaymentStatus').textContent = '';
    document.getElementById('arStartCheckoutBtn').onclick = startCheckout;
    modal.hidden = false;
    document.body.classList.add('ar-payment-open');
  }
  function closeModal() {
    const modal = document.getElementById('arPaymentModal');
    if (modal) modal.hidden = true;
    document.body.classList.remove('ar-payment-open');
  }
  function planModule(planKey) {
    if (planKey === 'article_ideas') return 'topic_ideas';
    if (['article_revision', 'reviewer_comment_revision', 'extra_revision_pass'].includes(planKey)) return 'article_revision';
    return 'article_writer';
  }
  async function startCheckout() {
    const email = document.getElementById('arPaymentEmail').value.trim();
    const country = document.getElementById('arPaymentCountry').value.trim().toUpperCase();
    const status = document.getElementById('arPaymentStatus');
    if (!email || !email.includes('@')) { status.textContent = 'Enter a valid email address.'; return; }
    status.textContent = 'Starting secure checkout...';
    try {
      const response = await fetch('/api/payments/checkout', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({plan_key: pendingPlan, user_email: email, billing_country: country, module_key: pendingModule, work_id: workIdFromPage(), metadata: {page: location.pathname}}),
      });
      const data = await readResponse(response);
      if (!response.ok) throw new Error(errorMessage(data.detail ?? data, response.statusText || `Checkout failed (${response.status})`));
      remember(data);
      if (!data.checkout_url) throw new Error('Checkout URL was not returned.');
      window.location.href = data.checkout_url;
    } catch (error) {
      status.textContent = errorMessage(error, 'Checkout could not be started.');
    }
  }
  function openFromApi(detail) {
    const normalised = detail && typeof detail === 'object' && !Array.isArray(detail) ? detail : {};
    const plan = normalised.recommended_plan || 'standard_full_article';
    openCheckout(plan, {message: errorMessage(normalised.message || normalised.detail, `${PLAN_NAMES[plan] || 'This package'} is required to continue.`)});
  }
  function selectedDraftPlan() {
    const stage = document.getElementById('draftStage')?.value || 'full_article';
    const type = (document.getElementById('articleType')?.value || '').toLowerCase();
    const words = Number(document.getElementById('targetWordCount')?.value || 0);
    if (stage === 'initial_to_methods') return 'stage1_article';
    if (type.includes('review') || type.includes('scoping') || type.includes('conceptual') || type.includes('systematic')) return 'review_conceptual_scoping';
    if (words > 9000) return 'long_article_plus';
    return 'standard_full_article';
  }
  function selectedRevisionPlan() {
    const comments = document.getElementById('reviewComments')?.value || '';
    return comments.trim() ? 'reviewer_comment_revision' : 'article_revision';
  }
  async function redeemPaymentHandoff(handoff) {
    const response = await fetch('/api/payments/redeem-handoff', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({handoff}),
    });
    const data = await readResponse(response);
    if (!response.ok) {
      const detail = errorMessage(data.detail ?? data, 'Paid access could not be restored.');
      throw new Error(detail);
    }
    remember(data);
    return data;
  }
  async function checkReturnStatus() {
    const params = new URLSearchParams(window.location.search);
    const payment = params.get('payment');
    if (!payment) return;
    const target = document.getElementById('paymentStatus') || document.getElementById('status') || document.querySelector('.status');
    if (payment === 'success') {
      const handoff = params.get('handoff') || '';
      const purchaseId = params.get('purchase_id') || '';
      if (target) target.textContent = 'Payment confirmed. Checking paid access...';
      try {
        // The checkout page stores an opaque credential before redirecting to the provider.
        // After payment, verify that credential first. This avoids rotating a valid token
        // unnecessarily and prevents a lost network response from stranding paid access.
        const existing = credentialsByPurchaseId(purchaseId);
        const existingStatus = existing ? await entitlementStatus(existing) : {active: false};
        if (existingStatus.active) {
          remember({...existing, plan_key: existingStatus.plan_key || existing.plan_key});
          if (target) target.textContent = 'Payment confirmed. Paid access is ready for the selected ArticleReady package.';
        } else if (handoff) {
          const restored = await redeemPaymentHandoff(handoff);
          const restoredStatus = await entitlementStatus(restored);
          if (!restoredStatus.active) throw new Error(restoredStatus.message || 'The paid package is not active yet.');
          if (target) target.textContent = 'Payment confirmed. Paid access is ready for the selected ArticleReady package.';
        } else if (target) {
          target.textContent = params.get('handoff_status') === 'recovery_required'
            ? 'Payment was received, but access restoration requires recovery. Use the payment recovery page with this Purchase ID.'
            : 'Payment was received, but the browser could not confirm the paid access credential. Use Payment Recovery.';
        }
      } catch (error) {
        if (target) target.textContent = `Payment was received, but automatic access restoration failed. ${errorMessage(error, 'Use Payment Recovery with the Purchase ID shown in the return URL.')}`;
      }
    }
    if (payment === 'failed' && target) target.textContent = 'Payment could not be confirmed. Try again or check your payment dashboard.';
    if (payment === 'cancelled' && target) target.textContent = 'Checkout was cancelled.';
    history.replaceState({}, document.title, window.location.pathname);
  }
  window.ArticleReadyPayments = {
    paymentHeaders,
    authorisedFetch,
    openCheckout,
    openFromApi,
    remember,
    selectedDraftPlan,
    selectedRevisionPlan,
    redeemPaymentHandoff,
    errorMessage,
    readResponse,
    credentials,
    entitlementStatus,
    readDeveloperAccess,
    rememberDeveloperAccess,
    clearDeveloperAccess,
    developerStatus,
  };
  window.addEventListener('DOMContentLoaded', checkReturnStatus);
})();
