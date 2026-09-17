# MiniPay API Integration Notes

## Purpose

This document describes the operational considerations for integrating with and supporting the MiniPay REST API from a **Support Engineer perspective**.

The API test suite is implemented as black-box HTTP automation using `pytest` and `requests`. Tests communicate with the running MiniPay service through its public HTTP interface and do not import application internals or directly manipulate the database.

The suite covers successful requests, validation failures, unknown resources, authentication, duplicate payment submissions, transaction-reference search, response schemas, server/dependency failures where practical, and basic response-time assertions.

---

## Running the Complete API Suite

Install the test dependencies:

```bash
pip install -r tests/api/requirements.txt
```

The default API address is:

```text
http://127.0.0.1:8000
```

A different environment can be selected using:

```bash
MINIPAY_API_BASE_URL=<MiniPay API address>
```

Every `/api/*` endpoint requires the configured API key.

Set the same API key configured on the running MiniPay instance:

```bash
export MINIPAY_API_KEY=<configured API key>
```

Run the complete API suite from the repository root:

```bash
MINIPAY_API_KEY=<configured API key> python -m pytest tests/api
```

The test session first verifies `/health`. It aborts with a clear error if the API is unavailable or if `MINIPAY_API_KEY` has not been configured.

The latest recorded execution collected 37 tests:

```text
36 passed
1 skipped
0 failed
```

The skipped test is an intentional database-unavailable fault-injection test that must only be enabled against an isolated environment.

---

# 1. Client and Server Timeouts

Every external API request should have a defined timeout. A payment integration should never wait indefinitely for a server or dependency.

The MiniPay API tests therefore use explicit request timeouts, for example:

```python
requests.get(url, timeout=5)
```

and:

```python
requests.post(url, json=payload, timeout=10)
```

A client timeout does not necessarily mean that the server failed to process the payment.

For example:

```text
Client
   |
   | POST payment
   v
MiniPay API
   |
   | transaction committed
   v
Database
   |
   X response does not reach client before timeout
```

The client now has an uncertain result. The transaction may exist even though the client did not receive a successful response.

### Support Engineer Handling

When investigating a payment timeout, I would check:

- API availability and `/health`;
- application/reverse-proxy logs;
- database connectivity;
- transaction reference;
- whether the transaction already exists;
- API and dependency latency;
- network errors;
- where the timeout occurred.

The transaction state should be established before deciding whether another payment submission is safe.

---

# 2. Retries

Retries can help recover from transient failures such as:

```text
connection timeout
connection reset
502 Bad Gateway
503 Service Unavailable
504 Gateway Timeout
```

Retries should be controlled using:

- a limited number of attempts;
- increasing delays;
- exponential backoff where appropriate;
- jitter where many clients could retry simultaneously.

For example:

```text
Request
   |
   X 503
   |
 wait
   |
 Retry
   |
   X 503
   |
 wait longer
   |
 Retry
   |
   + success
```

Retries should not be applied blindly to all failures.

For example:

```text
422 Unprocessable Entity
```

caused by a negative payment amount is a deterministic validation failure. Retrying the same request will not correct it.

Payment `POST` retries require additional care because the original payment may already have been committed.

Therefore payment retries must be designed together with idempotency.

---

# 3. Idempotency and Duplicate Payments

Idempotency means that repeating the same logical payment request does not create an additional financial transaction.

A production-safe behavior could look like:

```text
POST payment
Idempotency-Key: ABC123
       |
       v
Payment 50001 created

Client loses response

POST payment
Idempotency-Key: ABC123
       |
       v
Existing result for Payment 50001 returned
```

instead of:

```text
Request 1 -> Payment 50001
Request 2 -> Payment 50002
```

## Current MiniPay Behavior

The supplied MiniPay data model does not enforce uniqueness on:

```text
transactions.transaction_ref
```

and the supplied assessment dataset intentionally contains duplicate transaction references.

The automated test:

```text
test_duplicate_transaction_ref_is_not_idempotent
```

submits the same `transaction_ref` twice.

The current API returns:

```text
First request  -> 201 -> Payment A
Second request -> 201 -> Payment B
```

with different payment IDs.

Therefore the current MiniPay payment-creation operation is **not idempotent**.

The automated test deliberately records this actual behavior rather than incorrectly assuming that `transaction_ref` is unique.

## Production Recommendation

I would separate the business transaction reference from the request idempotency mechanism.

For example:

```text
transaction_ref = business/payment reference
Idempotency-Key = unique request/retry identifier
```

The server could persist the idempotency key together with the original request/result.

A repeated request using the same key and same payload could return the original result without creating another payment.

Reuse of the same idempotency key with a different payload should be rejected.

This would allow historical/business duplicate transaction references while still making network retries safe.

---

# 4. Authentication and Access Control

MiniPay implements a simple shared API-key authentication mechanism.

Every:

```text
/api/*
```

endpoint requires:

```text
X-API-Key: <configured key>
```

The health endpoint intentionally remains unauthenticated:

```text
GET /health
```

so infrastructure and monitoring systems can perform health checks without application credentials.

The automated suite validates the following behavior:

| Scenario | Expected |
|---|---:|
| `/health` without API key | `200` |
| `/api/*` without API key | `401` |
| `/api/*` with incorrect API key | `401` |
| `/api/*` with correct API key | Request proceeds |

The tests specifically include:

```text
test_health_requires_no_api_key
test_protected_endpoint_without_api_key_returns_401
test_protected_endpoint_with_wrong_api_key_returns_401
test_protected_endpoint_with_correct_api_key_succeeds
```

The transaction-reference search endpoint is also protected:

```text
GET /api/payments/search
```

and is independently verified to return `401` without the API key.

### Support Engineer Handling

For a `401` response, I would first verify:

- whether `X-API-Key` was supplied;
- whether the correct environment's credential is being used;
- whether the header name is correct;
- whether the configured server-side key matches;
- whether a deployment/configuration change recently modified the key.

Credentials must never be printed in investigation evidence, application logs, Git history, screenshots, or support tickets.

### Production Consideration

The shared API key is intentionally a simple mechanism suitable for demonstrating access-control behavior in this assessment.

A production payment platform would normally require stronger identity and authorization controls such as OAuth/OIDC, short-lived service credentials, scoped permissions, credential rotation, auditing, and appropriate secret management.

---

# 5. HTTP 4xx Errors

HTTP 4xx responses normally indicate a problem with the request, requested resource, authentication, or current resource state.

The MiniPay suite validates:

```text
401 Unauthorized
404 Not Found
405 Method Not Allowed
409 Conflict
422 Unprocessable Entity
```

Examples include:

- missing API key → `401`;
- incorrect API key → `401`;
- unknown customer → `404`;
- unknown payment → `404`;
- unknown route → `404`;
- unsupported HTTP method → `405`;
- duplicate unique `customer_ref` → `409`;
- missing required fields → `422`;
- zero/negative amount → `422`;
- incorrect field type → `422`;
- malformed JSON → `422`;
- missing required search parameter → `422`.

### Support Engineer Handling

A 4xx response should normally be investigated from the request/caller side before treating it as a server incident.

For `401`, verify credentials and authentication configuration.

For `404`, verify the resource identifier, endpoint, and target environment.

For `409`, inspect the conflicting resource/state.

For `422`, inspect JSON structure, required fields, field types, and validation rules.

For `405`, verify that the caller is using the supported HTTP method.

Deterministic 4xx failures should generally not be blindly retried.

---

# 6. HTTP 5xx Errors

HTTP 5xx responses indicate that the API or one of its required dependencies could not successfully complete an otherwise acceptable request.

Typical examples include:

```text
500 Internal Server Error
502 Bad Gateway
503 Service Unavailable
504 Gateway Timeout
```

### Support Engineer Investigation

For a MiniPay 5xx incident, I would investigate:

1. `/health`;
2. API/application logs;
3. PostgreSQL connectivity;
4. running process/container state;
5. listening ports;
6. network/DNS connectivity;
7. resource utilization;
8. recent deployments/configuration changes;
9. the affected customer or transaction reference.

The objective is to isolate the failing layer:

```text
Client
   |
   v
Proxy / Network
   |
   v
MiniPay API
   |
   v
PostgreSQL / Dependency
```

A 5xx response should not automatically trigger a payment retry until it is known whether the original operation was committed.

---

# 7. Controlled Database/Dependency Failure

The API suite contains an opt-in test:

```text
test_server_error_returns_generic_envelope_when_db_unreachable
```

The test is skipped during normal execution because automatically stopping PostgreSQL could disrupt a shared development/test database.

It can be enabled in an isolated environment using:

```bash
MINIPAY_TEST_DB_DOWN=1
```

after intentionally making the MiniPay database unavailable.

Expected health behavior:

```text
GET /health
     |
     v
PostgreSQL unavailable
     |
     v
503 Service Unavailable
```

A database-dependent application request is expected to return a controlled server-side error rather than exposing database credentials, SQL details, or stack traces.

After restoring PostgreSQL:

```text
GET /health
     |
     v
200 OK
```

should be verified before declaring recovery.

This is controlled fault injection and is preferable to corrupting transaction/customer data simply to generate a 5xx error.

---

# 8. Transaction Search by Reference

MiniPay provides:

```http
GET /api/payments/search?transaction_ref=<reference>
```

This is a search/collection operation rather than retrieval of one uniquely identified resource.

The API therefore supports three important outcomes:

```text
Reference matches one transaction
→ 200
→ count = 1

Reference matches no transactions
→ 200
→ count = 0
→ items = []

Reference matches duplicate transactions
→ 200
→ count > 1
→ all matching rows returned
```

The automated suite verifies:

```text
test_search_by_reference_finds_created_payment
test_search_by_reference_no_match_returns_empty_list
test_search_by_reference_returns_every_duplicate_match
test_search_by_reference_missing_param_returns_422
test_search_by_reference_requires_api_key
test_search_response_schema
```

This behavior is important because `transaction_ref` is not unique in the supplied database model.

The search endpoint must therefore not assume that a transaction reference always identifies exactly one database row.

From a **Support Engineer perspective**, this endpoint is particularly useful during transaction investigation because a business transaction reference can be used to retrieve all matching records.

---

# 9. JSON, Headers and API Contract

The automated tests verify more than HTTP status codes.

For successful resource creation, the suite checks relevant response headers such as:

```text
Location
```

The tests also verify JSON response structure and values.

Payment responses are checked for fields including:

```text
id
transaction_ref
customer_id
amount
status
created_at
completed_at
failure_code
```

Customer and payment-list response schemas are also validated.

The transaction-reference search response is expected to contain:

```json
{
    "query_ref": "...",
    "count": 1,
    "items": []
}
```

and the tests verify the envelope and returned payment objects.

This is important because:

```text
HTTP 200
```

alone does not prove that the API contract is correct.

Clients should send JSON requests using:

```text
Content-Type: application/json
```

and should validate both HTTP status and response content.

---

# 10. Response-Time Assertions

The suite contains basic response-time assertions for:

```text
GET /health
GET /api/payments/{id}
```

The configured threshold is:

```text
500 ms
```

The purpose is to identify an obvious performance regression in the test environment.

This threshold is **not a production SLA or load test**.

A single request completing below 500 ms does not demonstrate application behavior under production concurrency.

Production performance validation would additionally consider:

- throughput;
- concurrent requests;
- p50/p95/p99 latency;
- error rates;
- database utilization;
- application resource utilization;
- network latency.

---

# 11. Safe and Repeatable Testing

Tests that create resources generate unique references using UUID-based values such as:

```text
APITEST...
APITXN...
```

This reduces collisions with the seeded assessment dataset and previous test runs.

The suite uses the public HTTP interface instead of directly inserting or changing database rows.

The pre-test health check prevents a large number of misleading failures when the API itself is unavailable.

The suite also requires `MINIPAY_API_KEY` before starting so authenticated tests do not all fail because of missing test configuration.

Dependency fault injection remains opt-in so normal test execution cannot intentionally stop a shared PostgreSQL service.

---

# 12. Current Automated Coverage

The current suite covers:

- API health;
- successful customer creation;
- customer response schema;
- missing/invalid customer fields;
- duplicate customer references;
- successful payment creation;
- payment response schema;
- unknown customers;
- missing/invalid payment fields;
- zero and negative payment amounts;
- payment retrieval;
- unknown payment IDs;
- customer payment history;
- unknown customer history;
- payment-list response schema;
- duplicate/non-idempotent payment submission;
- valid API-key authentication;
- missing API key;
- incorrect API key;
- public health endpoint behavior;
- unsupported HTTP methods;
- unknown routes;
- malformed JSON;
- controlled database-unavailable behavior;
- transaction-reference search;
- no-result search;
- duplicate-reference search;
- search query-parameter validation;
- search authentication;
- search response schema;
- basic response-time assertions.

Latest recorded result:

```text
Collected: 37
Passed:    36
Skipped:   1
Failed:    0
```

The single skipped test is the intentionally gated database-unavailable scenario.

---

# 13. Support Engineer Operational Summary

From a **Support Engineer perspective**, API failures should first be classified before corrective action is taken.

```text
API request fails
        |
        +--- 401
        |      |
        |      +--> Verify authentication/configuration
        |
        +--- Other 4xx
        |      |
        |      +--> Validate request/resource/method
        |            Do not blindly retry
        |
        +--- 5xx / timeout
               |
               +--> Check health
                     Check logs
                     Check dependencies
                     Determine transaction state
                     Verify idempotency before retry
```

For payment integrations, a network failure or timeout does not prove that the financial operation failed.

Before retrying an uncertain payment, the existing transaction state should be checked using the available payment retrieval/search APIs.

Because the current MiniPay `POST /api/payments` operation is not idempotent, automatically retrying an uncertain payment request could create a duplicate payment.

A production implementation should therefore combine controlled retry behavior with a dedicated idempotency mechanism.