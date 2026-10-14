"""Verify the completed r02 MCP response and save its exact HTML attachment."""
import base64
import hashlib
import json
import prepare_m1_p1_deploy as common
from host_panel_followup_probe import REMOTE,OUT

if __name__=='__main__':
    task=json.loads((OUT/'host-panel-flow-submit-r02.json').read_bytes())
    old="downloads.append(dict(file_name=attachment['fileName'],bytes=len(raw),sha256=expected,verified=True))"
    new="downloads.append(dict(file_name=attachment['fileName'],bytes=len(raw),sha256=expected,verified=True,html_base64=__import__('base64').b64encode(raw).decode() if attachment['fileName']=='antigen-report.html' else None))"
    assert old in REMOTE
    value=common.remote(REMOTE.replace(old,new),dict(action='status',job_id=task['job_id']))
    assert value['state']=='succeeded' and value['facts']['design']['count']==0
    assert 'DESIGN_NOT_EXECUTED' in value['card_summary'] and 'N11 候选设计未执行' in value['card_summary']
    for name in ('rescore','design_audit'):
        assert value['nodes'][name]['state']=='skipped'
        assert value['nodes'][name]['reason_code']=='NO_DESIGNABLE_POSITIONS'
    assert len(value['controlled_downloads'])==3
    for item in value['controlled_downloads']:
        encoded=item.pop('html_base64',None)
        if encoded is not None:
            raw=base64.b64decode(encoded,validate=True)
            assert hashlib.sha256(raw).hexdigest()==item['sha256']
            html=raw.decode()
            assert '第一版临时宿主面板' in html and 'MHC-II 未评估' in html
            assert 'NO_DESIGNABLE_POSITIONS' in html
            (OUT/'antigen-report-r02.html').write_bytes(raw)
    value['idle_after_completion']=common.idle()
    assert not value['idle_after_completion']['active_jobs']
    (OUT/'host-flow-final-r02.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(state=value['state'],summary=value['card_summary'],downloads=value['controlled_downloads'],
        idle_after_completion=value['idle_after_completion']),ensure_ascii=False))
