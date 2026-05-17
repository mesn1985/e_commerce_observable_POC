# Security Notes

This document explains the security principles demonstrated and reinforced by this project. It is written for IT security students.

---

## Correlation IDs

### What they are

A Correlation-ID is a unique identifier attached to a request when it enters the system. Every service that handles the request includes the same ID in its logs. This makes it possible to search one log store and reconstruct the complete path of a single request across multiple services.

### What they are NOT

- **Not authentication.** A Correlation-ID does not prove who made a request.
- **Not a secret.** Correlation-IDs are returned to the client in response headers. Anyone who sends a request receives the ID.
- **Not tamper-proof.** A client can supply any string as the `Correlation-ID` header. The system will accept and forward it.

### Should you trust a client-supplied Correlation-ID?

For incident investigation, accepting a client-supplied ID is useful — a developer or tester can set their own ID to make their requests easy to find in logs.

In a production system you might want to validate the format (e.g., must be a UUID) or ignore the client value entirely and always generate your own.

---

## Log Security

### Logs are evidence

In a security incident, logs are often the primary evidence used to understand what happened. Structured logs with correlation IDs make investigation faster and more reliable.

### Logs can also be a liability

If logs contain sensitive data, they become a high-value target for attackers. A database breach that exposes logs containing payment card numbers or passwords can make a moderate incident into a critical one.

### The rule: log metadata, not content

**You may log:**
- IDs (product IDs, order IDs, transaction IDs, user IDs)
- HTTP methods, paths, and status codes
- Durations and timestamps
- Service names and event names
- Counts and totals (amounts are OK; card numbers are not)

**You must never log:**
- Payment card numbers (PAN), CVV, or expiry dates — this would violate PCI DSS
- Passwords, password hashes, or password reset tokens
- Session tokens, API keys, or bearer tokens
- Personally Identifiable Information (PII) beyond what is necessary
- Full request or response bodies — these frequently contain secrets

### This project enforces these rules

No service in this project logs request bodies. The payment service logs `amount` and `currency` but not any card data. The order service logs `order_id` but not customer addresses or payment instrument details.

---

## Nginx as a Security Boundary

In this project, Nginx routes all five backend services publicly:

```
/products/*    -> product-service
/cart/*        -> cart-service
/inventory/*   -> inventory-service
/payments/*    -> payment-service
/orders/*      -> order-service
```

This is done **intentionally for teaching purposes** so that students can call any service directly and observe individual service behaviour.

In a production system:
- Only client-facing endpoints should be exposed publicly (e.g., `/cart/*/checkout`)
- Internal service-to-service URLs should not be reachable from outside the private network
- Services like `inventory-service` and `order-service` should only be callable by `cart-service`, not by arbitrary external clients

---

## Intended and Non-Intended Use

This project is a local educational POC. It has no:
- Authentication or authorisation
- Rate limiting
- Input validation beyond Pydantic type checking
- TLS/HTTPS
- Secrets management

None of these omissions are acceptable in a production system. They are excluded here to keep the code readable and focused on the distributed tracing learning objective.
