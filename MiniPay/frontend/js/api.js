// Thin fetch wrapper around the MiniPay REST API.
const MiniPayApi = (() => {
  const base = window.MINIPAY_API_BASE_URL;

  async function request(path, options) {
    const res = await fetch(base + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    let body = null;
    try {
      body = await res.json();
    } catch (err) {
      body = null;
    }
    return { ok: res.ok, status: res.status, body };
  }

  return {
    health: () => request("/health", { method: "GET" }),
    createCustomer: (payload) =>
      request("/api/customers", { method: "POST", body: JSON.stringify(payload) }),
    createPayment: (payload) =>
      request("/api/payments", { method: "POST", body: JSON.stringify(payload) }),
    getPayment: (id) => request(`/api/payments/${encodeURIComponent(id)}`, { method: "GET" }),
    listCustomerPayments: (customerId, limit, offset) =>
      request(
        `/api/customers/${encodeURIComponent(customerId)}/payments?limit=${limit}&offset=${offset}`,
        { method: "GET" }
      ),
  };
})();
