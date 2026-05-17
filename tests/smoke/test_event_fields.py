from tests.smoke._helpers import COMMON_EVENT_RULES, EVENT_FIELD_RULES


def test_smoke_expected_fields_per_event(checkout_trace: dict) -> None:
    hits = checkout_trace["hits"]

    observed_event_pairs = set()

    for hit in hits:
        source = hit.get("_source", {})

        assert "@timestamp" in source, "Missing @timestamp on indexed document"
        assert "service_name" in source, "Missing service_name on indexed document"
        assert "correlation_id" in source, "Missing correlation_id on indexed document"

        event_name = source.get("event_name")
        if not event_name:
            # nginx access logs do not contain event_name by design.
            continue

        service_name = source["service_name"]
        observed_event_pairs.add((service_name, event_name))

        common_required_fields = COMMON_EVENT_RULES.get(event_name, [])
        for field_name in common_required_fields:
            assert field_name in source, (
                f"Missing field {field_name!r} for event {event_name!r} "
                f"from service {service_name!r}: {source}"
            )

        specific_required_fields = EVENT_FIELD_RULES.get((service_name, event_name), [])
        for field_name in specific_required_fields:
            assert field_name in source, (
                f"Missing field {field_name!r} for event tuple {(service_name, event_name)!r}: {source}"
            )

    required_event_pairs = {
        ("cart-service", "checkout_started"),
        ("cart-service", "checkout_completed"),
        ("payment-service", "payment_authorization_completed"),
        ("order-service", "order_creation_completed"),
    }
    missing_pairs = required_event_pairs - observed_event_pairs
    assert not missing_pairs, f"Missing expected service/event pairs: {sorted(missing_pairs)}"
