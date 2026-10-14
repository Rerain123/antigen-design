"""Run a fresh P0-M1B S-07 output-audit campaign and build its reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# Keep an explicitly supplied substituted drive (for example P:) intact.  The
# Windows BLAST LMDB reader cannot open this project's non-ASCII physical path.
WORKSPACE = Path(__file__).absolute().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

from t01_s07_candidate import build_output_audit, run_campaign  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument(
        "--plan",
        type=Path,
        default=WORKSPACE / "discovery" / "p0" / "s07" / "p0-s07-m1b-plan-v0.1.json",
    )
    parser.add_argument(
        "--campaign-root",
        type=Path,
        help="Defaults to discovery/p0/s07/<campaign-id> under the workspace.",
    )
    parser.add_argument("--blast-bin", type=Path)
    parser.add_argument("--blast-db", type=Path)
    parser.add_argument("--skip-network", action="store_true")
    parser.add_argument("--skip-blast", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    campaign_root = args.campaign_root or (
        WORKSPACE / "discovery" / "p0" / "s07" / args.campaign_id
    )
    summary = run_campaign(
        workspace=WORKSPACE,
        plan_path=args.plan,
        campaign_root=campaign_root,
        campaign_id=args.campaign_id,
        blast_bin=args.blast_bin,
        blast_db=args.blast_db,
        skip_network=args.skip_network,
        skip_blast=args.skip_blast,
    )
    audit = build_output_audit(campaign_root)
    result = {
        "campaign_root": str(campaign_root.resolve()),
        "execution_status": summary["execution_status"],
        "capture_count": summary["capture_count"],
        "capture_process_failure_count": summary["capture_process_failure_count"],
        "file_count": audit["inventory"]["file_count"],
        "total_size_bytes": audit["inventory"]["total_size_bytes"],
        "report": str((campaign_root / "reports" / "P0_M1B_OUTPUT_AUDIT.md").resolve()),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
