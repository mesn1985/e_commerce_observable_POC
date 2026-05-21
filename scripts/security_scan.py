from __future__ import annotations

import argparse
import http.client
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit


def _api_get_json(url: str) -> dict:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")
    if not parsed.netloc:
        raise ValueError(f"Missing host in URL: {url}")

    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(parsed.netloc, timeout=20.0)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        raw = response.read().decode("utf-8")
        if response.status >= 400:
            raise RuntimeError(f"ZAP API request failed ({response.status}): {url} -> {raw}")
        return json.loads(raw)
    finally:
        conn.close()


def _wait_for_zap_ready(zap_api_base: str, timeout_seconds: int = 90) -> None:
    deadline = time.time() + timeout_seconds
    last_error = "unknown"

    while time.time() < deadline:
        try:
            _api_get_json(f"{zap_api_base}/JSON/core/view/version/")
            return
        except Exception as exc:
            last_error = str(exc)
            time.sleep(0.5)

    raise TimeoutError(f"Timed out waiting for ZAP API readiness at {zap_api_base}: {last_error}")


def _load_paths(wordlist_dir: Path) -> tuple[list[str], list[Path]]:
    if not wordlist_dir.exists() or not wordlist_dir.is_dir():
        raise FileNotFoundError(f"Wordlist directory not found: {wordlist_dir}")

    wordlist_files = sorted(p for p in wordlist_dir.iterdir() if p.is_file())
    if not wordlist_files:
        raise RuntimeError(f"No wordlist files found in: {wordlist_dir}")

    merged_paths: list[str] = []
    seen: set[str] = set()

    for file_path in wordlist_files:
        for raw_line in file_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            normalized = line.lstrip("/")
            if not normalized:
                continue
            if normalized not in seen:
                seen.add(normalized)
                merged_paths.append(normalized)

    if not merged_paths:
        raise RuntimeError("No valid paths found after filtering all wordlist files.")

    return merged_paths, wordlist_files


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OWASP ZAP path enumeration via API")
    parser.add_argument("--zap-api-base", default="http://localhost:8090")
    parser.add_argument("--target-base", default="http://nginx:80")
    parser.add_argument("--wordlist-dir", default="security/wordlists")
    parser.add_argument("--report-dir", default="security/reports")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args()

    zap_api_base = args.zap_api_base.rstrip("/")
    target_base = args.target_base.rstrip("/")
    wordlist_dir = Path(args.wordlist_dir)
    report_dir = Path(args.report_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    correlation_id = f"sec-scan-{timestamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"zap_paths_{timestamp}.json"

    paths, wordlist_files = _load_paths(wordlist_dir)

    print(f"Preparing OWASP ZAP path enumeration against {target_base}")
    print(f"Wordlist files: {len(wordlist_files)}")
    print(f"Correlation-ID: {correlation_id}")

    _wait_for_zap_ready(zap_api_base, timeout_seconds=90)

    # Keep rule deterministic for repeated runs.
    try:
        _api_get_json(f"{zap_api_base}/JSON/replacer/action/removeRule/?description=scan-cid")
    except Exception:
        pass

    add_rule_url = (
        f"{zap_api_base}/JSON/replacer/action/addRule/"
        f"?description=scan-cid"
        f"&enabled=true"
        f"&matchType=REQ_HEADER"
        f"&matchRegex=false"
        f"&matchString=Correlation-ID"
        f"&replacement={quote(correlation_id, safe='')}"
    )
    _api_get_json(add_rule_url)

    before = int(_api_get_json(f"{zap_api_base}/JSON/core/view/numberOfMessages/").get("numberOfMessages", 0))

    for path in paths:
        target_url = f"{target_base}/{path}"
        encoded_target = quote(target_url, safe="")
        _api_get_json(
            f"{zap_api_base}/JSON/core/action/accessUrl/?url={encoded_target}&followRedirects=true"
        )

    expected = before + len(paths)
    deadline = time.time() + max(1, args.timeout_seconds)
    current = before

    while current < expected and time.time() < deadline:
        time.sleep(0.5)
        current = int(_api_get_json(f"{zap_api_base}/JSON/core/view/numberOfMessages/").get("numberOfMessages", 0))

    seen_urls = _api_get_json(f"{zap_api_base}/JSON/core/view/urls/").get("urls", [])
    discovered_paths_set: set[str] = set()

    for candidate in seen_urls:
        if not isinstance(candidate, str) or not candidate.startswith(f"{target_base}/"):
            continue
        path_part = candidate[len(target_base) :]
        if path_part:
            discovered_paths_set.add(path_part)

    discovered_paths = sorted(discovered_paths_set)

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target": target_base,
        "correlation_id": correlation_id,
        "wordlist_directory": str(wordlist_dir),
        "wordlist_files": [str(path) for path in wordlist_files],
        "wordlist_file_count": len(wordlist_files),
        "attempted_path_count": len(paths),
        "zap_message_count_before": before,
        "zap_message_count_after": current,
        "discovered_path_count": len(discovered_paths),
        "discovered_paths": discovered_paths,
    }

    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Report: {report_path}")
    print(f"Correlation-ID: {correlation_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
