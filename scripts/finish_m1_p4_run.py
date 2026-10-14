"""Finite closeout of one already-submitted service task; never submits or retries science."""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime,timezone
from pathlib import Path
import run_cluster_workflow_probe as probe

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--batch',default='r02');a=ap.parse_args()
    folder=ROOT/'discovery/t01-phase1-real/m1-p4-20260922'/a.batch
    batch=json.loads((folder/'batch.json').read_bytes());probe.OUT=folder
    end=time.monotonic()+9*3600;last=None;errors=0
    def save(name,value):
        (folder/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    save('closeout-process.json',dict(pid=os.getpid(),job_id=batch['job_id'],started_at=datetime.now(timezone.utc).isoformat(),
        bounded_hours=9,science_submission_allowed=False,public_publication_allowed=False))
    while time.monotonic()<end:
        try:
            value=probe.tool(batch,'workflow.get',dict(job_id=batch['job_id']));errors=0
        except Exception as exc:
            errors+=1;print('QUERY_RETRY',type(exc).__name__,errors,flush=True)
            if errors>=10:raise
            time.sleep(45);continue
        active=[n for n,r in value.get('nodes',{}).items() if r['state'] in ('running','reconciling')]
        marker=(value['state'],tuple(active))
        if marker!=last:
            print(datetime.now(timezone.utc).isoformat(),value['state'],active,flush=True);last=marker
        save('closeout-state.json',dict(job_id=batch['job_id'],state=value['state'],active_nodes=active,
            observed_at=datetime.now(timezone.utc).isoformat(),error_code=value['error_code']))
        if value['terminal']:
            probe.save('status.json',value)
            commands=[['scripts/run_m1_p4_probe.py','collect','--batch',a.batch]]
            if value['state']=='succeeded':commands += [
                ['scripts/run_m1_p4_probe.py','download','--batch',a.batch],['scripts/audit_m1_p4.py','--batch',a.batch]]
            for argv in commands:subprocess.run([sys.executable,'-X','utf8','-B',*argv],cwd=ROOT,check=True)
            complete=value['state']=='succeeded'
            summary=dict(status='ENGINEERING_COMPLETED_TARGET_NR_PENDING' if complete else 'ENGINEERING_RUN_FAILED',
                job_id=batch['job_id'],run_id=value['run_id'],error_code=value['error_code'],
                native_evidence_retained=True,controlled_download_and_audit_pass=complete,p4_m1_complete=False,
                target_nr_accepted=False,scientific_release_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')
            save('completion.json',summary)
            status=ROOT/'docs/project/STATUS.md';text=status.read_text(encoding='utf-8')
            prefix='P4 主设计新 run：'
            lines=text.splitlines()
            for i,line in enumerate(lines):
                if line.startswith(prefix) and batch['job_id'] in line:
                    if complete:
                        lines[i]=prefix+'`'+batch['job_id']+'` 已成功完成自动接续；[原生证据、受控报告/ZIP 与独立审计](../../discovery/t01-phase1-real/m1-p4-20260922/'+a.batch+'/completion.json)通过。此为 engineering-n03 工程验证，目标 nr 与 P4/M1 最终验收仍待完成。'
                    else:
                        lines[i]=prefix+'`'+batch['job_id']+'` 已终止为 `'+value['state']+' / '+str(value['error_code'])+'`；[原生诊断](../../discovery/t01-phase1-real/m1-p4-20260922/'+a.batch+'/completion.json)已保留，未生成成功交付声明；需要处理该失败后重新验证。'
                    status.write_text('\n'.join(lines)+'\n',encoding='utf-8');break
            print(summary['status'],flush=True);return
        time.sleep(45)
    raise TimeoutError('Bounded closeout deadline reached; service task was not cancelled or resubmitted')


if __name__=='__main__':main()
