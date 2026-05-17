# demo_checkout.ps1 — Send a checkout request through Nginx and print the Correlation-ID.
# Usage: .\scripts\demo_checkout.ps1

if ($null -eq $env:BASE_URL) {
  $BaseUrl = "http://localhost:8080"
} else {
  $BaseUrl = $env:BASE_URL
}

Write-Host "Sending checkout request to $BaseUrl/cart/student-1/checkout ..."
Write-Host ""

$body = @{
  items = @(
    @{ product_id = "p1001"; quantity = 2 }
  )
} | ConvertTo-Json

try {
  $response = Invoke-WebRequest -Uri "$BaseUrl/cart/student-1/checkout" `
    -Method Post `
    -Headers @{"Content-Type" = "application/json"} `
    -Body $body `
    -UseBasicParsing

  # Print response headers and status
  Write-Host "HTTP/1.1 $($response.StatusCode) $($response.StatusDescription)"
  foreach ($header in $response.Headers.GetEnumerator()) {
    Write-Host "$($header.Key): $($header.Value -join ', ')"
  }
  Write-Host ""
  Write-Host $response.Content
  Write-Host ""

  # Extract Correlation-ID header
  $corrId = $response.Headers["Correlation-ID"]

  if ($corrId) {
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    Write-Host "  Correlation-ID : $corrId"
    Write-Host ""
    Write-Host "  Open Kibana Discover at http://localhost:5601 and search:"
    Write-Host "    correlation_id : `"$corrId`""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  } else {
    Write-Host "WARNING: Correlation-ID header was not found in the response."
  }
} catch {
  Write-Host "ERROR: Failed to send checkout request."
  Write-Host $_.Exception.Message
  exit 1
}
