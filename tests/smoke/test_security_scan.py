from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from tests.smoke._helpers import REPO_ROOT, wait_for_trace_in_elasticsearch


def test_smoke_security_scan_path_enumeration(smoke_environment: None) -> None:
    script_path = REPO_ROOT / "scripts" / "security_scan.py"
    report_dir = REPO_ROOT / "security" / "reports"

    assert script_path.exists(), f"Missing scan script: {script_path}"
    report_dir.mkdir(parents=True, exist_ok=True)

    before_reports = {p.name for p in report_dir.glob("zap_paths_*.json")}
    start_ts = time.time()

    command = [sys.executable, str(script_path)]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert result.returncode == 0, (
        "security_scan.py failed\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    new_reports = [p for p in report_dir.glob("zap_paths_*.json") if p.name not in before_reports]
    assert new_reports, "Expected security_scan.py to generate a new zap_paths_*.json report"

    report_path = max(new_reports, key=lambda p: p.stat().st_mtime)
    assert report_path.stat().st_mtime >= start_ts - 1

    report = json.loads(report_path.read_text(encoding="utf-8"))

    correlation_id = report.get("correlation_id", "")
    assert correlation_id.startswith("sec-scan-"), f"Unexpected correlation ID: {correlation_id}"

    assert report.get("target") == "http://nginx:80"
    assert int(report.get("wordlist_file_count", 0)) >= 1
    assert int(report.get("attempted_path_count", 0)) > 0
    assert int(report.get("discovered_path_count", 0)) > 0

    discovered_paths = report.get("discovered_paths", [])
    assert isinstance(discovered_paths, list)
    assert discovered_paths, "Expected non-empty discovered_paths in scan report"

    hits = wait_for_trace_in_elasticsearch(
        correlation_id,
        timeout_seconds=180,
        min_hits=1,
        required_services={"nginx"},
    )
    assert hits, f"No Elasticsearch hits found for correlation_id={correlation_id}"

    nginx_hits = [
        hit
        for hit in hits
        if hit.get("_source", {}).get("service_name") == "nginx"
    ]
    assert nginx_hits, f"Expected nginx logs for correlation_id={correlation_id}"
