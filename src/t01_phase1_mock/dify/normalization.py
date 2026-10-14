"""Narrow main/debug result normalization and JSON-pointer diagnostics."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


OBSERVABILITY_ALLOWLIST = (
    "/dify_observability/app_id",
    "/dify_observability/workflow_id",
    "/dify_observability/workflow_run_id",
    "/dify_observability/role",
)


def normalize_result(value: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(value)
    result.pop("dify_observability", None)
    return result


def first_difference(left: Any, right: Any, pointer: str = "") -> str | None:
    if type(left) is not type(right):
        return pointer or "/"
    if isinstance(left, dict):
        if set(left) != set(right):
            return pointer or "/"
        for key in sorted(left):
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            difference = first_difference(left[key], right[key], f"{pointer}/{escaped}")
            if difference is not None:
                return difference
        return None
    if isinstance(left, list):
        if len(left) != len(right):
            return pointer or "/"
        for index, (l_item, r_item) in enumerate(zip(left, right, strict=True)):
            difference = first_difference(l_item, r_item, f"{pointer}/{index}")
            if difference is not None:
                return difference
        return None
    return None if left == right else (pointer or "/")
