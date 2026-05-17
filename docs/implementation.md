# Implementation Details

This document describes the internal implementation of the distributed tracing system, including logging architecture, middleware patterns, and Filebeat configuration.

## Table of Contents

1. [Logging Architecture](#logging-architecture)
2. [FastAPI Middleware Pattern](#fastapi-middleware-pattern)
3. [Shared Logging Configuration](#shared-logging-configuration)
4. [HTTP Client with Correlation ID](#http-client-with-correlation-id)
5. [Filebeat Configuration](#filebeat-configuration)
6. [Field Mapping and Payload Reduction](#field-mapping-and-payload-reduction)

---

## Logging Architecture

### Overview

All services use structured JSON logging. Every log entry is a single JSON object printed to `stdout`/`stderr`, where Docker captures it. Filebeat then reads these logs from Docker container volumes and ships them to Elasticsearch.

### Log Flow

```
Service (logger.info()) 
  ↓
JSONFormatter (shared/logging_config.py) 
  ↓
JSON string to stdout 
  ↓
Docker stdout capture 
  ↓
Container log file (/var/lib/docker/containers/*/*)
  ↓
Filebeat (filestream input + docker parser)
  ↓
Elasticsearch
```

---

## FastAPI Middleware Pattern

### Request-Response Middleware

Every FastAPI service includes HTTP middleware that:

1. **Extracts or generates Correlation-ID**
2. **Logs request arrival**
3. **Stores state in request object**
4. **Processes the request**
5. **Logs request completion**
6. **Returns response headers with Correlation-ID**

### Implementation Example (from cart-service)

```python
@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    # Step 1: Extract or generate Correlation-ID
    incoming_correlation_id = request.headers.get(CORRELATION_ID_HEADER)
    correlation_id = incoming_correlation_id or str(uuid.uuid4())
    correlation_source = "request_header" if incoming_correlation_id else "generated"
    request.state.correlation_id = correlation_id

    # Step 2: Log request received
    start = time.monotonic()
    logger.info(
        "request_received",
        extra={
            "event": "request_received",
            "correlation_id": correlation_id,
            "correlation_id_source": correlation_source,
            "method": request.method,
            "path": request.url.path,
        },
    )

    # Step 3: Call next middleware/handler
    response = await call_next(request)
    duration_ms = int((time.monotonic() - start) * 1000)

    # Step 4: Add Correlation-ID response header
    if CORRELATION_ID_HEADER not in response.headers:
        response.headers[CORRELATION_ID_HEADER] = correlation_id

    # Step 5: Log request completed
    logger.info(
        "request_completed",
        extra={
            "event": "request_completed",
            "correlation_id": correlation_id,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )

    return response
```

### Key Points

- **No dependency injection needed** — `request.state` is a clean way to pass correlation ID to handlers
- **Timing is accurate** — middleware wraps the entire request, capturing true end-to-end duration
- **All 5 services** (product, cart, inventory, payment, order) implement this same pattern
- **Source tracking** — `correlation_id_source` distinguishes client-supplied vs generated IDs

---

## Shared Logging Configuration

### JSONFormatter

The `JSONFormatter` class in `shared/logging_config.py` converts Python log records into JSON.

#### Key Features

**Field Mapping:**
```python
mapped_key = {
    "event": "event_name",
    "service": "service_name",
    "error": "error_message",
    "status": "status_text",  # Avoid field type conflicts
}.get(key, key)
```

This remapping prevents conflicts with Elasticsearch mappings:
- `event` → `event_name` (clearer semantics)
- `service` → `service_name` (consistency)
- `status` → `status_text` (avoids conflict with nginx numeric status)
- `error` → `error_message` (clarity)

**Timestamp Format:**
```python
ts = (
    datetime.fromtimestamp(record.created, tz=timezone.utc)
    .strftime("%Y-%m-%dT%H:%M:%S.")
    + f"{int(record.msecs):03d}Z"
)
```
Produces ISO 8601 format: `2026-01-15T14:30:45.123Z`

**Extra Fields:**
```python
logger.info(
    "request_received",
    extra={
        "event": "request_received",
        "correlation_id": correlation_id,
        "method": "POST",
        "path": "/checkout",
    },
)
```

All keys in `extra` are merged into the JSON output, except reserved Python logging attributes (stored in `_SKIP_ATTRS`).

#### Output Example

```json
{
  "timestamp": "2026-01-15T14:30:45.123Z",
  "level": "INFO",
  "service_name": "cart-service",
  "event_name": "request_received",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "method": "POST",
  "path": "/cart/student-1/checkout"
}
```

---

## HTTP Client with Correlation ID

### Automatic Header Forwarding

The `call_service()` function in `shared/http_client.py` handles all service-to-service HTTP calls.

#### Features

1. **Automatic Correlation-ID forwarding** — Every outbound request includes the header
2. **Request/response logging** — Logs both sides of the call
3. **Retry logic** — Up to 3 attempts with exponential backoff
4. **Duration tracking** — Measures elapsed time per attempt

#### Implementation

```python
async def call_service(
    correlation_id: str,
    method: str,
    url: str,
    target_service: str,
    logger,
    json: Optional[Any] = None,
    params: Optional[dict] = None,
) -> httpx.Response:
    """Make an HTTP call to a downstream service."""
    async with httpx.AsyncClient(
        headers={CORRELATION_ID_HEADER: correlation_id},  # Automatic forwarding
        timeout=10.0,
    ) as client:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            # Log outbound request
            logger.info(
                "outbound_http_request",
                extra={
                    "event": "outbound_http_request",
                    "correlation_id": correlation_id,
                    "target_service": target_service,
                    "target_url": url,
                    "method": method.upper(),
                    "retry_attempt": attempt,
                    "max_attempts": MAX_ATTEMPTS,
                },
            )

            try:
                response = await client.request(method, url, json=json, params=params)

                # Log outbound response
                logger.info(
                    "outbound_http_response",
                    extra={
                        "event": "outbound_http_response",
                        "correlation_id": correlation_id,
                        "target_service": target_service,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                        "retry_attempt": attempt,
                    },
                )

                response.raise_for_status()
                return response

            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                if attempt < MAX_ATTEMPTS:
                    # Log retry attempt
                    logger.warning(
                        "retry_attempt",
                        extra={
                            "event": "retry_attempt",
                            "correlation_id": correlation_id,
                            "target_service": target_service,
                            "error": str(exc),
                            "retry_attempt": attempt,
                        },
                    )
```

#### Usage Example (from cart-service checkout)

```python
resp = await call_service(
    correlation_id=correlation_id,
    method="GET",
    url=f"{PRODUCT_SERVICE_URL}/products/{product_id}",
    target_service="product-service",
    logger=logger,
)
product = resp.json()
```

#### Logging Output

For a successful call:
```
outbound_http_request (attempt 1/3) → outbound_http_response (200, 25ms)
```

For a failed call with retry:
```
outbound_http_request (attempt 1/3) → failed with 503
retry_attempt (waiting)
outbound_http_request (attempt 2/3) → outbound_http_response (200, 40ms)
```

---

## Filebeat Configuration

### Overview

Filebeat uses the modern `filestream` input type with Docker container parser (not the deprecated `log` input type). This configuration ships Docker container logs directly to Elasticsearch with minimal processing.

### filebeat.yml Structure

#### 1. Input Configuration

```yaml
filebeat.inputs:
  - type: filestream
    id: docker-containers
    paths:
      - /var/lib/docker/containers/*/*.log
    parsers:
      - container:
          stream: all
          format: docker
```

**Why filestream?**
- Modern, recommended approach (legacy `log` input is deprecated)
- Better performance and reliability
- Native Docker container parsing

**Parser details:**
- `stream: all` — captures both stdout and stderr
- `format: docker` — parses Docker's JSON log format and extracts container metadata

#### 2. Metadata Enrichment

```yaml
processors:
  - add_docker_metadata:
      host: "unix:///var/run/docker.sock"
```

Adds Docker container information (container name, image, labels) to each log entry.

#### 3. Self-Log Filtering

```yaml
  - drop_event:
      when:
        equals:
          container.name: "e_commerce_distributed_tracing_poc-filebeat-1"
```

**Purpose:** Prevent Filebeat's own logs from being indexed back into Elasticsearch.

**Why needed:** Filebeat's internal event structure conflicted with application field types, causing 400 errors during indexing. This filter silently drops self-logs before they reach Elasticsearch.

#### 4. JSON Field Decoding

```yaml
  - decode_json_fields:
      fields: ["message"]
      target: ""
      overwrite_keys: true
      add_error_key: false
```

Docker's JSON log format includes a `message` field containing the application's JSON output. This processor:
- Parses the JSON in the `message` field
- Merges it into the top level (target: "")
- Allows Kibana to search application fields directly

**Example:**
```
Before: {"message": "{\"event_name\": \"request_received\", ...}", "container": {...}}
After:  {"event_name": "request_received", ..., "container": {...}}
```

#### 5. Field Reduction

```yaml
  - drop_fields:
      ignore_missing: true
      fields:
        - message
        - host
        - input
        - stream
        - timestamp
        - log
        - container.id
        - container.image
        - container.labels
```

**Payload Reduction Strategy:** Remove bulky fields not needed for application troubleshooting.

**Dropped Fields:**
- `message` — Already decoded and merged
- `host` — Redundant with container metadata
- `input`, `stream` — Filebeat internals
- `timestamp` — Use `@timestamp` instead
- `log` — Filebeat wrapper (all data is in top-level now)
- `container.id`, `container.image`, `container.labels` — Bulky metadata

**Kept Fields:**
- `@timestamp` — Elasticsearch ingest timestamp
- `container.name` — Maps to service name
- `correlation_id`, `event_name`, `service_name` — Application fields
- All other application custom fields

**Impact:** Reduces typical log entry from ~2KB to ~500 bytes, improving throughput and storage efficiency.

#### 6. Output to Elasticsearch

```yaml
output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  index: "filebeat-%{[agent.version]}-%{+yyyy.MM.dd}"
```

Writes to daily indices like `filebeat-8.13.4-2026-01-15`.

#### 7. Kibana and ILM Setup

```yaml
setup.kibana:
  host: "kibana:5601"

setup.template.name: "filebeat"
setup.template.pattern: "filebeat-*"
setup.ilm.enabled: false
```

- Creates a data view in Kibana for pattern `filebeat-*`
- ILM disabled (not needed for POC)

#### 8. Filebeat's Own Logging

```yaml
logging.to_files: false
logging.to_stderr: true
logging.level: warning
```

Filebeat logs go to stderr only, not to Elasticsearch. This keeps the system clean and prevents recursive logging.

---

## Field Mapping and Payload Reduction

### Why Field Mapping?

Elasticsearch pre-existing field mappings can cause indexing failures if a new document tries to insert a different type into a field.

### Root Causes Fixed

#### Issue 1: Filebeat Self-Log ID Conflict

- **Filebeat internally emitted:** `id: "docker-containers"` (string)
- **Nginx logs had:** `id: <number>` (long/numeric)
- **Solution:** Drop Filebeat self-logs before indexing with `drop_event` processor

#### Issue 2: Application Status Field Conflict

- **Application payment logs emitted:** `status: "approved"` (string)
- **Nginx logs had:** `status: 200` (long/numeric)
- **Solution:** Remap application `status` field to `status_text` in JSONFormatter

### Payload Reduction Benefits

**Before optimization:**
```json
{
  "message": "{...}",  // Bulky, redundant
  "host": "...",       // Unnecessary
  "input": "...",
  "stream": "...",
  "timestamp": "...",
  "log": {...},        // Wrapper object
  "container.id": "...",     // Long hex string
  "container.image": "...",  // Long string
  "container.labels": {...}, // Metadata
  "correlation_id": "...",   // Important
  "event_name": "..."        // Important
}
```
**~2KB per entry**

**After optimization:**
```json
{
  "@timestamp": "2026-01-15T14:30:45.123Z",
  "container.name": "e_commerce-cart-service-1",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "event_name": "request_received",
  "service_name": "cart-service",
  "method": "POST",
  "path": "/cart/student-1/checkout",
  "status_code": 200,
  "duration_ms": 42
}
```
**~500 bytes per entry**

**Result:** 75% reduction in storage, faster indexing, lower network bandwidth.

---

## Testing the Implementation

### End-to-End Test

1. Send a checkout request:
```bash
python scripts/demo_checkout.py
```

2. Copy the returned `Correlation-ID`

3. Query Elasticsearch to see the full trace:
```bash
curl -s "http://localhost:9200/filebeat-*/_search?q=correlation_id:YOUR_ID&size=100&sort=@timestamp:asc" | jq '.hits.hits[] | {service: ._source.service_name, event: ._source.event_name, timestamp: ._source["@timestamp"]}'
```

4. Verify:
   - All 6 services appear (nginx, cart, product, inventory, payment, order)
   - No Elasticsearch 400 errors in Filebeat logs
   - Events are in chronological order
   - No sensitive data in any log entries

### Debugging Filebeat Issues

Enable debug logging temporarily:
```yaml
logging.level: debug
logging.selectors: ["elasticsearch"]
```

Then restart Filebeat and check logs:
```bash
docker compose logs -f filebeat | grep -i "failed\|400"
```

This will show exact rejection messages if documents fail to index.

---

## Summary

The implementation achieves distributed tracing through:

1. **Middleware** — Captures request/response in FastAPI services
2. **Shared utilities** — Ensures consistent logging and header forwarding across all services
3. **Structured JSON** — Makes logs machine-searchable
4. **Filebeat + Elasticsearch** — Centralizes logs with built-in full-text search
5. **Kibana UI** — Allows students to reconstruct request paths visually

The system is optimized for learning: minimal complexity, maximum visibility into distributed behavior.
