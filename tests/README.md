# Test Guide

This document explains the test suites in this repository, what they validate, and how to run them.

## Overview

The project currently contains two test layers:

1. Integration tests in `tests/`
2. Smoke tests in `tests/smoke/`

They serve different purposes:

- Integration tests assume the environment is already running and verify the application behavior through HTTP requests.
- Smoke tests manage the full Docker Compose environment through Testcontainers, run a real checkout, inspect logs, query Elasticsearch, and validate indexed fields.

---

## Test Structure

### Integration tests

Located in `tests/`:

- `test_health.py` - checks all health endpoints through Nginx
- `test_checkout_flow.py` - checks the checkout flow, response body, and Correlation-ID propagation

These tests are useful when:
- You already have the full stack running
- You want a fast confirmation that the application endpoints work
- You are focusing on HTTP behavior rather than log ingestion internals

### Smoke tests

Located in `tests/smoke/`:

- `conftest.py` - shared fixtures for environment lifecycle and checkout trace creation
- `_helpers.py` - shared helpers for Docker Compose, readiness checks, and Elasticsearch queries
- `test_checkout.py` - verifies checkout succeeds end-to-end
- `test_docker_logs.py` - verifies Docker logs contain the trace and Filebeat shows no Elasticsearch 400 indexing errors
- `test_elasticsearch_trace.py` - verifies the full trace is indexed and includes all expected services
- `test_event_fields.py` - verifies expected fields exist on key indexed events

These tests are useful when:
- You want to validate the full observability pipeline
- You want to verify Filebeat and Elasticsearch are working correctly
- You want to catch regressions in structured logging fields
- You want one higher-confidence end-to-end validation run

---

## Prerequisites

### For integration tests

You need:
- Docker Desktop or Docker Engine running
- The full stack started manually
- Python available locally
- Test dependencies installed

### For smoke tests

You need:
- Docker Desktop or Docker Engine running
- Python available locally
- Test dependencies installed
- Testcontainers installed

Smoke tests start the full environment using the repository's `docker-compose.yml`.

---

## Install Test Dependencies

### Create a Python Virtual Environment

It is recommended to create a Python virtual environment to isolate test dependencies. Run these commands from the **repository root folder** (not from within `tests/`):

**Bash (Linux/macOS/WSL):**
```bash
# Navigate to repository root if not already there
cd <path to e_commerce_observable_POC>

# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate
```

**PowerShell (Windows):**
```powershell
# Navigate to repository root if not already there
cd <path to e_commerce_observable_POC>

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1
```

> **Note:** If you encounter an execution policy error on PowerShell, run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### Install Test Dependencies

With the virtual environment activated (from the repository root), install the test dependencies:

```bash
pip install pytest httpx testcontainers
```

If you only want to run the basic integration tests, `pytest` and `httpx` are sufficient:

```bash
pip install pytest httpx
```

### Deactivate Virtual Environment

When you are finished, deactivate the virtual environment:

```bash
# Bash
deactivate

# PowerShell
deactivate
```

---

## Running the Integration Tests

Start the full stack first:

```bash
docker compose up -d --build
```

Then run all integration tests:

```bash
pytest tests/ -v
```

Or run them individually:

```bash
pytest tests/test_health.py -v
pytest tests/test_checkout_flow.py -v
```

### What they verify

#### `test_health.py`
- Every service health endpoint returns HTTP 200 through Nginx
- Each service returns a valid `Correlation-ID` response header
- Response payloads include expected health fields

#### `test_checkout_flow.py`
- Checkout returns HTTP 200
- Response body contains `status`, `order_id`, and `correlation_id`
- `Correlation-ID` header is present
- Response header and response body correlation IDs match
- Client-supplied `Correlation-ID` values are preserved end-to-end

---

## Running the Smoke Tests

Run the full smoke suite:

```bash
pytest tests/smoke -v
```

Run individual smoke modules:

```bash
pytest tests/smoke/test_checkout.py -v
pytest tests/smoke/test_docker_logs.py -v
pytest tests/smoke/test_elasticsearch_trace.py -v
pytest tests/smoke/test_event_fields.py -v
```

### How the smoke tests work

The smoke suite performs the following flow:

1. Stop and clean any previous Compose environment with `docker compose down -v`
2. Start the full stack through Testcontainers using `docker-compose.yml`
3. Wait until all health endpoints respond successfully
4. Send one real checkout request through Nginx
5. Capture the returned `Correlation-ID`
6. Wait until Elasticsearch indexes the related trace
7. Run assertions against:
   - checkout success
   - Docker logs
   - Filebeat behavior
   - Elasticsearch trace completeness
   - expected structured fields on indexed events
8. Tear down the environment when the session finishes

### Smoke fixture behavior

The shared smoke fixture is session-scoped, which means:
- The environment is started once per test run
- The checkout request is performed once per test run
- The resulting trace is reused across all smoke test modules

This keeps the suite reasonably efficient while still validating the full stack.

### Keeping the environment running

By default, the smoke suite tears the environment down after the tests complete.

To keep the environment running for inspection afterward:

**PowerShell:**
```powershell
$env:SMOKE_KEEP_ENV = "1"
pytest tests/smoke -v
```

**Bash:**
```bash
SMOKE_KEEP_ENV=1 pytest tests/smoke -v
```

---

## Smoke Test Coverage

### `test_checkout.py`
Validates:
- The checkout request succeeds
- The response status is `success`
- An `order_id` is returned
- The success message is present

### `test_docker_logs.py`
Validates:
- The trace correlation ID appears in Docker logs for `cart-service`
- `request_received` appears in the captured service logs
- Filebeat logs do not contain Elasticsearch `400` indexing errors

### `test_elasticsearch_trace.py`
Validates:
- Elasticsearch contains the indexed trace for the checkout correlation ID
- The trace contains at least a reasonable minimum number of events
- All expected services appear in the indexed trace:
  - `nginx`
  - `cart-service`
  - `product-service`
  - `inventory-service`
  - `payment-service`
  - `order-service`

### `test_event_fields.py`
Validates:
- Indexed documents include core fields such as:
  - `@timestamp`
  - `service_name`
  - `correlation_id`
- Common event types include their expected fields, for example:
  - `request_received`
  - `request_completed`
  - `outbound_http_request`
  - `outbound_http_response`
  - `database_query`
- Key business events include their service-specific fields, for example:
  - `checkout_started`
  - `payment_authorization_completed`
  - `order_creation_completed`

This is especially useful for catching regressions in structured logging format and Elasticsearch indexing.

---

## Common Test Workflows

### Quick application check

Use this when you already have the stack running and only want to verify the API behavior:

```bash
docker compose up -d --build
pytest tests/test_health.py tests/test_checkout_flow.py -v
```

### Full observability verification

Use this when you want to validate the full pipeline from request to indexed logs:

```bash
pytest tests/smoke -v
```

### Investigate a smoke failure manually

Keep the environment alive after the smoke suite:

```bash
SMOKE_KEEP_ENV=1 pytest tests/smoke -v
```

Then inspect manually with:

```bash
docker compose logs filebeat
curl -s "http://localhost:9200/filebeat-*/_search?size=20&sort=@timestamp:desc"
```

---

## Troubleshooting Test Failures

### Smoke tests skip immediately

Likely cause:
- Missing optional dependency such as `httpx` or `testcontainers`

Fix:
```bash
pip install pytest httpx testcontainers
```

### Smoke tests time out waiting for health checks

Likely cause:
- Elasticsearch or MongoDB is still starting
- Docker Desktop is low on memory
- A service failed to build or start

Inspect:
```bash
docker compose ps
docker compose logs
```

### Elasticsearch trace assertions fail

Likely cause:
- Filebeat did not ingest logs correctly
- Elasticsearch rejected documents due to field mapping conflicts
- The environment was not clean before the run

Inspect:
```bash
docker compose logs filebeat
curl -s "http://localhost:9200/filebeat-*/_search?size=50&sort=@timestamp:desc"
```

See also:
- [docs/troubleshooting.md](../docs/troubleshooting.md)
- [docs/implementation.md](../docs/implementation.md)

---

## Summary

Use the integration tests for fast API-level validation when the stack is already running.

Use the smoke tests when you want stronger end-to-end confidence that:
- the environment starts correctly
- checkout works
- logs are emitted
- Filebeat ships them
- Elasticsearch indexes them
- the expected structured fields are present
