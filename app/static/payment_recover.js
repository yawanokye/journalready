(function () {
  const emailInput = document.getElementById('recoveryEmail');
  const purchaseInput = document.getElementById('recoveryPurchaseId');
  const button = document.getElementById('restoreAccessBtn');
  const status = document.getElementById('recoveryStatus');

  const params = new URLSearchParams(window.location.search);
  if (params.get('purchase_id')) purchaseInput.value = params.get('purchase_id');

  button.addEventListener('click', async () => {
    const email = emailInput.value.trim();
    const purchaseId = purchaseInput.value.trim();
    if (!email || !email.includes('@') || !purchaseId) {
      status.textContent = 'Enter the payment email and Purchase ID.';
      return;
    }
    button.disabled = true;
    status.textContent = 'Verifying the payment and restoring access...';
    try {
      const response = await fetch('/api/payments/recover-access', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({email, purchase_id: purchaseId}),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(ArticleReadyPayments.errorMessage(data.detail ?? data, 'Paid access could not be restored.'));
      ArticleReadyPayments.remember(data);
      status.textContent = data.message || 'Paid access restored on this device.';
    } catch (error) {
      status.textContent = ArticleReadyPayments.errorMessage(error, 'Paid access could not be restored.');
    } finally {
      button.disabled = false;
    }
  });
})();
