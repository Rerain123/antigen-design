"""Execute all PH1-MOCK-M2 blocker assertions and write the compact result."""

from __future__ import annotations

from t01_phase1_mock import AcceptanceHarness


def main() -> int:
    report = AcceptanceHarness().run_and_write()
    print(
        f"m2_acceptance={report['status']} "
        f"cases={report['case_count']} "
        f"submissions={report['submission_count']} "
        f"checkpoints={report['checkpoint_count']} "
        f"blockers={report['blocker_assertion_count']} "
        f"failures={report['blocker_failure_count']}"
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
