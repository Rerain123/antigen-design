"""User-requested screenshot sequence run through the deployed HiMat MCP."""
import argparse
import base64
import json
from pathlib import Path
import prepare_m1_p1_deploy as common
import first_version_flow_probe as original
from version_bundle import encode,sha

OUT=common.ROOT/'reports/pcv2-full-20260928'
SEQUENCE=('MRHRPIFRRRPRPRRRRRHRRRYVRRKLFIRRPTAGTYYTKKYSTM'
          'NVISVGTPQNNKPWHANHFITRLNEWETAISFEYYKILKMKVTLSPVISPAQ'
          'QTKTMFGHTAIDLDGAWTTNTWLQDDPYAESSTRKVMTSKKKHSRYFTPK'
          'PILAGTTSAHPGQSLFFFSRPTPWLNTYDPTVQWGALLWSIYVPEKTGMTD'
          'FYGTKEVWIRYKSVL')
ARGS=dict(protein_sequence=SEQUENCE,host_species='猪',run_key='pcv2-cap-user-full-20260928-r01')
REMOTE=original.REMOTE
REMOTE=REMOTE.replace("old=rt.get(p['old']);body=decode(rt._request_bytes(old))", "body=p['args']")
REMOTE=REMOTE.replace("args=dict(protein_sequence=body['protein_sequence'],host_species=body['host_species'],run_key='first-version-flow-20260926-r01')", "args=p['args']")
REMOTE=REMOTE.replace("source_request_job=p['old']", "input_origin='USER_SCREENSHOT_20260928'")
REMOTE=REMOTE.replace("downloads.append(dict(file_name=attachment['fileName'],bytes=len(raw),sha256=expected,verified=True))",
    "downloads.append(dict(file_name=attachment['fileName'],bytes=len(raw),sha256=expected,verified=True,content_base64=__import__('base64').b64encode(raw).decode()))")


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','status'])
    action=parser.parse_args().action;OUT.mkdir(parents=True,exist_ok=True)
    assert len(SEQUENCE)==214
    receipt=OUT/'submission.json'
    if action=='start':
        if receipt.exists():
            print(receipt.read_text(encoding='utf8'));return
        idle=common.idle()
        if idle['active_jobs'] or idle['gpu_state']['phase']!='idle':raise RuntimeError('Existing active work; do not duplicate')
        (OUT/'preflight.json').write_bytes(encode(idle))
        (OUT/'input.json').write_bytes(encode(dict(args=ARGS,sequence_sha256=sha(SEQUENCE.encode()),
            label='用户提供：猪圆环病毒二型 Cap 蛋白',sequence_length=len(SEQUENCE),
            user_authorization='现在可以调用工具完整的跑一次吗；2026-09-28',
            confirmation_policy='No T4/R57 consent inferred; preserve backend confirmation gates')))
        value=common.remote(REMOTE,dict(action='start',args=ARGS))
        receipt.write_bytes(encode(value))
    else:
        submitted=json.loads(receipt.read_bytes())
        value=common.remote(REMOTE,dict(action='status',job_id=submitted['job_id']))
        for item in value['controlled_downloads']:
            raw=base64.b64decode(item.pop('content_base64'),validate=True)
            name=item['file_name']
            if Path(name).name!=name or '/' in name or '\\' in name:raise ValueError('Invalid attachment filename')
            assert sha(raw)==item['sha256']
            (OUT/name).write_bytes(raw)
        (OUT/'latest-status.json').write_bytes(encode(value))
        if value['state'] in ('succeeded','failed','timed_out','cancelled'):
            (OUT/'final.json').write_bytes(encode(value))
    print(json.dumps(value,ensure_ascii=False))


if __name__=='__main__':main()
