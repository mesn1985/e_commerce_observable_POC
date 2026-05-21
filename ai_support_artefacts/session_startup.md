# Session Startup Context Guide

Use this checklist at the beginning of every new Copilot chat session so the assistant has the full project context before making changes.

## Goal

Ensure Copilot starts with the same shared understanding of:

- Functional requirements
- Observability and correlation-id contract
- Security and logging constraints
- Test and acceptance criteria

## Required Read Order

1. Project contract (source of truth)

- [ai_support_artefacts/generate_specifications.md](ai_support_artefacts/generate_specifications.md)
- Why: Defines required behavior, event contracts, architecture, non-goals, and acceptance criteria.

2. Current operational entry point

- [README.md](README.md)
- Why: Documents how the implementation is run, tested, and explained to students.

3. Design and implementation docs

- [docs/architecture.md](docs/architecture.md)
- [docs/implementation.md](docs/implementation.md)
- [docs/kibana-search-guide.md](docs/kibana-search-guide.md)
- [docs/security-notes.md](docs/security-notes.md)
- [docs/path-enumeration.md](docs/path-enumeration.md)
- [docs/troubleshooting.md](docs/troubleshooting.md)
- Why: Captures practical behavior and known conventions (especially logging/event field naming).

4. Test contract and expected checks

- [tests/README.md](tests/README.md)
- [tests/test_health.py](tests/test_health.py)
- [tests/test_checkout_flow.py](tests/test_checkout_flow.py)
- [tests/smoke/test_checkout.py](tests/smoke/test_checkout.py)
- [tests/smoke/test_docker_logs.py](tests/smoke/test_docker_logs.py)
- [tests/smoke/test_elasticsearch_trace.py](tests/smoke/test_elasticsearch_trace.py)
- [tests/smoke/test_event_fields.py](tests/smoke/test_event_fields.py)
- [tests/smoke/test_security_scan.py](tests/smoke/test_security_scan.py)
- Why: These tests are part of the implementation contract and define completion.

5. Runtime wiring (when changes affect infra or pipelines)

- [docker-compose.yml](docker-compose.yml)
- [nginx/nginx.conf](nginx/nginx.conf)
- [filebeat/filebeat.yml](filebeat/filebeat.yml)
- Why: Needed for correlation-id propagation, log shipping, and scanner behavior.

## Optional but Recommended (Task-Driven)

Read these when editing specific areas:

- Shared helpers:
	- [shared/correlation.py](shared/correlation.py)
	- [shared/http_client.py](shared/http_client.py)
	- [shared/logging_config.py](shared/logging_config.py)
	- [shared/retry.py](shared/retry.py)
	- [shared/responses.py](shared/responses.py)
- Service implementation folder being modified under [services](services)
- Relevant script(s) under [scripts](scripts)

## Suggested Startup Prompt

Use this in a new Copilot session:

"Please read [ai_support_artefacts/generate_specifications.md](ai_support_artefacts/generate_specifications.md), [README.md](README.md), all files in [docs](docs), and [tests/README.md](tests/README.md). Then summarize key constraints (correlation-id, logging fields, security limits, and test contract) before making any code changes."

## Notes for Consistency

- Keep logging field naming consistent across code, tests, and docs (for example: event vs event_name mapping).
- Do not introduce behavior outside the documented non-goals (no auth, no OpenTelemetry, no Logstash, no intentional failure scenarios).
- Preserve educational intent: broad observability and clear trace reconstruction in Kibana.
