import importlib


def test_payment_plans_include_article_ideas():
    from app.payments.entitlements import build_plans_payload
    payload = build_plans_payload()
    keys = {plan['plan_key'] for plan in payload['plans']}
    assert 'article_ideas' in keys
    plan = next(plan for plan in payload['plans'] if plan['plan_key'] == 'article_ideas')
    assert plan['price_display'] == 'US$2.99'
    assert plan['max_ideas'] == 20


def test_paid_idea_entitlement_can_be_claimed(tmp_path, monkeypatch):
    db = tmp_path / 'payments.db'
    monkeypatch.setenv('ARTICLEREADY_SQLITE_DB_PATH', str(db))
    from app.payments import store
    importlib.reload(store)
    reference = store.make_provider_reference('stripe')
    purchase = store.create_pending_purchase(
        user_email='author@example.com', work_id='article-one', module_key='topic_ideas',
        plan_key='article_ideas', amount=2.99, currency='USD', display_amount=2.99,
        display_currency='USD', payment_provider='stripe', provider_reference=reference,
    )
    store.activate_purchase(provider_reference=reference, verified_amount=2.99, verified_currency='USD', provider_payload={'ok': True})
    claim = store.claim_entitlement(
        purchase_id=purchase['id'], access_token=purchase['access_token'], action='idea',
        idempotency_key='run-1',
    )
    assert claim['claimed'] is True
    status = store.entitlement_status(purchase_id=purchase['id'], access_token=purchase['access_token'])
    assert status['remaining']['ideas'] == 0


def test_payment_handoff_restores_browser_access_once(tmp_path, monkeypatch):
    db = tmp_path / 'handoff.db'
    monkeypatch.setenv('ARTICLEREADY_SQLITE_DB_PATH', str(db))
    from app.payments import store
    importlib.reload(store)
    reference = store.make_provider_reference('stripe')
    purchase = store.create_pending_purchase(
        user_email='author@example.com', work_id='article-two', module_key='article_writer',
        plan_key='standard_full_article', amount=14.99, currency='USD', display_amount=14.99,
        display_currency='USD', payment_provider='stripe', provider_reference=reference,
    )
    store.activate_purchase(provider_reference=reference, verified_amount=14.99, verified_currency='USD', provider_payload={'paid': True})
    handoff = store.create_access_handoff(purchase['id'])
    restored = store.redeem_access_handoff(handoff)
    assert restored['access_token']
    assert restored['access_token'] != purchase['access_token']
    assert store.entitlement_status(purchase_id=purchase['id'], access_token=restored['access_token'])['active'] is True
    assert store.entitlement_status(purchase_id=purchase['id'], access_token=purchase['access_token'])['active'] is False
    try:
        store.redeem_access_handoff(handoff)
    except PermissionError as exc:
        assert 'already been used' in str(exc)
    else:
        raise AssertionError('Expected one-time handoff redemption to fail on second use')
