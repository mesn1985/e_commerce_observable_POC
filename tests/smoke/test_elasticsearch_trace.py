from tests.smoke._helpers import CORE_SERVICES


def test_smoke_elasticsearch_query_has_complete_trace(checkout_trace: dict) -> None:
    hits = checkout_trace["hits"]

    assert len(hits) >= 20, f"Expected at least 20 events in the trace, got {len(hits)}"

    services_in_trace = {
        hit.get("_source", {}).get("service_name")
        for hit in hits
        if hit.get("_source", {}).get("service_name")
    }
    missing_services = CORE_SERVICES - services_in_trace
    assert not missing_services, f"Missing services in trace: {sorted(missing_services)}"
