"""Capture one immutable HTTP exchange for a T-01 discovery campaign.

This is a discovery evidence helper, not a production S-07 adapter.  It delegates
the request to curl, preserves the raw response and headers, and writes a small
machine-readable exchange record with timestamps and hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


USER_AGENT = "T01-S07-Discovery/0.1 (non-production evidence capture)"

# curl's all-fields `%{json}` includes certificate chains and the effective
# output filename.  On Windows, locale decoding of a non-ASCII workspace path
# can make that large blob invalid JSON even though the request succeeded.
# Capture only the small, audit-relevant fields using a line format whose
# values cannot contain our separator.
CURL_WRITE_OUT_FIELDS = {
    "http_code": "http_code",
    "response_code": "response_code",
    "exitcode": "exitcode",
    "content_type": "content_type",
    "remote_ip": "remote_ip",
    "remote_port": "remote_port",
    "http_version": "http_version",
    "method": "method",
    "num_redirects": "num_redirects",
    "size_download": "size_download",
    "size_upload": "size_upload",
    "time_total": "time_total",
    "ssl_verify_result": "ssl_verify_result",
}
INTEGER_METRICS = {
    "http_code",
    "response_code",
    "exitcode",
    "remote_port",
    "num_redirects",
    "ssl_verify_result",
}
FLOAT_METRICS = {"size_download", "size_upload", "time_total"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exchange-id", required=True)
    parser.add_argument("--method", choices=("GET", "POST"), required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--response-name", required=True)
    parser.add_argument("--body-file", type=Path)
    parser.add_argument("--accept", default="application/json")
    parser.add_argument("--content-type", default="application/json")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument(
        "--resolve",
        help="Optional curl host:port:address override; recorded as transport evidence.",
    )
    parser.add_argument(
        "--ssl-revoke-best-effort",
        action="store_true",
        help="Use curl's Windows best-effort certificate revocation mode; never disables TLS verification.",
    )
    return parser.parse_args()


def parse_curl_metrics(output: str) -> dict[str, object]:
    metrics: dict[str, object] = {}
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key not in CURL_WRITE_OUT_FIELDS:
            continue
        if key in INTEGER_METRICS:
            try:
                metrics[key] = int(value)
            except ValueError:
                metrics[key] = None
        elif key in FLOAT_METRICS:
            try:
                metrics[key] = float(value)
            except ValueError:
                metrics[key] = None
        else:
            metrics[key] = value or None
    return metrics


def main() -> int:
    args = parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise SystemExit(f"refusing to overwrite non-empty evidence directory: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    curl = shutil.which("curl.exe") or shutil.which("curl")
    if curl is None:
        raise SystemExit("curl was not found")

    response_path = args.output_dir / args.response_name
    headers_path = args.output_dir / "response.headers.txt"
    stderr_path = args.output_dir / "curl.stderr.txt"
    request_body_copy: Path | None = None

    command = [
        curl,
        "--silent",
        "--show-error",
        "--request",
        args.method,
        "--url",
        args.url,
        "--header",
        f"Accept: {args.accept}",
        "--header",
        f"User-Agent: {USER_AGENT}",
        "--max-time",
        str(args.timeout_seconds),
        "--dump-header",
        str(headers_path),
        "--output",
        str(response_path),
        "--write-out",
        "\\n".join(
            f"{key}=%{{{variable}}}" for key, variable in CURL_WRITE_OUT_FIELDS.items()
        ),
    ]
    if args.resolve:
        command.extend(["--resolve", args.resolve])
    if args.ssl_revoke_best_effort:
        command.append("--ssl-revoke-best-effort")
    if args.body_file is not None:
        if args.method != "POST":
            raise SystemExit("--body-file is only valid with POST")
        if not args.body_file.is_file():
            raise SystemExit(f"request body does not exist: {args.body_file}")
        request_body_copy = args.output_dir / "request.body.json"
        shutil.copyfile(args.body_file, request_body_copy)
        command.extend(
            [
                "--header",
                f"Content-Type: {args.content_type}",
                "--data-binary",
                f"@{request_body_copy}",
            ]
        )

    started_at = utc_now()
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    finished_at = utc_now()
    stderr_path.write_text(completed.stderr, encoding="utf-8")

    curl_metrics = parse_curl_metrics(completed.stdout)

    exchange = {
        "exchange_id": args.exchange_id,
        "classification": "discovery_evidence",
        "production_deployment_status": "NOT_DEPLOYED",
        "started_at": started_at,
        "finished_at": finished_at,
        "request": {
            "method": args.method,
            "url": args.url,
            "headers": {
                "accept": args.accept,
                "content_type": args.content_type if request_body_copy else None,
                "user_agent": USER_AGENT,
            },
            "body_file": request_body_copy.name if request_body_copy else None,
            "body_sha256": sha256_file(request_body_copy) if request_body_copy else None,
            "timeout_seconds": args.timeout_seconds,
            "connection_override": args.resolve,
            "ssl_revoke_best_effort": args.ssl_revoke_best_effort,
        },
        "response": {
            "body_file": response_path.name if response_path.exists() else None,
            "body_size_bytes": response_path.stat().st_size if response_path.exists() else 0,
            "body_sha256": sha256_file(response_path) if response_path.exists() else None,
            "headers_file": headers_path.name if headers_path.exists() else None,
            "headers_sha256": sha256_file(headers_path) if headers_path.exists() else None,
        },
        "curl": {
            "executable": Path(curl).name,
            "exit_code": completed.returncode,
            "metrics": curl_metrics,
            "stderr_file": stderr_path.name,
            "stderr_sha256": sha256_file(stderr_path),
        },
    }
    (args.output_dir / "exchange.json").write_text(
        json.dumps(exchange, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(json.dumps(exchange, indent=2, ensure_ascii=False))
    return 0 if completed.returncode == 0 else completed.returncode


if __name__ == "__main__":
    sys.exit(main())
