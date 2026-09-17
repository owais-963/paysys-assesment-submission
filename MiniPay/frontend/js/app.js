function renderResult(el, result) {
  el.textContent = JSON.stringify(result.body, null, 2);
  el.dataset.status = result.ok ? "ok" : "error";
}

document.addEventListener("DOMContentLoaded", () => {
  const healthOut = document.getElementById("health-result");
  document.getElementById("check-health").addEventListener("click", async () => {
    renderResult(healthOut, await MiniPayApi.health());
  });

  const customerOut = document.getElementById("customer-result");
  document.getElementById("customer-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      customer_ref: document.getElementById("customer-ref").value,
      name: document.getElementById("customer-name").value,
    };
    renderResult(customerOut, await MiniPayApi.createCustomer(payload));
  });

  const paymentOut = document.getElementById("payment-result");
  document.getElementById("payment-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      transaction_ref: document.getElementById("payment-ref").value,
      customer_id: Number(document.getElementById("payment-customer-id").value),
      amount: document.getElementById("payment-amount").value,
    };
    renderResult(paymentOut, await MiniPayApi.createPayment(payload));
  });

  const lookupOut = document.getElementById("lookup-result");
  document.getElementById("lookup-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = document.getElementById("lookup-payment-id").value;
    renderResult(lookupOut, await MiniPayApi.getPayment(id));
  });

  const historyOut = document.getElementById("history-result");
  document.getElementById("history-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const customerId = document.getElementById("history-customer-id").value;
    const limit = document.getElementById("history-limit").value || 20;
    renderResult(historyOut, await MiniPayApi.listCustomerPayments(customerId, limit, 0));
  });
});
