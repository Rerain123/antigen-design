"""Read-only historical PCV2 early rejection, preserving its original count<=12 rule."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from t01_phase1_real.common import encode,sha
from t01_phase1_real.development.workflow.revision_evaluation import foldx_pool


def replay():
    source=ROOT/'reports/n14-scope-audit-20260928/stop-confirmation.json'
    original=source.read_bytes();saved=json.loads(original)
    audit=json.loads((ROOT/'reports/n14-scope-audit-20260928/audit-summary.json').read_bytes())
    assert audit['source_sha256']==sha(original)
    request=saved['before']['request'];wt=request['protein_sequence']
    assert saved['parent']['state']==saved['child']['state']=='cancelled' and saved['execution']['tree_stopped']
    validations=saved['execution']['nodes']['validation']['fact']['records'];records=[]
    assert len(validations)==len(request['variants'])==24
    for variant,validation in zip(request['variants'],validations):
        sequence=list(wt);positions=[]
        for mutation in variant['mutations']:
            p=mutation['position'];assert wt[p-1]==mutation['wt'] and mutation['mut']!=mutation['wt']
            assert p not in positions;positions.append(p);sequence[p-1]=mutation['mut']
        sequence=''.join(sequence);assert sha(sequence.encode())==validation['sequence_sha256']
        count=sum(a!=b for a,b in zip(wt,sequence))
        burden=validation['mutation_burden'];thresholds=burden['engineering_thresholds']
        assert thresholds['objective']=='general' and thresholds['limits']['count']==12
        assert count==burden['values']['count'] and count>12 and validation['burden_exceeded'] is True
        records.append(dict(candidate_id=variant['variant_id'],content_hash=sha(sequence.encode()),stage='formal',
            sequence=sequence,mutations=variant['mutations'],hard_check_status='FAIL',
            constraint_check=dict(check_status='FAIL',reason_codes=['LEGACY_COUNT_EXCEEDED']),
            original_count_limit=12,independently_recomputed_count=count))
    pool=foldx_pool(records,None,20,mode='variant_score',task_id=saved['parent']['job_id'])
    assert pool['results']==[] and len(pool['excluded'])==24 and pool['reason_codes']==['SKIPPED_EMPTY']
    assert source.read_bytes()==original
    return dict(status='PASS',evidence_kind='HISTORICAL_READ_ONLY_REPLAY',source=str(source.relative_to(ROOT)),
        source_sha256=sha(original),run_id=saved['parent']['run_id'],original_rule='v10.5 general count<=12',
        records=records,foldx_selected=0,rejected_before_foldx=24,repairpdb_calls=0,buildmodel_calls=0,
        new_scientific_jobs=0,archived_source_unchanged=True,
        proves='Known hard failure is excluded before FoldX; not a new constrained-generation or performance result')


if __name__=='__main__':
    result=replay();out=ROOT/'reports/expert-revision-core-20260929';out.mkdir(parents=True,exist_ok=True)
    (out/'historical-early-filter.json').write_bytes(encode(result)+b'\n')
    print(json.dumps({k:result[k] for k in ('status','rejected_before_foldx','foldx_selected','new_scientific_jobs')}))
