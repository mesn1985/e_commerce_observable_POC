from tests.smoke._helpers import run_compose


def test_smoke_docker_logs_include_trace(checkout_trace: dict) -> None:
    correlation_id = checkout_trace["correlation_id"]

    cart_logs = run_compose(["logs", "--no-color", "cart-service"], timeout=180)
    assert correlation_id in cart_logs, "Correlation ID not found in cart-service docker logs"
    assert "request_received" in cart_logs, "Expected request_received event not found in cart-service logs"

    filebeat_logs = run_compose(["logs", "--no-color", "filebeat"], timeout=180)
    assert "status=400" not in filebeat_logs.lower(), "Filebeat logs show Elasticsearch 400 indexing errors"
