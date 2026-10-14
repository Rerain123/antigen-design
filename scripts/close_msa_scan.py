"""Collect actual release evidence; does not change plans or scientific gates."""
import json
import subprocess
import sys
from pathlib import Path
from version_bundle import encode,sha
import deploy_msa_scan as release

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/msa-scan-20260928'


def read(name):return json.loads((OUT/name).read_bytes())


def main():
    checks=release.regression();deployment=read('deployment-verification.json')
    msa=read('af3-native-msa-replay.json');scan=read('n17-native-replay.json')
    tensor=read('thermompnn-tensor-equivalence.json')
    assert deployment['status']=='PASS' and deployment['new_jobs']==0
    assert msa['new_jobs']==scan['new_jobs']==0 and any(r['status']=='PASS' for r in msa['records'])
    assert all(r['status']=='PASS' for r in scan['records'])
    done=subprocess.run([sys.executable,'-X','utf8','-B','scripts/check_docs.py'],cwd=ROOT,capture_output=True)
    doc=dict(exit_code=done.returncode,stdout=done.stdout.decode('utf8'),stderr=done.stderr.decode('utf8'))
    (OUT/'docs-check.json').write_bytes(encode(doc));assert done.returncode==0
    names=('deployment-verification.json','af3-native-msa-replay.json','n17-native-replay.json','real-skip-replay.json',
        'control-report-replay.json','thermompnn-tensor-equivalence.json','upstream-inspection.json','predeploy-imports.json',
        'full.junit.xml','final-affected.junit.xml','docker-recheck.junit.xml','tested-source.json','frozen.json','docs-check.json')
    value=dict(status='ENGINEERING_DELIVERED_WITH_EXPLICIT_NATIVE_VALIDATION_GAPS',items=[1,6],
        authority=dict(version='v10.5_20260902',sections=['Structure ToolSpec 2b','FoldX ToolSpec RepairPDB/PositionScan','C43 full SSM']),
        user_authorization='允许实现并接入后续流程；本次不提交新的科学任务',
        completed=dict(wt_msa='Same-run native WT MSA replay/reuse, one persisted preparation-only child when absent, all AF3 validation rounds share it; exact query, homolog, host, source and stop guards.',
            foldx='16-position batches, one RepairPDB, byte-verified bounded archives, complete coverage merge; missing/corrupt batches never publish partial scores.',
            thermompnn='Recorded project adapter around pinned official SSM; 320 mutations/batch, one whole-WT embedding, per-batch CPU outputs, full 20xL CSV required; upstream files unchanged.'),
        deployment={k:deployment[k] for k in ('generation','pod','source_sha256','files_per_snapshot','job_count','new_jobs')},
        regression=dict(total=checks['total'],passed=checks['total']-checks['skipped'],skipped=checks['skipped'],
            initial_docker_failures=3,docker_recheck_passed=6,frozen_assets=read('frozen.json')['frozen_asset_count']),
        native_replays=dict(msa_passed=sum(r['status']=='PASS' for r in msa['records']),
            msa_blocked=[r for r in msa['records'] if r['status']!='PASS'],n17_passed=len(scan['records'])),
        tensor_equivalence=tensor,
        remaining=['No new native WT MSA preparation or candidate AF3 inference this turn; archived-native reuse projection only.',
            'No new large-scope native FoldX/ThermoMPNN performance run or long-sequence capacity qualification.',
            'FoldX archives remain bounded: 32MiB compressed/256MiB expanded each, 128MiB/128 files for job collection. Large-structure capacity is not guaranteed by batching.',
            'R04 ambiguous routes, N17 membrane/sequence-only conflicts and rank-comparison gaps remain; L4/geometric and CamSol expert gaps unchanged.'],
        new_scientific_jobs=0,scientific_eligible=False,evidence={n:sha((OUT/n).read_bytes()) for n in names})
    (OUT/'closeout.json').write_bytes(encode(value))
    print(json.dumps({k:value[k] for k in ('status','deployment','regression','native_replays')}))


if __name__=='__main__':main()
