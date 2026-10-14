"""Read concise status for the fresh PH1-REAL-ROUTE-1 service tasks."""
import argparse
import json
from pathlib import Path

import run_cluster_workflow_probe as probe

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'discovery/t01-phase1-real/m1-p4-20260922'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('batches',nargs='+')
    args=ap.parse_args()
    for name in args.batches:
        assert name.startswith('r') and name[1:].isdigit()
        batch=json.loads((BASE/name/'batch.json').read_bytes())
        value=probe.tool(batch,'workflow.get',dict(job_id=batch['job_id']))
        active=[(n,r['state']) for n,r in value['nodes'].items()
            if r['state'] not in ('not_executed','skipped','unavailable')]
        print(name,value['state'],value.get('error_code'),active[-8:])


if __name__=='__main__':main()
