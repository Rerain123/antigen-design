"""Fresh validation of no-generation reporting; preserves the first run unchanged."""
import argparse
import json
from datetime import datetime,timezone
import prepare_m1_p1_deploy as common
import first_version_flow_probe as original
from host_panel_flow_probe import OUT
REMOTE=original.REMOTE.replace('first-version-flow-20260926-r01','host-panel-flow-20260926-r02')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=('start','status'));args=ap.parse_args()
    receipt=OUT/'host-panel-flow-submit-r02.json'
    if args.action=='start':
        value=common.remote(REMOTE,dict(action='start',old=original.OLD))
        if receipt.exists():assert json.loads(receipt.read_bytes())['job_id']==value['job_id']
        else:receipt.write_text(json.dumps(value,indent=2),encoding='utf8')
    else:
        value=common.remote(REMOTE,dict(action='status',job_id=json.loads(receipt.read_bytes())['job_id']))
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        (OUT/('host-flow-r02-status-'+stamp+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(value,ensure_ascii=False))
