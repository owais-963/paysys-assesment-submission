# MiniPay API Integration Notes

## Purpose

This document describes the operational considerations for integrating with and supporting the MiniPay REST API from an L2 engineering perspective.

The automated API suite validates normal requests, invalid input, unknown resources, duplicate submissions, response schemas, HTTP behavior, dependency failures where practical, and basic response-time expectations.

The tests are implemented as black-box HTTP tests using `pytest` and `requests`. They communicate with the running MiniPay API rather than importing application internals.

---

## Running the Complete API Suite

Install the test dependencies:

```bash
pip install -r tests/api/requirements.txt
```

By default, the tests expect MiniPay at:

```text
http://127.0.0.1:8000
```

A different environment can be selected using:

```bash
MINIPAY_API_BASE_URL=<MiniPay API address>
```

Run the complete suite from the repository root:

```bash
python -m pytest tests/api
```

The suite performs a health check before starting and aborts with a clear error if the MiniPay API is unavailable.

The latest recorded execution is available in `tests/api/RESULT.md`.

---

# 1. Client and Server Timeouts

Every network request should have a defined timeout. A payment integration should never wait indefinitely for an API or dependency to respond.

The automated MiniPay tests therefore use explicit request timeouts, for example:

```python
requests.get(url, timeout=5)
```

or:

```python
requests.post(url, json=payload, timeout=10)
```

A timeout does not necessarily mean that the server did not process the request.

For example:

```text
Client
  |
  | POST payment
  v
MiniPay
  |
  | Payment created
  v
Database
  |
  X Response times out before reaching client
```

From the client's perspective, the result is uncertain: the payment may have been created even though no successful response was received.

For this reason, a timed-out payment request should not automatically be treated as a failed payment.

### L2 handling

When investigating a timeout, I would check:

- whether MiniPay is reachable;
- application and reverse-proxy logs;
- database availability;
- request/transaction reference;
- whether the payment already exists;
- dependency latency;
- whether the timeout occurred at the client, API, proxy, or database layer.

The transaction should be checked before deciding whether another payment submission is safe.

---

# 2. Retries

Retries are useful for temporary failures, but they must be controlled.

Examples of potentially transient failures include:

```text
connection timeout
connection reset
HTTP 502 Bad Gateway
HTTP 503 Service Unavailable
HTTP 504 Gateway Timeout
```

A retry strategy should normally use:

- a limited number of attempts;
- increasing delay between attempts;
- preferably exponential backoff;
- optional jitter to avoid many clients retrying simultaneously.

For example:

```text
Attempt 1
   |
   X 503

wait

Attempt 2
   |
   X 503

wait longer

Attempt 3
   |
   + success
```

Retries should not be performed blindly for every HTTP response.

A request rejected because of invalid data will normally continue to fail regardless of how many times it is retried.

For example:

```text
422 Invalid amount
```

should be corrected rather than retried.

### Payment-specific risk

Retrying a `POST /api/payments` request is particularly sensitive because the original request may have reached MiniPay even if the client did not receive the response.

Without reliable idempotency, automatically retrying a payment creation request can create duplicate payments.

Therefore retry behavior must be considered together with idempotency.

---

# 3. Payment Idempotency

Idempotency means that repeating the same logical payment request does not create additional financial transactions.

For example, the desired behavior in a production payment API would typically be:

```text
POST payment
transaction/idempotency reference = ABC123
        |
        v
Payment 50001 created

Network failure occurs

Client retries ABC123
        |
        v
Existing Payment 50001 returned
```

rather than:

```text
ABC123 -> Payment 50001

ABC123 -> Payment 50002
```

## Current MiniPay Behavior

The current MiniPay implementation intentionally allows duplicate `transaction_ref` values because the supplied database schema does not define `transaction_ref` as unique and the supplied assessment dataset contains duplicate references.

The automated test:

```text
test_duplicate_transaction_ref_is_not_idempotent
```

submits the same transaction reference twice and confirms that two different payment IDs are created.

Therefore, **the current MiniPay payment-creation endpoint is not idempotent**.

The test documents the actual system behavior rather than assuming idempotency that the implementation does not provide.

## Production Approach

In a production payment integration, I would not rely only on `transaction_ref` uniqueness if historical/business requirements allow duplicate references.

A stronger design would use a dedicated idempotency mechanism, for example:

```text
Idempotency-Key: <unique request key>
```

The server would persist the key together with the result of the original request.

If the same key is received again with the same request, the original result can be returned instead of creating another payment.

If the same key is reused with a different request payload, the API should reject the request rather than silently treating it as the same transaction.

This allows the business model to continue supporting non-unique historical `transaction_ref` values while providing safe retry behavior for payment creation.

---

# 4. HTTP 4xx Errors

HTTP 4xx responses normally indicate that the request cannot be processed because of something related to the request, resource, or caller.

MiniPay tests cover examples including:

```text
404 Not Found
409 Conflict
405 Method Not Allowed
422 Unprocessable Entity
```

Examples from the automated suite include:

- missing required customer fields → `422`;
- empty `customer_ref` → `422`;
- zero or negative payment amount → `422`;
- invalid `customer_id` type → `422`;
- unknown customer → `404`;
- unknown payment → `404`;
- duplicate unique `customer_ref` → `409`;
- unsupported HTTP method → `405`;
- malformed JSON → `422`.

### L2 handling

A 4xx response should normally be investigated from the request side first.

For example:

```text
422
```

means I would inspect:

- JSON structure;
- required fields;
- data types;
- validation constraints;
- field values.

A:

```text
404
```

means I would verify:

- requested resource ID;
- environment;
- whether the resource was previously created;
- whether the caller is using the correct endpoint.

A:

```text
409
```

indicates a conflict with current resource state, such as attempting to create a customer with an already existing unique `customer_ref`.

Blind retries are normally inappropriate for deterministic 4xx validation failures.

---

# 5. HTTP 5xx Errors

HTTP 5xx responses indicate that the server or one of its required dependencies could not successfully complete an otherwise acceptable request.

Examples include:

```text
500 Internal Server Error
502 Bad Gateway
503 Service Unavailable
504 Gateway Timeout
```

These errors require investigation of the server and dependency path rather than immediately assuming the client request is incorrect.

### L2 investigation flow

For a MiniPay 5xx incident, I would check:

1. `/health`;
2. API/application logs;
3. PostgreSQL connectivity;
4. listening services and ports;
5. container/process status;
6. recent deployments or configuration changes;
7. resource utilization;
8. dependency/network failures;
9. the specific transaction/customer reference involved.

The objective is to determine where the failure occurred:

```text
Client
   |
   v
MiniPay API
   |
   v
Database / Dependency
```

---

# 6. Database/Dependency Failure

A genuine server-side failure should be generated through controlled fault injection rather than by corrupting source payment data.

The API suite contains an opt-in database-unavailable test:

```text
test_server_error_returns_generic_envelope_when_db_unreachable
```

It is skipped during the normal test run because automatically stopping a shared PostgreSQL instance would be unsafe.

To test this scenario, PostgreSQL should be made unavailable only in an isolated test environment and the test enabled with:

```text
MINIPAY_TEST_DB_DOWN=1
```

The expected health behavior is:

```text
GET /health
       |
       v
Database unavailable
       |
       v
HTTP 503
```

Database-dependent API requests should return a controlled server-error response rather than exposing stack traces, database credentials, or implementation details.

After restoring PostgreSQL, `/health` should be checked again to verify service recovery.

This approach demonstrates failure handling without modifying transaction records merely to force an error.

---

# 7. Response-Time Handling

The automated suite includes basic response-time assertions for:

```text
GET /health
GET /api/payments/{id}
```

The current threshold is:

```text
500 ms
```

The purpose of this assertion is to detect an obvious response-time regression in the test environment.

It is **not a load test, capacity test, SLA, or production performance benchmark**.

A single API request completing below 500 ms does not demonstrate system behavior under concurrency or production traffic.

A production performance assessment would additionally consider:

- concurrent users;
- throughput;
- p50/p95/p99 latency;
- database load;
- network latency;
- error rate;
- resource utilization.

---

# 8. Authentication and Access Control

The current MiniPay assessment implementation does not include an authentication mechanism.

The automated tests explicitly verify this current behavior and also verify API routing boundaries such as:

```text
unknown route       -> 404
unsupported method  -> 405
```

This documents the implementation accurately, but **404/405 routing behavior should not be considered a replacement for authentication or authorization**.

For a production payment API, endpoints that create or retrieve payment/customer information should require authenticated and authorized callers.

A production implementation could use mechanisms such as:

- OAuth 2.0 / OpenID Connect;
- signed service credentials;
- short-lived access tokens;
- API keys for controlled service-to-service integrations where appropriate.

Authorization should then determine which operations and resources an authenticated caller is permitted to access.

For the assessment, the absence of authentication is a known implementation limitation rather than something silently assumed to be production-ready.

---

# 9. JSON, Headers and API Contract

The tests validate both HTTP behavior and response content.

Successful resource creation verifies the `Location` response header where applicable.

Tests also validate response fields and types rather than checking only:

```python
assert response.status_code == 200
```

For example, payment tests verify fields such as:

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

This is important because a `200` response with an incorrect JSON structure is still an API contract failure.

Clients should send JSON using:

```text
Content-Type: application/json
```

and should validate both the HTTP status and expected response structure.

---

# 10. Safe and Repeatable Testing

API tests create their own customers and transactions using generated references prefixed with:

```text
APITEST
APITXN
```

Random reference values prevent collisions between repeated test executions and avoid relying on fixed IDs from the supplied dataset.

The suite communicates through the public HTTP API rather than directly manipulating application tables.

The supplied assessment data should not be changed merely to make a test easier to execute.

Fault scenarios that require dependency failure are isolated and opt-in rather than automatically disrupting the normal test environment.

---

# 11. Current Automated Test Coverage

The current suite contains automated coverage for:

- API health;
- successful customer creation;
- customer response schema;
- invalid/missing customer fields;
- duplicate customer references;
- successful payment creation;
- payment response schema;
- invalid/missing payment fields;
- non-positive payment amounts;
- incorrect data types;
- unknown customers;
- payment retrieval;
- unknown payments;
- customer payment history;
- payment-list response schema;
- unknown customer history;
- duplicate payment submission behavior;
- malformed JSON;
- unsupported HTTP methods;
- unknown routes;
- basic response-time thresholds;
- controlled database-unavailable behavior as an opt-in test.

The latest recorded run collected 28 tests:

```text
27 passed
1 skipped
0 failed
```

The skipped test is the intentional database-unavailable fault-injection scenario and is not executed automatically against the normal database.

---

# 12. L2 Operational Summary

From an L2 support perspective, payment API failures should be classified before action is taken.

```text
Request fails
     |
     +-- 4xx
     |     |
     |     +--> Validate request/resource/access
     |           Do not blindly retry
     |
     +-- 5xx / timeout
           |
           +--> Check health, logs and dependencies
                 Determine whether request was processed
                 Check idempotency before retrying payment
```

The most important payment-integration principle is that a communication failure does not always mean the financial operation failed.

Before retrying a timed-out or failed payment request, the transaction state should be verified and the retry should be protected by an appropriate idempotency mechanism.

This prevents a temporary network or dependency issue from becoming a duplicate financial transaction.