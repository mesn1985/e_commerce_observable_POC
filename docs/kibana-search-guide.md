# Kibana Search Guide

This guide shows how to use Kibana to reconstruct the full path of a single request through the system.

## Prerequisites

- The full Docker Compose stack is running
- You have sent at least one checkout request and copied the `Correlation-ID` from the response

---

## Step 1 — Open Kibana

Navigate to **http://localhost:5601** in your browser.

If Kibana is still loading, wait a minute and refresh. It takes longer to start than the other services.

---

## Step 2 — Create a Data View

> Skip this step if you have done it before.

1. In the left sidebar click the **hamburger menu** (☰)
2. Go to **Management → Stack Management**
3. Click **Data Views** (formerly "Index Patterns")
4. Click **Create data view**
5. Set the name to `filebeat-*`
6. Set the **Timestamp field** to `@timestamp`
7. Click **Save data view to Kibana**

---

## Step 3 — Open Discover

1. Click the **hamburger menu** (☰)
2. Go to **Analytics → Discover**
3. Make sure the data view at the top left shows `filebeat-*`

---

## Step 4 — Search by Correlation-ID

In the **search bar** at the top, enter:

```
correlation_id : "paste-your-id-here"
```

For example:

```
correlation_id : "3d9f4c9b5e0c4b1aa0b9e8d8c7f6a5e1"
```

Press **Enter** or click the **Refresh** button.

---

## Step 5 — Sort by Timestamp

Click the **@timestamp** column header to sort ascending. This shows the request path in chronological order.

---

## Step 6 — Reconstruct the Request Path

With the logs sorted by time you will see entries from each component:

| Service | What you expect to see |
|---|---|
| `cart-service` | `checkout_started`, `product_lookup_started/completed`, `inventory_reservation_started/completed`, `payment_authorization_started/completed`, `order_creation_started/completed`, `checkout_completed` |
| `product-service` | `request_received`, `database_query`, `request_completed` |
| `inventory-service` | `request_received`, `inventory_reservation_started`, `database_write`, `inventory_reservation_completed`, `request_completed` |
| `payment-service` | `request_received`, `payment_authorization_started`, `payment_authorization_completed`, `request_completed` |
| `order-service` | `request_received`, `order_creation_started`, `database_write`, `order_creation_completed`, `request_completed` |
| `nginx` | Access log with `request_method`, `request_uri`, `status`, `request_time` |

### Outbound HTTP call logs (in cart-service)

Look for `event: outbound_http_request` and `event: outbound_http_response` entries. These show:
- The target service and URL
- The HTTP status code returned
- The `retry_attempt` (always `1` when the call succeeds first time)
- The `duration_ms`

---

## Useful Kibana Queries

Find all logs for a specific correlation ID:
```
correlation_id : "your-id-here"
```

Find only logs from cart-service:
```
correlation_id : "your-id" AND service_name : "cart-service"
```

Find only database operations:
```
correlation_id : "your-id" AND event_name : "database_write"
```

Find only outbound HTTP calls:
```
correlation_id : "your-id" AND event_name : "outbound_http_request"
```

---

## Tip — Add Columns

In Discover, click **Add column** and add these fields for a cleaner view:
- `service_name`
- `event_name`
- `status_code`
- `duration_ms`
- `target_service`
