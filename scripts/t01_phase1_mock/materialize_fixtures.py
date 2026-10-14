"""Materialize the closed PH1-MOCK-M2 synthetic fixture set."""

from __future__ import annotations

import argparse

from t01_phase1_mock import FixtureMaterializer, FixtureRepository


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the existing closed fixture set without writing",
    )
    args = parser.parse_args()
    if args.check:
        counts = FixtureRepository.check()
        operation = "CHECK"
    else:
        result = FixtureMaterializer().materialize()
        counts = result["counts"]
        operation = "BUILD"
    print(
        f"fixture_materialization={operation}_PASS "
        f"inputs={counts['input_fixture_count']} "
        f"requests={counts['request_variant_count']} "
        f"attempts={counts['attempt_fixture_count']} "
        f"payload_files={counts['payload_file_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
