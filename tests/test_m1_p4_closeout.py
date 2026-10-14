"""Finite closeout may observe/export one existing task, never submit science."""
import json
import sys
import pytest
from t01_phase1_real.common import REPO
sys.path.insert(0,str(REPO/'scripts'))
import finish_m1_p4_run as closeout


@pytest.mark.parametrize('state',['succeeded','failed'])
def test_terminal_closeout_only_collects_existing_task(tmp_path,monkeypatch,state):
    folder=tmp_path/'discovery/t01-phase1-real/m1-p4-20260922/r02';folder.mkdir(parents=True)
    job='t01p1r-job-'+'a'*32
    (folder/'batch.json').write_text(json.dumps(dict(job_id=job,owner='owner')))
    status=tmp_path/'docs/project/STATUS.md';status.parent.mkdir(parents=True)
    status.write_text('P4 主设计新 run：`'+job+'` 计算中。\n',encoding='utf-8')
    calls=[];commands=[]
    def tool(batch,name,args):
        calls.append((name,args))
        return dict(job_id=job,run_id='current-run',terminal=True,state=state,nodes={},error_code=None if state=='succeeded' else 'TOOL_FAILED')
    monkeypatch.setattr(closeout,'ROOT',tmp_path)
    monkeypatch.setattr(closeout.probe,'OUT',folder)
    monkeypatch.setattr(closeout.probe,'tool',tool)
    monkeypatch.setattr(closeout.subprocess,'run',lambda argv,**kwargs:commands.append(argv))
    monkeypatch.setattr(sys,'argv',['closeout','--batch','r02'])
    closeout.main()
    assert calls==[('workflow.get',dict(job_id=job))]
    assert len(commands)==(3 if state=='succeeded' else 1)
    assert all('start' not in argv and 'prepare' not in argv and 'retry' not in argv for argv in commands)
    value=json.loads((folder/'completion.json').read_bytes())
    assert not value['p4_m1_complete'] and not value['target_nr_accepted']
    assert value['controlled_download_and_audit_pass']==(state=='succeeded')
    assert '计算中' not in status.read_text(encoding='utf-8')
