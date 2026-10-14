"""Offline validation of the shared tool boundary; no scientific tool execution."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
import sys

from jsonschema import Draft202012Validator, FormatChecker

BASE = Path(__file__).resolve().parent


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parameters_hash(parameters: dict) -> str:
    return sha256(json.dumps(parameters, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8"))


def strict_json(path: Path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f"non-finite JSON number: {value}")

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                       parse_constant=invalid)
    ensure_finite(value)
    return value


def ensure_finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite JSON number (including exponent overflow)")
    if isinstance(value, dict):
        for child in value.values():
            ensure_finite(child)
    elif isinstance(value, list):
        for child in value:
            ensure_finite(child)


def schema_errors(value, kind: str) -> list[str]:
    ensure_finite(value)
    schema = strict_json(BASE / f"{kind}.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [f"{kind}.{'.'.join(map(str, e.absolute_path)) or '$'}: {e.message}"
            for e in validator.iter_errors(value)]


def local_path(root: Path, relative: str) -> Path:
    """Portable paths only; resolved containment also catches symlink escapes."""
    p = PurePosixPath(relative)
    if (not relative or p.is_absolute() or any(x in relative for x in ("\\", ":"))
            or any(ord(x) < 32 for x in relative) or any(x in (".", "..", "") for x in relative.split("/"))):
        raise ValueError(f"unsafe relative path: {relative!r}")
    result = (root / Path(*p.parts)).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes root: {relative!r}")
    return result


def input_refs(request):
    if request["tool_id"] == "t01.real.freesasa":
        for name in ("structure", "mapping"):
            if request["inputs"][name] is not None:
                yield name, request["inputs"][name]
        if request["parameters"]["config"] is not None:
            yield "config", request["parameters"]["config"]


def request_errors(request) -> list[str]:
    errors = schema_errors(request, "request")
    if errors:
        return errors
    for name, ref in input_refs(request):
        try:
            local_path(Path.cwd(), ref["path"])
        except ValueError as exc:
            errors.append(f"inputs.{name}: {exc}")
    if request["tool_id"] == "t01.real.bepipred":
        p = request["parameters"]
        if p["threshold"] != 0.1512 and p["relaxation_metadata"] is None:
            errors.append("parameters.relaxation_metadata: required when threshold changes")
    if request["run_mode"] == "pipeline":
        low_skip = (request["tool_id"] == "t01.real.freesasa" and request["node_id"] == "N02"
                    and request["inputs"]["quality_confidence"] == "low")
        if not low_skip:
            if request["rule_profile"] is None:
                errors.append("rule_profile: pipeline computation requires an approved profile reference")
            if request["tool_id"] == "t01.real.freesasa":
                if request["inputs"]["mapping_status"] != "verified":
                    errors.append("inputs.mapping_status: pipeline computation requires verified mapping")
                for name, ref in [("structure", request["inputs"]["structure"]),
                                  ("mapping", request["inputs"]["mapping"]),
                                  ("config", request["parameters"]["config"])]:
                    if ref is None or ref["sha256"] is None:
                        errors.append(f"inputs.{name}: pipeline computation requires file and hash")
    return errors


def pair_errors(request, result, request_bytes: bytes | None = None) -> list[str]:
    errors = request_errors(request) + schema_errors(result, "result")
    if errors:
        return errors
    for key in ("contract_version", "tool_id", "request_id", "run_mode"):
        if request[key] != result[key]:
            errors.append(f"result.{key}: does not match request")
    if errors:
        return errors
    p = result["provenance"]
    if request_bytes is not None and p["request_sha256"] != sha256(request_bytes):
        errors.append("provenance.request_sha256: does not match exact request bytes")
    if p["parameters_sha256"] != parameters_hash(request["parameters"]):
        errors.append("provenance.parameters_sha256: does not match parameters")
    if p["rule_profile"] != request["rule_profile"]:
        errors.append("provenance.rule_profile: does not match request")
    if datetime.fromisoformat(p["finished_at"].upper().replace("Z", "+00:00")) < datetime.fromisoformat(p["started_at"].upper().replace("Z", "+00:00")):
        errors.append("provenance.finished_at: precedes started_at")
    status, payload = result["execution_status"], result["result"]
    codes = {i["code"] for i in result["issues"]}
    has_error = any(i["severity"] == "error" for i in result["issues"])
    if (status == "failed") != has_error:
        errors.append("issues: error severity is required exactly for failed results")
    error_codes = {"INVALID_INPUT", "ASSET_MISSING", "HASH_MISMATCH", "TOOL_FAILED", "OUTPUT_INVALID", "TIMEOUT", "CANCELLED"}
    for issue in result["issues"]:
        expected_severity = "error" if issue["code"] in error_codes else "info" if issue["code"] == "QUALITY_LOW" else "warning"
        if issue["severity"] != expected_severity:
            errors.append(f"issues.{issue['code']}: severity must be {expected_severity}")
    if result["review_required"] and not result["issues"]:
        errors.append("issues: review_required needs a concrete explanation")
    if codes & error_codes and status != "failed":
        errors.append("execution_status: error codes require failed")
    review_codes = {"RULES_PENDING", "MAPPING_UNVERIFIED", "MAPPING_UNRELIABLE", "UNSUPPORTED_RESIDUE", "VALUE_OUT_OF_RANGE", "REVIEW_REQUIRED"}
    if codes & review_codes and not result["review_required"]:
        errors.append("review_required: must be true for unresolved rules/data")
    if status == "succeeded" and payload is None and not result["review_required"]:
        errors.append("result: succeeded without payload requires review")
    if status == "succeeded" and payload is None and not codes & review_codes:
        errors.append("issues: succeeded without payload requires a specific unresolved reason")
    if payload is not None and (request["rule_profile"] is None or codes & {"RULES_PENDING", "MAPPING_UNVERIFIED", "MAPPING_UNRELIABLE", "VALUE_OUT_OF_RANGE"}):
        errors.append("result: unresolved rules/mapping/out-of-range values must remain in diagnostics")
    n = len(request["inputs"]["sequence"])
    for issue in result["issues"]:
        if any(pos > n for pos in issue.get("positions", [])):
            errors.append("issues.positions: exceeds input sequence length")
    low_skip = (request["tool_id"] == "t01.real.freesasa" and request["node_id"] == "N02"
                and request["inputs"]["quality_confidence"] == "low")
    if (status == "skipped" and (not low_skip or "QUALITY_LOW" not in codes)) or (low_skip and status == "succeeded"):
        errors.append("execution_status: only N02 FreeSASA quality=low may skip; it must not compute")
    if "QUALITY_LOW" in codes and status != "skipped":
        errors.append("issues.QUALITY_LOW: only valid for a skipped result")
    if low_skip and p["command"]:
        errors.append("provenance.command: N02 quality=low must not invoke FreeSASA")
    if status == "skipped" and (p["command"] or p["tool_exit_code"] is not None):
        errors.append("provenance: skipped invocation must not claim a tool command or exit code")
    if payload is not None:
        if result["tool_id"] == "t01.real.freesasa":
            if request["inputs"]["mapping_status"] != "verified":
                errors.append("result: aligned FreeSASA payload requires verified mapping")
            scores = payload["per_residue"]
            covered = {pos for issue in result["issues"] if issue["code"] in {"MISSING_RESIDUE", "UNSUPPORTED_RESIDUE"} for pos in issue.get("positions", [])}
            if any(v is None and i + 1 not in covered for i, v in enumerate(scores)):
                errors.append("issues.positions: every null residue needs a missing/unsupported explanation")
        else:
            scores = payload["linear_scores"]
            previous_end = 0
            for peak in payload["linear_peaks"]:
                if not (previous_end < peak["start"] <= peak["end"] <= n):
                    errors.append("result.linear_peaks: intervals must be ordered, non-overlapping, 1-based and within sequence")
                previous_end = peak["end"]
        if len(scores) != n:
            errors.append("result: residue array length differs from input sequence length")
    ids, paths = set(), set()
    for artifact in result["artifacts"]:
        if artifact["artifact_id"] in ids or artifact["path"].casefold() in paths:
            errors.append("artifacts: duplicate id or path (case-insensitive portable paths)")
        ids.add(artifact["artifact_id"])
        paths.add(artifact["path"].casefold())
        if artifact["path"].casefold() == "result.json":
            errors.append("artifacts: result.json cannot reference/hash itself")
        try:
            local_path(Path.cwd(), artifact["path"])
        except ValueError as exc:
            errors.append(f"artifacts: {exc}")
    environments = {a["artifact_id"] for a in result["artifacts"] if a["role"] == "environment"}
    if p["environment_artifact_id"] is not None and p["environment_artifact_id"] not in environments:
        errors.append("provenance.environment_artifact_id: must identify an environment artifact")
    if status == "succeeded":
        if p["tool_version"] is None or not p["command"] or p["tool_exit_code"] != 0:
            errors.append("provenance: succeeded requires tool version, command and zero tool exit code")
        if p["environment_artifact_id"] not in environments or not any(a["role"] == "raw" for a in result["artifacts"]):
            errors.append("artifacts: succeeded requires raw and environment evidence references")
    return errors


def check_files(request, result, request_dir: Path, output_dir: Path) -> list[str]:
    errors = []
    files = [(request_dir, ref, f"input {name}") for name, ref in input_refs(request)]
    if result is not None:
        files += [(output_dir, a, f"artifact {a['artifact_id']}") for a in result["artifacts"]]
    for root, ref, label in files:
        try:
            path = local_path(root, ref["path"])
            content = path.read_bytes()
            if ref["sha256"] is None or sha256(content) != ref["sha256"]:
                errors.append(f"{label}: missing or mismatched SHA-256")
            if "size_bytes" in ref and len(content) != ref["size_bytes"]:
                errors.append(f"{label}: size_bytes mismatch")
        except (OSError, ValueError) as exc:
            errors.append(f"{label}: {exc}")
    if not errors and request['tool_id'] == 't01.real.freesasa' and request['inputs']['mapping'] is not None:
        spec = importlib.util.spec_from_file_location('local_mapping_validator', BASE / 'structure_mapping/validate_mapping.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        ref = request['inputs']['mapping']
        structure_ref = request['inputs']['structure']
        try:
            value = strict_json(local_path(request_dir, ref['path']))
            errors += module.validate_mapping(value, sequence=request['inputs']['sequence'],
                                               structure_sha256=structure_ref['sha256'] if structure_ref else None,
                                               expected_status=request['inputs']['mapping_status'])
        except (OSError, ValueError) as exc:
            errors.append(f'mapping: {exc}')
    return errors


def validate_paths(request_path: Path, result_path: Path | None = None, check_file_bytes=False) -> list[str]:
    request = strict_json(request_path)
    result = strict_json(result_path) if result_path else None
    errors = pair_errors(request, result, request_path.read_bytes()) if result is not None else request_errors(request)
    if check_file_bytes and not errors:
        errors += check_files(request, result, request_path.parent, result_path.parent if result_path else Path.cwd())
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--check-files", action="store_true", help="Check local file bytes, size and hashes; never fetch URLs")
    parser.add_argument("--examples", action="store_true", help="Check all bundled synthetic examples and artifact bytes")
    args = parser.parse_args(argv)
    if args.examples and (args.request or args.result or args.check_files):
        parser.error("--examples cannot be combined with other options")
    if not args.examples and not args.request:
        parser.error("provide --request or --examples")
    try:
        if args.examples:
            paths = sorted((BASE / "examples").glob("*/request.json"))
            if not paths:
                raise ValueError("no example requests found")
            errors = [f"{p.parent.name}: {e}" for p in paths for e in validate_paths(p, p.parent / "output/result.json", True)]
            count = len(paths)
        else:
            errors = validate_paths(args.request, args.result, args.check_files)
            count = 1
    except (OSError, ValueError) as exc:
        errors, count = [str(exc)], 0
    print(json.dumps({"status": "FAIL" if errors else "PASS", "checked": count,
                      "scope": "engineering_contract_only", "scientific_acceptance": "NOT_EVALUATED",
                      "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
