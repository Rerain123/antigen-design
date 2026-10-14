"""Strict JSON and deterministic identity helpers."""

from __future__ import annotations

import hashlib
import json
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any


class ContractError(ValueError):
    """Raised when a frozen contract or runtime object is inconsistent."""


class DuplicateJsonKeyError(ContractError):
    """Raised when a JSON object contains a duplicate member name."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    """Load UTF-8 JSON while rejecting duplicate keys."""

    try:
        return json.loads(
            path.read_text(encoding="utf-8-sig"), object_pairs_hook=_unique_object
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot load JSON {path}: {exc}") from exc


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def pretty_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def stable_uuid4(seed: str) -> str:
    """Return deterministic UUID bytes with RFC 4122 version/variant bits set.

    The identity is deterministic for test reproducibility, but it is opaque to all
    control-flow code and therefore cannot influence scenario projection.
    """

    raw = bytearray(hashlib.sha256(seed.encode("utf-8")).digest()[:16])
    raw[6] = (raw[6] & 0x0F) | 0x40
    raw[8] = (raw[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(raw)))


def deep_copy(value: Any) -> Any:
    return deepcopy(value)
