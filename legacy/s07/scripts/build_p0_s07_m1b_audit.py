"""Rebuild P0-M1B reports from an already captured campaign."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

from t01_s07_candidate import build_output_audit  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    args = parser.parse_args()
    audit = build_output_audit(args.campaign_root)
    print(
        json.dumps(
            {
                "campaign_id": audit["campaign_id"],
                "file_count": audit["inventory"]["file_count"],
                "report": str(
                    (args.campaign_root / "reports" / "P0_M1B_OUTPUT_AUDIT.md").resolve()
                ),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
