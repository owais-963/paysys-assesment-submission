"""Playwright UI journeys against the real MiniPay static frontend.

MiniPay has no authentication (by design -- see MiniPay/README.md), so
"open/login to the application" is covered as opening the page and
confirming it can reach the API (the health check), rather than a login
flow that doesn't exist.

All assertions use Playwright's auto-retrying `expect(locator)` API against
stable element IDs already present in MiniPay/frontend/index.html -- no
manual `sleep`/timing-based waits.
"""
import uuid

from playwright.sync_api import expect


def test_open_application(page, ui_base_url):
    """1. Open the application (no authentication exists, so there is no
    login step) and confirm it can reach the API.
    """
    page.goto(ui_base_url)

    expect(page).to_have_title("MiniPay")
    expect(page.locator("#customer-form")).to_be_visible()
    expect(page.locator("#payment-form")).to_be_visible()
    expect(page.locator("#lookup-form")).to_be_visible()
    expect(page.locator("#history-form")).to_be_visible()

    page.locator("#check-health").click()
    result = page.locator("#health-result")
    expect(result).to_have_attribute("data-status", "ok")
    expect(result).to_contain_text('"status": "ok"')
    expect(result).to_contain_text('"db": "reachable"')


def test_search_transaction_by_id(page, ui_base_url, api_payment):
    """2. Search for a transaction (by payment ID, via the lookup form)."""
    page.goto(ui_base_url)

    page.locator("#lookup-payment-id").fill(str(api_payment["id"]))
    page.locator("#lookup-form button[type='submit']").click()

    result = page.locator("#lookup-result")
    expect(result).to_have_attribute("data-status", "ok")
    expect(result).to_contain_text(api_payment["transaction_ref"])
    expect(result).to_contain_text(str(api_payment["customer_id"]))


def test_submit_payment_and_validate_success(page, ui_base_url, api_customer):
    """3. Create/submit a test payment via the UI.
    4. Validate the successful result.
    """
    page.goto(ui_base_url)

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


def test_submit_payment_negative_scenario(page, ui_base_url):
    """5. Negative/error scenario: submitting a payment for a customer_id
    that does not exist must surface a clear error in the UI, not a silent
    failure or a fabricated success.
    """
    page.goto(ui_base_url)

    page.locator("#payment-ref").fill(f"UITXN{uuid.uuid4().hex[:12]}")
    page.locator("#payment-customer-id").fill("999999999")
    page.locator("#payment-amount").fill("10.00")
    page.locator("#payment-form button[type='submit']").click()

    result = page.locator("#payment-result")
    expect(result).to_have_attribute("data-status", "error")
    expect(result).to_contain_text('"error": "not_found"')
