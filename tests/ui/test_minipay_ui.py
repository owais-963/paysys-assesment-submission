"""Playwright UI journeys against the real MiniPay static frontend.

MiniPay now requires an API key (X-API-Key) for every action except the
health check (see MiniPay/README.md, app/auth.py). "Open/login to the
application" is covered as opening the page, confirming it can reach the
API (the health check, which needs no key), and entering the API key that
every other journey depends on -- the closest equivalent this app has to a
login step.

All assertions use Playwright's auto-retrying `expect(locator)` API against
stable element IDs already present in MiniPay/frontend/index.html -- no
manual `sleep`/timing-based waits.
"""
import uuid

from playwright.sync_api import expect


def test_open_application(page, ui_base_url):
    """1. Open the application and confirm it can reach the API via the
    unauthenticated health check.
    """
    page.goto(ui_base_url)

    expect(page).to_have_title("MiniPay")
    expect(page.locator("#api-key")).to_be_visible()
    expect(page.locator("#customer-form")).to_be_visible()
    expect(page.locator("#payment-form")).to_be_visible()
    expect(page.locator("#lookup-form")).to_be_visible()
    expect(page.locator("#search-form")).to_be_visible()
    expect(page.locator("#history-form")).to_be_visible()

    page.locator("#check-health").click()
    result = page.locator("#health-result")
    expect(result).to_have_attribute("data-status", "ok")
    expect(result).to_contain_text('"status": "ok"')
    expect(result).to_contain_text('"db": "reachable"')


def test_search_transaction_by_id(authenticated_page, api_payment):
    """2. Search for a transaction (by payment ID, via the lookup form)."""
    page = authenticated_page

    page.locator("#lookup-payment-id").fill(str(api_payment["id"]))
    page.locator("#lookup-form button[type='submit']").click()

    result = page.locator("#lookup-result")
    expect(result).to_have_attribute("data-status", "ok")
    expect(result).to_contain_text(api_payment["transaction_ref"])
    expect(result).to_contain_text(str(api_payment["customer_id"]))


def test_search_transaction_by_reference(authenticated_page, api_payment):
    """New functionality: search by transaction_ref, via the dedicated
    search form (distinct from the numeric-ID lookup form above).
    """
    page = authenticated_page

    page.locator("#search-transaction-ref").fill(api_payment["transaction_ref"])
    page.locator("#search-form button[type='submit']").click()

    result = page.locator("#search-result")
    expect(result).to_have_attribute("data-status", "ok")
    expect(result).to_contain_text(f'"query_ref": "{api_payment["transaction_ref"]}"')
    expect(result).to_contain_text('"count": 1')
    expect(result).to_contain_text(str(api_payment["customer_id"]))


def test_submit_payment_and_validate_success(authenticated_page, api_customer):
    """3. Create/submit a test payment via the UI.
    4. Validate the successful result.
    """
    page = authenticated_page

    transaction_ref = f"UITXN{uuid.uuid4().hex[:12]}"
    page.locator("#payment-ref").fill(transaction_ref)
    page.locator("#payment-customer-id").fill(str(api_customer["id"]))
    page.locator("#payment-amount").fill("99.99")
    page.locator("#payment-form button[type='submit']").click()

    result = page.locator("#payment-result")
    expect(result).to_have_attribute("data-status", "ok")
    expect(result).to_contain_text(transaction_ref)
    expect(result).to_contain_text('"status": "PROCESSING"')
    expect(result).to_contain_text(f'"customer_id": {api_customer["id"]}')


def test_submit_payment_negative_scenario(authenticated_page):
    """5. Negative/error scenario: submitting a payment for a customer_id
    that does not exist must surface a clear error in the UI, not a silent
    failure or a fabricated success.
    """
    page = authenticated_page

    page.locator("#payment-ref").fill(f"UITXN{uuid.uuid4().hex[:12]}")
    page.locator("#payment-customer-id").fill("999999999")
    page.locator("#payment-amount").fill("10.00")
    page.locator("#payment-form button[type='submit']").click()

    result = page.locator("#payment-result")
    expect(result).to_have_attribute("data-status", "error")
    expect(result).to_contain_text('"error": "not_found"')


def test_submit_payment_without_api_key_is_rejected(page, ui_base_url):
    """Negative/access-control scenario: leaving the API Key field blank and
    attempting an action must surface the real 401 from the API in the UI,
    not silently fail or fabricate a success.
    """
    page.goto(ui_base_url)
    # API Key field deliberately left blank.

    page.locator("#payment-ref").fill(f"UITXN{uuid.uuid4().hex[:12]}")
    page.locator("#payment-customer-id").fill("1")
    page.locator("#payment-amount").fill("10.00")
    page.locator("#payment-form button[type='submit']").click()

    result = page.locator("#payment-result")
    expect(result).to_have_attribute("data-status", "error")
    expect(result).to_contain_text("Invalid or missing API key")
