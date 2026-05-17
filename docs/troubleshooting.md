# Troubleshooting Guide

This guide documents common troubleshooting commands and queries used when debugging the distributed tracing system, Filebeat, Elasticsearch, and Docker services.

## Docker Commands

### View container logs

View logs from a specific service:
```bash
docker compose logs cart-service
docker compose logs filebeat
docker compose logs elasticsearch
```

Follow logs in real-time:
```bash
docker compose logs -f cart-service
docker compose logs -f filebeat
```

View last N lines:
```bash
docker compose logs --tail=100 cart-service
```

### Rebuild and restart services

Clean rebuild (removes volumes, forces rebuild):
```bash
docker compose down -v
docker compose up -d --build
```

Rebuild a specific service:
```bash
docker compose up -d --build cart-service
```

Restart without rebuilding:
```bash
docker compose restart cart-service
```

### Inspect containers

List running containers:
```bash
docker compose ps
```

Execute a command in a running container:
```bash
docker compose exec cart-service bash
docker compose exec filebeat bash
```

Inspect container configuration:
```bash
docker inspect <container_id>
```

## Elasticsearch Direct Queries

### Search by correlation ID

Find all log entries for a specific correlation ID, sorted by timestamp:
```bash
curl -s "http://localhost:9200/filebeat-*/_search?q=correlation_id:YOUR_CORRELATION_ID&size=100&sort=@timestamp:asc" | jq
```

Filter specific fields from the result:
```bash
curl -s "http://localhost:9200/filebeat-*/_search?q=correlation_id:6dddf5a06b6184fa32c4121b1946547a&size=100&sort=@timestamp:asc&filter_path=hits.total,hits.hits._source.event_name,hits.hits._source.service_name,hits.hits._source.status,hits.hits._source.status_text,hits.hits._source.transaction_id" | jq
```

### Check field mappings

View the mapping for the filebeat data stream to identify field type conflicts:
```bash
curl -s "http://localhost:9200/filebeat-*/_mapping" | jq '.[] | .mappings.properties' | head -50
```

View mapping for a specific field:
```bash
curl -s "http://localhost:9200/filebeat-*/_mapping" | jq '.[] | .mappings.properties | .status'
curl -s "http://localhost:9200/filebeat-*/_mapping" | jq '.[] | .mappings.properties | .id'
```

### Check index health and stats

Get overall index health:
```bash
curl -s "http://localhost:9200/_cluster/health?pretty"
```

Get stats on a specific data stream:
```bash
curl -s "http://localhost:9200/filebeat-*/_stats" | jq '.indices | keys'
```

### Query by service and event

Find all logs from a specific service:
```bash
curl -s "http://localhost:9200/filebeat-*/_search?q=service_name:cart-service&size=100" | jq '.hits.hits[] | {service: ._source.service_name, event: ._source.event_name, timestamp: ._source["@timestamp"]}'
```

Find all logs of a specific event type:
```bash
curl -s "http://localhost:9200/filebeat-*/_search?q=event_name:request_received&size=50" | jq
```

### Debug rejected documents

Check Elasticsearch recent cluster events for rejections:
```bash
curl -s "http://localhost:9200/_cluster/state?pretty" | jq '.metadata'
```

Monitor for 400 errors in Filebeat logs to identify mapping conflicts:
```bash
docker compose logs filebeat | grep -i "400\|mapping\|failed"
```

## Filebeat Debug Logging

### Enable debug logging temporarily

Edit `filebeat/filebeat.yml` and add/modify the logging section:

```yaml
logging.level: debug
logging.selectors: ["elasticsearch", "publisher"]
```

Then rebuild and restart Filebeat:
```bash
docker compose up -d --build filebeat
```

This will log detailed information about:
- Elasticsearch connection and authentication
- Document rejections with exact error messages
- Field mapping conflicts
- Publisher behavior

### Common debug output patterns

When a document is rejected due to mapping conflict, look for messages like:
```
failed to parse field [status] of type [long]
failed to parse field [id] of type [long]
```

These indicate that Elasticsearch rejected the document because a field value type doesn't match the pre-existing mapping.

### Reset logging to normal

Set `logging.level: info` and remove the selectors array, then restart:
```bash
docker compose up -d --build filebeat
```

## Kibana Queries

### Search by correlation ID in Kibana UI

1. Open Kibana: http://localhost:5601
2. Navigate to **Discover**
3. In the search bar, enter: `correlation_id:YOUR_CORRELATION_ID`
4. Click the `@timestamp` column header to sort ascending
5. Expand each log entry to view all fields

### Filter by service

Add a filter in Kibana UI:
- Click **Add Filter**
- Field: `service_name`
- Operator: `is`
- Value: `cart-service`

### View field distributions

In Kibana **Discover** tab:
- Left sidebar shows all available fields
- Click a field name to see top values and distribution
- Useful for checking if new fields (like `status_text`) are present in recent logs

## Common Troubleshooting Scenarios

### Issue: Elasticsearch returns 400 errors, logs not appearing

**Diagnosis:**
```bash
# Enable debug logging in filebeat.yml
# Check logs for field mapping conflicts
docker compose logs -f filebeat | grep -i "failed"

# Query Elasticsearch mapping to see pre-existing field types
curl -s "http://localhost:9200/filebeat-*/_mapping" | jq '.[] | .mappings.properties.status'
```

**Root causes from this project:**
1. **Filebeat self-logs conflicting with nginx field types**: Filebeat emitted `id='docker-containers'` (string), but nginx logs had `id: <number>` (long). Solution: Drop Filebeat self-logs with `drop_event` processor.
2. **Application status field conflicting**: Application emitted `status='approved'` (string), but nginx had `status: 200` (long). Solution: Remap application status field to `status_text` in logging formatter.

### Issue: Nginx access log appears out of order in trace

**Expected behavior:**
Nginx logs completion events, not arrival events. When viewing a complete trace in Kibana sorted by `@timestamp`, the Nginx access log often appears _after_ the final backend response logs, not at the beginning.

**Verification:**
```bash
curl -s "http://localhost:9200/filebeat-*/_search?q=correlation_id:YOUR_ID&size=100&sort=@timestamp:asc" | jq '.hits.hits[] | {timestamp: ._source["@timestamp"], service: ._source.service_name, event: ._source.event_name}'
```

This is correct behavior—Nginx doesn't have access to the request until it completes response handling.

### Issue: No logs appearing in Elasticsearch

**Checklist:**
1. Verify Filebeat is running: `docker compose ps | grep filebeat`
2. Check Filebeat logs for errors: `docker compose logs filebeat`
3. Verify Elasticsearch is healthy: `curl -s http://localhost:9200/_cluster/health?pretty`
4. Verify data exists: `curl -s "http://localhost:9200/filebeat-*/_count"`
5. Verify services are logging: `docker compose logs cart-service | grep -i json`

**Common fixes:**
- Rebuild entire stack: `docker compose down -v && docker compose up -d --build`
- Check Filebeat input paths match Docker log location: verify `/var/lib/docker/containers/*/*.log` in filebeat.yml
- Verify Elasticsearch has not run out of disk space

## Performance Monitoring

### Check Filebeat event processing rate

Monitor Filebeat logs:
```bash
docker compose logs -f filebeat | grep -i "events"
```

Look for lines like:
```
published X events
```

### Monitor Elasticsearch ingestion rate

```bash
watch -n 5 'curl -s http://localhost:9200/filebeat-*/_stats | jq ".indices | map(.primaries.indexing.index_total) | add"'
```

This refreshes every 5 seconds and shows total documents indexed.

### Check memory and disk usage

```bash
docker stats
```

Monitor Elasticsearch disk space:
```bash
curl -s "http://localhost:9200/_cat/allocation?v"
```

## Useful jq Filters

### Extract specific fields from Elasticsearch results

```bash
# Get just the timestamps and event names
curl -s "http://localhost:9200/filebeat-*/_search?size=50" | jq '.hits.hits[] | {timestamp: ._source["@timestamp"], event: ._source.event_name, service: ._source.service_name}'
```

### Count logs by service

```bash
curl -s "http://localhost:9200/filebeat-*/_search?size=1000" | jq '.hits.hits | group_by(._source.service_name) | map({service: .[0]._source.service_name, count: length})'
```

### Find recent errors

```bash
curl -s "http://localhost:9200/filebeat-*/_search?q=error_message:*&size=20&sort=@timestamp:desc" | jq '.hits.hits[] | {timestamp: ._source["@timestamp"], service: ._source.service_name, error: ._source.error_message}'
```

## Testing End-to-End Flow

### Run a complete checkout and verify logs

1. Execute the checkout demo:
```bash
python scripts/demo_checkout.py
```

2. Extract the correlation ID from the output

3. Query Elasticsearch for that correlation ID:
```bash
curl -s "http://localhost:9200/filebeat-*/_search?q=correlation_id:YOUR_ID&size=100&sort=@timestamp:asc" | jq '.hits.hits | length'
```

4. Verify you see logs from all services (cart, product, inventory, payment, order)

5. Verify no 400 errors in Filebeat: `docker compose logs filebeat | grep 400`

Expected output for a successful flow:
- 30-40 log entries total (varies based on service interactions)
- At least one entry from each service
- All entries share the same `correlation_id`
- No Filebeat errors in logs
