(function () {
  const form = document.getElementById('developerAccessForm');
  const email = document.getElementById('developerEmail');
  const code = document.getElementById('developerCode');
  const status = document.getElementById('developerStatus');
  const card = document.getElementById('developerSessionCard');
  const logout = document.getElementById('developerLogoutBtn');

  function formatExpiry(epochSeconds) {
    if (!epochSeconds) return 'Unknown';
    return new Date(Number(epochSeconds) * 1000).toLocaleString();
  }

  function renderSession(info) {
    if (info?.active) {
      card.innerHTML = `<div class="developer-active-badge">Developer access active</div><p><strong>Email:</strong> ${info.email || 'Not restricted by email'}</p><p><strong>Expires:</strong> ${formatExpiry(info.expires_at)}</p><p class="muted">Paid actions are available without consuming a customer package until this session expires or is ended.</p>`;
    } else {
      card.innerHTML = `<div class="developer-inactive-badge">Developer access inactive</div><p class="muted">Enter the configured developer credentials to begin a signed session.</p>`;
    }
  }

  async function refresh() {
    const info = await ArticleReadyPayments.developerStatus();
    renderSession(info);
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    status.textContent = 'Activating developer access...';
    try {
      const response = await fetch('/api/developer/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({email: email.value.trim(), access_code: code.value}),
      });
      const data = await ArticleReadyPayments.readResponse(response);
      if (!response.ok) throw new Error(ArticleReadyPayments.errorMessage(data.detail ?? data, 'Developer access could not be activated.'));
      ArticleReadyPayments.rememberDeveloperAccess(data);
      code.value = '';
      status.textContent = 'Developer access activated.';
      await refresh();
    } catch (error) {
      status.textContent = ArticleReadyPayments.errorMessage(error, 'Developer access could not be activated.');
    }
  });

  logout.addEventListener('click', async () => {
    ArticleReadyPayments.clearDeveloperAccess();
    status.textContent = 'Developer session ended on this browser.';
    await refresh();
  });

  refresh();
})();
