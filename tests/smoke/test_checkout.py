def test_smoke_checkout_success(checkout_trace: dict) -> None:
    body = checkout_trace["checkout_body"]

    assert body.get("status") == "success"
    assert body.get("order_id")
    assert body.get("message") == "Order created successfully"
