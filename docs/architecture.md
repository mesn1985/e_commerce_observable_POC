# Architecture

## Overview

This system demonstrates **log-based distributed tracing** using a shared `Correlation-ID` header and centralized structured JSON logs.

It intentionally avoids span-based tools (OpenTelemetry, Jaeger, Zipkin) so that students can see how distributed tracing works at the most fundamental level: structured log lines, a shared identifier, and a search engine.

## Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant Nginx
    participant Cart as cart-service
    participant Product as product-service
    participant Inventory as inventory-service
    participant Payment as payment-service
    participant Order as order-service
    participant Mongo as MongoDB
    participant Filebeat
    participant ES as Elasticsearch
    participant Kibana

    Client->>Nginx: POST /cart/student-1/checkout
    Nginx->>Nginx: Generate Correlation-ID if missing
    Nginx->>Cart: Forward request with Correlation-ID header
    Cart->>Product: GET /products/p1001
    Product->>Mongo: find_one (product_db.products)
    Product-->>Cart: Product details
    Cart->>Inventory: POST /inventory/reserve
    Inventory->>Mongo: find_one_and_update (inventory_db.inventory)
    Inventory-->>Cart: Reservation result
    Cart->>Payment: POST /payments/authorize
    Payment-->>Cart: Mock approval + transaction_id
    Cart->>Order: POST /orders
    Order->>Mongo: insert_one (order_db.orders)
    Order-->>Cart: order_id
    Cart-->>Nginx: Checkout result
    Nginx-->>Client: Response with Correlation-ID header

    Note over Nginx,Order: All services log JSON to stdout with correlation_id
    Filebeat->>ES: Ship container logs
    Kibana->>ES: Search by correlation_id
```

## Component Ports

| Component | Internal port | Host port |
|---|---|---|
| nginx | 80 | **8080** |
| product-service | 8001 | 8001 |
| cart-service | 8002 | 8002 |
| inventory-service | 8003 | 8003 |
| payment-service | 8004 | 8004 |
| order-service | 8005 | 8005 |
| mongodb | 27017 | 27017 |
| elasticsearch | 9200 | 9200 |
| kibana | 5601 | **5601** |

## Shared Utilities (`shared/`)

| Module | Responsibility |
|---|---|
| `correlation.py` | `CORRELATION_ID_HEADER` constant, header extraction |
| `logging_config.py` | `JSONFormatter`, `setup_logging()` factory |
| `http_client.py` | `call_service()` — forwarded header, outbound logging, retries |
| `retry.py` | Tenacity retry decorator (3 attempts) |
| `responses.py` | `with_correlation_id()` helper |
