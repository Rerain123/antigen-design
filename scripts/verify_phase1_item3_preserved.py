"""Read-only N09 database and frozen-asset checks, preserving prior receipts."""
import json

import prepare_m1_p1_deploy as common
import prepare_phase1_item3 as deploy
from verify_n09_swissprot import REMOTE
from t01_phase1_mock.dify.campaign import verify_freeze_manifest


if __name__=='__main__':
    value=dict(n09=common.remote(REMOTE,dict(files=[])),frozen=verify_freeze_manifest())
    with (deploy.EVIDENCE/'preserved-capabilities-r01.json').open('x',encoding='utf8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2)
    print(json.dumps(value))
