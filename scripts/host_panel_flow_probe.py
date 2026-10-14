"""User-authorized first-version host-panel run; no T4/R57 consent is invented."""
import argparse
import json
from datetime import datetime,timezone
import prepare_m1_p1_deploy as common
import first_version_flow_probe as original

OUT=common.ROOT/'reports/n05-duration-20260926'
REMOTE=original.REMOTE.replace('first-version-flow-20260926-r01','host-panel-flow-20260926-r01')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=('start','status'));args=ap.parse_args()
    receipt=OUT/'host-panel-flow-submit.json'
    if args.action=='start':
        value=common.remote(REMOTE,dict(action='start',old=original.OLD))
        if receipt.exists():assert json.loads(receipt.read_bytes())['job_id']==value['job_id']
        else:receipt.write_text(json.dumps(value,indent=2),encoding='utf8')
    else:
        value=common.remote(REMOTE,dict(action='status',job_id=json.loads(receipt.read_bytes())['job_id']))
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        (OUT/('host-flow-status-'+stamp+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(value,ensure_ascii=False))


if __name__=='__main__':main()
