#!/usr/bin/env bash
# health_check.sh — Verify all five services are up through Nginx.
# Usage: ./scripts/health_check.sh

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
FAILED=0

check() {
  local name="$1"
  local url="$2"
  local http_code

  http_code=$(curl -s -o /dev/null -w "%{http_code}" "$url")
  if [ "$http_code" -eq 200 ]; then
    echo "[OK]   $name -> HTTP $http_code"
  else
    echo "[FAIL] $name -> HTTP $http_code"
    FAILED=1
  fi
}

echo "Checking service health through Nginx at $BASE_URL ..."
echo ""

check "product-service"   "$BASE_URL/product-health"
check "cart-service"      "$BASE_URL/cart-health"
check "inventory-service" "$BASE_URL/inventory-health"
check "payment-service"   "$BASE_URL/payment-health"
check "order-service"     "$BASE_URL/order-health"

echo ""
if [ "$FAILED" -eq 0 ]; then
  echo "All services are healthy."
else
  echo "One or more services failed the health check."
  exit 1
fi
