"""Build or read-only check the two generated Phase 1 Mock Dify templates."""

from __future__ import annotations

import argparse

from t01_phase1_mock.dify.generator import render_all
from t01_phase1_mock.dify.validator import load_yaml_bytes, validate_main_debug_pair, validate_workflow_document
from t01_phase1_mock.jsonio import ContractError, sha256_bytes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Do not write; reject any generated-template drift.")
    args = parser.parse_args(argv)
    generated = render_all()
    documents = []
    for item in generated:
        validate_workflow_document(
            item.document,
            expected_app_name=item.app_name,
            template=True,
        )
        documents.append(item.document)
        if args.check:
            if not item.output_path.is_file() or item.output_path.read_bytes() != item.content:
                raise ContractError(f"generated template drift: {item.output_path}")
        else:
            item.output_path.parent.mkdir(parents=True, exist_ok=True)
            item.output_path.write_bytes(item.content)
        print(f"{item.role} {item.output_path} sha256={sha256_bytes(item.content)}")
    validate_main_debug_pair(documents[0], documents[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
