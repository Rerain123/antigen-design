"""Bind target Dify provider identity into generated templates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from t01_phase1_mock.dify.binding import bind_documents, binding_evidence, write_bound_atomic
from t01_phase1_mock.jsonio import ContractError, load_json
from t01_phase1_mock.paths import PROJECT_ROOT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args(argv)
    manifest_path = args.manifest.resolve()
    manifest = load_json(manifest_path)
    items = bind_documents(manifest)
    if args.check:
        for item in items:
            if not item.path.is_file() or item.path.read_bytes() != item.content:
                raise ContractError(f"bound workflow drift: {item.path}")
    else:
        write_bound_atomic(items)
    evidence_path = args.evidence
    if evidence_path is not None:
        evidence_path = evidence_path.resolve()
        evidence_path.relative_to(PROJECT_ROOT.resolve())
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            json.dumps(binding_evidence(manifest_path, items), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    for item in items:
        print(f"{item.role} {item.path} sha256={item.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
