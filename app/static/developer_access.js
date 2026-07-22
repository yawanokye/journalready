(function () {
  'use strict';

  const form = document.getElementById('developerAccessForm');
  const emailInput = document.getElementById('developerEmail');
  const codeInput = document.getElementById('developerCode');
  const statusElement = document.getElementById('developerStatus');
  const sessionCard = document.getElementById('developerSessionCard');
  const logoutButton = document.getElementById('developerLogoutBtn');
  const submitButton = form?.querySelector('button[type="submit"]');

  if (
    !form ||
    !emailInput ||
    !codeInput ||
    !statusElement ||
    !sessionCard ||
    !logoutButton
  ) {
    console.error('Developer access page elements could not be found.');
    return;
  }

  if (!window.ArticleReadyPayments) {
    statusElement.textContent =
      'Developer access services could not be loaded. Refresh the page and try again.';
    statusElement.classList.add('error');
    return;
  }

  function formatExpiry(epochSeconds) {
    const timestamp = Number(epochSeconds);
    if (!Number.isFinite(timestamp) || timestamp <= 0) {
      return 'Unknown';
    }
    return new Date(timestamp * 1000).toLocaleString();
  }

  function setStatus(message, type = '') {
    statusElement.textContent = message;
    statusElement.classList.remove('success', 'error', 'loading');
    if (type) {
      statusElement.classList.add(type);
    }
  }

  function setLoading(isLoading) {
    if (submitButton) {
      submitButton.disabled = isLoading;
      submitButton.textContent = isLoading
        ? 'Activating...'
        : 'Activate developer access';
    }
    logoutButton.disabled = isLoading;
    emailInput.disabled = isLoading;
    codeInput.disabled = isLoading;
  }

  function appendParagraph(label, value) {
    const paragraph = document.createElement('p');
    const strong = document.createElement('strong');
    strong.textContent = `${label}: `;
    paragraph.appendChild(strong);
    paragraph.appendChild(document.createTextNode(value));
    sessionCard.appendChild(paragraph);
  }

  function renderSession(info) {
    sessionCard.replaceChildren();

    if (info?.active) {
      const badge = document.createElement('div');
      badge.className = 'developer-active-badge';
      badge.textContent = 'Developer access active';
      sessionCard.appendChild(badge);

      appendParagraph(
        'Email',
        String(info.email || 'Not restricted by email')
      );
      appendParagraph('Expires', formatExpiry(info.expires_at));

      const note = document.createElement('p');
      note.className = 'muted';
      note.textContent =
        'Paid actions are available without consuming a customer package until this session expires or is ended.';
      sessionCard.appendChild(note);
      logoutButton.disabled = false;
      return;
    }

    const badge = document.createElement('div');
    badge.className = 'developer-inactive-badge';
    badge.textContent = 'Developer access inactive';
    sessionCard.appendChild(badge);

    const note = document.createElement('p');
    note.className = 'muted';
    note.textContent =
      'Enter the configured developer credentials to begin a signed session.';
    sessionCard.appendChild(note);
    logoutButton.disabled = true;
  }

  function validateCredentials(email, accessCode) {
    if (!email) {
      throw new Error('Enter the configured developer email.');
    }
    if (!/^\d{6}$/.test(accessCode)) {
      throw new Error('Enter the six-digit developer access code.');
    }
  }

  async function refresh() {
    try {
      const info = await ArticleReadyPayments.developerStatus();
      renderSession(info);
      return info;
    } catch (error) {
      renderSession({ active: false });
      setStatus(
        ArticleReadyPayments.errorMessage(
          error,
          'Developer session status could not be checked.'
        ),
        'error'
      );
      return null;
    }
  }

  form.addEventListener('submit', async function (event) {
    event.preventDefault();

    const email = emailInput.value.trim();
    const accessCode = codeInput.value.trim();

    try {
      validateCredentials(email, accessCode);
    } catch (error) {
      setStatus(error.message, 'error');
      codeInput.focus();
      return;
    }

    setLoading(true);
    setStatus('Activating developer access...', 'loading');

    try {
      const response = await fetch('/api/developer/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json'
        },
        credentials: 'same-origin',
        body: JSON.stringify({
          email,
          access_code: accessCode
        })
      });

      const data = await ArticleReadyPayments.readResponse(response);
      if (!response.ok) {
        throw new Error(
          ArticleReadyPayments.errorMessage(
            data?.detail ?? data,
            'Developer access could not be activated.'
          )
        );
      }

      ArticleReadyPayments.rememberDeveloperAccess(data);
      codeInput.value = '';
      setStatus('Developer access activated.', 'success');
      await refresh();
    } catch (error) {
      setStatus(
        ArticleReadyPayments.errorMessage(
          error,
          'Developer access could not be activated.'
        ),
        'error'
      );
      codeInput.select();
    } finally {
      setLoading(false);
    }
  });

  codeInput.addEventListener('input', function () {
    const digitsOnly = codeInput.value.replace(/\D/g, '').slice(0, 6);
    if (codeInput.value !== digitsOnly) {
      codeInput.value = digitsOnly;
    }
  });

  logoutButton.addEventListener('click', async function () {
    logoutButton.disabled = true;
    try {
      ArticleReadyPayments.clearDeveloperAccess();
      setStatus('Developer session ended on this browser.', 'success');
      await refresh();
    } catch (error) {
      setStatus(
        ArticleReadyPayments.errorMessage(
          error,
          'The developer session could not be ended.'
        ),
        'error'
      );
    }
  });

  refresh();
})();
