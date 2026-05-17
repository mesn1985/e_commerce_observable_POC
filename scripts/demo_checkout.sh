#!/usr/bin/env bash
# demo_checkout.sh — Send a checkout request through Nginx and print the Correlation-ID.
# Usage: ./scripts/demo_checkout.sh

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"

echo "Sending checkout request to $BASE_URL/cart/student-1/checkout ..."
echo ""

response=$(curl -si -X POST "$BASE_URL/cart/student-1/checkout" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      { "product_id": "p1001", "quantity": 2 }
    ]
  }')

echo "$response"
echo ""

# Extract and highlight the Correlation-ID header
corr_id=$(echo "$response" | grep -i "^correlation-id:" | awk '{print $2}' | tr -d '\r')

if [ -n "$corr_id" ]; then
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  Correlation-ID : $corr_id"
  echo ""
  echo "  Open Kibana Discover at http://localhost:5601 and search:"
  echo "    correlation_id : \"$corr_id\""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
  echo "WARNING: Correlation-ID header was not found in the response."
fi
