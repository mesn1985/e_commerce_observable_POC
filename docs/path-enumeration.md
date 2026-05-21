# Path Enumeration Guide

This document explains how to run and validate API path enumeration in this repository using OWASP ZAP.

## Scope and Safety

This workflow is for local, authorized lab use only.

- Target inside Docker network: http://nginx:80
- Target from host: http://localhost:8080
- Do not scan external or production hosts

The scanner workflow is API-only. Spider or crawl-based discovery is intentionally out of scope.

## What Is Implemented

- security-scanner service in docker-compose.yml
- ZAP daemon API exposed on host at http://localhost:8090
- Postman request for API check: Security Scanner -> ZAP API Version in postman/ecommerce-distributed-tracing-poc.postman_collection.json
- PowerShell scan script (manual Windows use): scripts/security_scan.ps1
- Python scan script (cross-platform and CI): scripts/security_scan.py
- Wordlist folder: security/wordlists
- Report output folder: security/reports

## Wordlist Rules

All files in security/wordlists are consumed.

- Empty lines are ignored
- Lines starting with # are ignored
- Paths from all files are merged and deduplicated

## Run the Enumeration

1. Start the full stack:

```powershell
docker compose up -d
```

2. Run the scan script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\security_scan.ps1
```

Cross-platform alternative:

```bash
python scripts/security_scan.py
```

3. Confirm script output includes:

- Report path, for example: security/reports/zap_paths_YYYYMMDD_HHMMSS.json
- Correlation-ID, for example: sec-scan-YYYYMMDD_HHMMSS

Optional quick check before running the script:

- Run the Postman request Security Scanner -> ZAP API Version and confirm HTTP 200 with a version field in the JSON response.

## What the Script Does

1. Waits for ZAP API readiness
2. Generates one fixed scan correlation ID for the run
3. Adds a ZAP replacer rule to inject Correlation-ID header
4. Calls ZAP core/action/accessUrl for each generated path
5. Polls ZAP core/view/numberOfMessages to observe request completion
6. Exports one JSON report with metadata and discovered paths

## Validate Results

### Report Validation

Open the latest report under security/reports and verify:

- attempted_path_count > 0
- discovered_path_count > 0
- correlation_id starts with sec-scan-
- discovered_paths contains expected route prefixes such as /products, /cart, /inventory, /payments, /orders

### Elasticsearch Validation

Use the report correlation_id and query Elasticsearch:

```powershell
$cid = "sec-scan-YYYYMMDD_HHMMSS"
$body = @{ size = 20; query = @{ query_string = @{ query = "*${cid}*" } } } | ConvertTo-Json -Depth 8
Invoke-RestMethod -Method Post -Uri "http://localhost:9200/filebeat-*/_search" -ContentType "application/json" -Body $body
```

### Kibana Validation

In Discover, search:

service_name:"nginx" AND correlation_id:"sec-scan-YYYYMMDD_HHMMSS"

## Troubleshooting

### Registry pull denied for scanner image

- Ensure docker-compose.yml uses zaproxy/zap-stable:latest
- Run: docker compose pull security-scanner

### Script fails with connection reset

- Usually means ZAP daemon is not ready yet
- Re-run the script (it includes readiness waiting)

### Elasticsearch has no hits for scan correlation ID

- Check full stack is running: docker compose ps
- Re-run scan after Filebeat and Elasticsearch are up
- Check Filebeat logs: docker compose logs --tail=200 filebeat

## Related Files

- docker-compose.yml
- scripts/security_scan.ps1
- scripts/security_scan.py
- security/wordlists/default_paths.txt
- docs/security-notes.md
- tests/smoke/test_security_scan.py
