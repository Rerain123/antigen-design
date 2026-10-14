"""Strict provider binding and source-to-bound hash evidence."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..catalog import SpecificationBundle
from ..jsonio import ContractError, canonical_sha256, load_json, sha256_bytes
from ..paths import PROJECT_ROOT, resolve_project_relative
from .generator import render_all
from .validator import load_yaml_bytes, validate_workflow_document


BINDING_SCHEMA_VERSION = "T01-PHASE1-MOCK-M3-PROVIDER-BINDING-SCHEMA-v0.1"
BINDING_DOCUMENT_VERSION = "T01-PHASE1-MOCK-M3-PROVIDER-BINDING-v0.1"
PROFILE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


@dataclass(frozen=True)
class BoundWorkflow:
    role: str
    path: Path
    content: bytes
    sha256: str


def binding_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": BINDING_SCHEMA_VERSION,
        "type": "object",
        "additionalProperties": False,
        "required": [
            "document_type", "binding_version", "binding_profile", "target_profile_ref",
            "dify_version", "dsl_version", "provider_display_name", "mcp_provider_id",
            "target_provider_record_id", "registry_version", "registry_sha256",
            "template_sha256", "tool_ids", "scientific_compute",
        ],
        "properties": {
            "$schema": {"type": "string"},
            "document_type": {"const": "T01_PHASE1_MOCK_PROVIDER_BINDING"},
            "binding_version": {"const": BINDING_DOCUMENT_VERSION},
            "binding_profile": {"type": "string", "pattern": "^[a-z][a-z0-9_-]{0,31}$", "not": {"const": "legacy"}},
            "target_profile_ref": {"type": "string", "pattern": "^dify/t01-phase1-mock-v0\\.1/evidence/m3/[a-z][a-z0-9_-]{0,31}/target-preflight\\.json$"},
            "dify_version": {"type": "string", "minLength": 1},
            "dsl_version": {"const": "0.7.0"},
            "provider_display_name": {"const": "t01-phase1-mock-mcp-v01"},
            "mcp_provider_id": {"type": "string", "minLength": 1},
            "target_provider_record_id": {"type": "string", "format": "uuid"},
            "registry_version": {"type": "string", "minLength": 1},
            "registry_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "template_sha256": {
                "type": "object",
                "additionalProperties": False,
                "required": ["PRIMARY", "DEBUG"],
                "properties": {
                    "PRIMARY": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    "DEBUG": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                },
            },
            "tool_ids": {"type": "array", "minItems": 26, "maxItems": 26, "uniqueItems": True, "items": {"type": "string"}},
            "scientific_compute": {"const": False},
        },
    }


def validate_manifest(manifest: dict[str, Any], bundle: SpecificationBundle | None = None) -> None:
    bundle = bundle or SpecificationBundle.load()
    errors = sorted(Draft202012Validator(binding_schema()).iter_errors(manifest), key=lambda item: list(item.path))
    if errors:
        first = errors[0]
        raise ContractError(f"binding manifest schema error at /{'/'.join(map(str, first.path))}: {first.message}")
    profile = manifest["binding_profile"]
    if PROFILE_PATTERN.fullmatch(profile) is None or profile == "legacy":
        raise ContractError("invalid or forbidden binding profile")
    registry = bundle.asset_registry
    expected_tools = [item["tool_id"] for item in registry["tool_namespace"]["tools"]]
    if manifest["tool_ids"] != expected_tools:
        raise ContractError("binding tool list must equal the ordered 26-tool registry")
    if manifest["provider_display_name"] != registry["tool_namespace"]["dify_provider_name"]:
        raise ContractError("binding provider display name mismatch")
    if manifest["mcp_provider_id"] != manifest["provider_display_name"]:
        raise ContractError("Dify 1.17 MCP workflow provider ID must equal its stable server identifier")
    registry_path = resolve_project_relative(registry["generation"]["registry_input"], must_exist=True)
    if manifest["registry_version"] != registry["registry_version"] or manifest["registry_sha256"] != sha256_bytes(registry_path.read_bytes()):
        raise ContractError("binding registry version/hash mismatch")
    target_profile = resolve_project_relative(manifest["target_profile_ref"], must_exist=True)
    preflight = load_json(target_profile)
    if preflight.get("binding_profile") != profile or preflight.get("provider", {}).get("record_id") != manifest["target_provider_record_id"]:
        raise ContractError("binding target profile does not match the preflight evidence")
    if preflight.get("provider", {}).get("tool_ids") != expected_tools:
        raise ContractError("preflight provider tool enumeration differs from the registry")


def bind_documents(
    manifest: dict[str, Any],
    *,
    bundle: SpecificationBundle | None = None,
) -> tuple[BoundWorkflow, BoundWorkflow]:
    bundle = bundle or SpecificationBundle.load()
    validate_manifest(manifest, bundle)
    generated = render_all(bundle)
    token = bundle.asset_registry["binding"]["provider_binding_token"]
    provider_id = manifest["mcp_provider_id"]
    prepared: list[BoundWorkflow] = []
    for item in generated:
        actual_template_hash = sha256_bytes(item.content)
        if manifest["template_sha256"][item.role] != actual_template_hash:
            raise ContractError(f"{item.role} template hash drift")
        text = item.content.decode("utf-8")
        if token not in text:
            raise ContractError(f"{item.role} template has no registered binding token")
        bound_text = text.replace(token, provider_id)
        if token in bound_text or "__T01_" in bound_text:
            raise ContractError("bound content retains an unresolved token")
        content = bound_text.encode("utf-8")
        document = load_yaml_bytes(content, f"{item.role} bound DSL")
        validate_workflow_document(
            document,
            bundle=bundle,
            expected_app_name=item.app_name,
            expected_provider_id=provider_id,
            template=False,
        )
        registered = next(entry for entry in bundle.asset_registry["binding"]["bound_outputs"] if entry["workflow_id"] == item.workflow_id)
        relative = registered["output_path_template"].format(binding_profile=manifest["binding_profile"])
        output_path = resolve_project_relative(relative)
        prepared.append(BoundWorkflow(item.role, output_path, content, sha256_bytes(content)))
    return tuple(prepared)  # type: ignore[return-value]


def write_bound_atomic(items: tuple[BoundWorkflow, BoundWorkflow]) -> None:
    temporary: list[tuple[Path, Path]] = []
    try:
        for item in items:
            item.path.parent.mkdir(parents=True, exist_ok=True)
            temp = item.path.with_suffix(item.path.suffix + ".tmp")
            temp.write_bytes(item.content)
            temporary.append((temp, item.path))
        for temp, target in temporary:
            os.replace(temp, target)
    finally:
        for temp, _ in temporary:
            temp.unlink(missing_ok=True)


def binding_evidence(manifest_path: Path, items: tuple[BoundWorkflow, BoundWorkflow]) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    return {
        "document_type": "T01_PHASE1_MOCK_M3_BINDING_EVIDENCE",
        "evidence_version": "T01-PHASE1-MOCK-M3-BINDING-EVIDENCE-v0.1",
        "binding_profile": manifest["binding_profile"],
        "result": "PASS",
        "registry_sha256": manifest["registry_sha256"],
        "template_sha256": manifest["template_sha256"],
        "binding_manifest_sha256": sha256_bytes(manifest_path.read_bytes()),
        "bound_sha256": {item.role: item.sha256 for item in items},
        "tool_count": len(manifest["tool_ids"]),
        "unresolved_token_count": 0,
        "secret_finding_count": 0,
        "scientific_compute": False,
        "manifest_content_sha256": canonical_sha256(manifest),
    }
