# health_check.ps1 — Verify all five services are up through Nginx.
# Usage: .\scripts\health_check.ps1

if ($null -eq $env:BASE_URL) {
  $BaseUrl = "http://localhost:8080"
} else {
  $BaseUrl = $env:BASE_URL
}
$Failed = $false

function Check-Service {
  param(
    [string]$Name,
    [string]$Url
  )

  try {
    $response = Invoke-WebRequest -Uri $Url -Method Get -UseBasicParsing -ErrorAction SilentlyContinue
    $httpCode = $response.StatusCode
    if ($httpCode -eq 200) {
      Write-Host "[OK]   $Name -> HTTP $httpCode"
    } else {
      Write-Host "[FAIL] $Name -> HTTP $httpCode"
      $script:Failed = $true
    }
  } catch {
    Write-Host "[FAIL] $Name -> HTTP 0 (Connection failed)"
    $script:Failed = $true
  }
}

Write-Host "Checking service health through Nginx at $BaseUrl ..."
Write-Host ""

Check-Service "product-service"   "$BaseUrl/product-health"
Check-Service "cart-service"      "$BaseUrl/cart-health"
Check-Service "inventory-service" "$BaseUrl/inventory-health"
Check-Service "payment-service"   "$BaseUrl/payment-health"
Check-Service "order-service"     "$BaseUrl/order-health"

Write-Host ""
if (-not $Failed) {
  Write-Host "All services are healthy."
  exit 0
} else {
  Write-Host "One or more services failed the health check."
  exit 1
}
