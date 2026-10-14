"""Independently audit the corrected expert-diagram route on fresh service jobs."""
import argparse
import json
from pathlib import Path
from audit_m1_p4 import ROOT, audit as audit_p4, read

BASE=ROOT/'discovery/t01-phase1-real/m1-p4-20260922'


CHILD_TOOL_NODES = {'prediction':'N01','structure':'N01','bepipred':'N04',
    'netmhc':'N05','epitope_map':'N06','glycosylation':'N07','developability':'N10'}


def check_node_labels(rows, records):
    for name, record in records.items():
        stage=rows[name]['node_id']
        tool_node=stage
        if name.startswith(('rep1_','rep2_','rep3_','wt_')):
            kind=name.split('_',1)[1]
            if kind in CHILD_TOOL_NODES:
                assert stage==('N12' if kind in ('prediction','structure') else 'N13')
                tool_node=CHILD_TOOL_NODES[kind]
            elif name=='wt_foldx':
                assert stage=='N17'
                tool_node='N14'
        assert record['job']['node_id']==tool_node


def route_checks(folder):
    batch=read(folder/'batch.json');snap=read(folder/'workflow-snapshot.json')
    rows=snap['nodes'];branch=batch['branch'];parent=snap['job']
    assert batch['database_kind']=='target-nr'
    assert not {'selection_report','base_report'} & set(rows)
    records={n:read(folder/(n+'.json')) for n,r in rows.items() if r.get('job_id')}
    check_node_labels(rows, records)
    if branch=='design':
        assert parent['state']=='succeeded'
        assert [name for name,row in rows.items() if row['node_id']=='N15' and row.get('job_id')]==['variant_report']
        assert rows['preselection']['node_id']=='N12' and rows['preselection']['state']=='succeeded'
        assert rows['preselection']['job_id'] is None and rows['preselection']['origin']=='INTERNAL_FACT'
        fact=rows['preselection']['fact'];selected=fact['selected']
        assert fact['kind']=='N12_REPRESENTATIVE_PRESELECTION'
        assert fact['source']==dict(job_id=records['design_audit']['job']['job_id'],
            artifact=next(r for r in records['design_audit']['job']['artifacts'] if r['role']=='result'))
        assert 1<=len(selected)<=3 and [r['sample_number'] for r in selected]==fact['sample_numbers']
        n13=records['protection'];n14=records['stability'];n15=records['variant_report']
        assert rows['protection']['node_id']=='N13' and rows['stability']['node_id']=='N14'
        assert all(rows[n]['state']=='succeeded' for n in ('design_audit','protection','stability','variant_report','wt_reference','local_delivery'))
        assert records['design_audit']['job']['finished_at']<=rows['preselection']['recorded_at']<=n13['job']['started_at']
        assert n13['job']['finished_at']<=n14['job']['started_at'] and n14['job']['finished_at']<=n15['job']['started_at']
        assert set(n13['request'])=={'protein_sequence','user_sequence_id','upstream','preselection','pairs','timeout_seconds'}
        assert n13['request']['upstream']=={'design_audit':fact['source']}
        assert n13['request']['preselection']==fact
        assert [p['variant_id'] for p in n13['request']['pairs']]==[r['id'] for r in selected]
        assert n13['result']['protection']['preselection']==fact
        assert [r['variant_id'] for r in n13['result']['protection']['records']]==[r['id'] for r in selected]
        wt=records['design']['request']['structure_artifact']
        assert n14['request']['mode']=='buildmodel' and n14['request']['structure_artifact']==wt
        assert [v['variant_id'] for v in n14['request']['variants']]==[r['id'] for r in selected]
        assert [v['mutations'] for v in n14['request']['variants']]==[r['mutations'] for r in selected]
        assert all(r['runs']==len(r['native_ddg_runs'])==5 for r in n14['result']['variant_ddg'])
        assert n15['request']['n13_source']['job_id']==n13['job']['job_id']
        assert n15['request']['upstream']['foldx']['job_id']==n14['job']['job_id']
        assert n15['request']['upstream']['design_audit']==fact['source']
        assert [r['sample_number'] for r in n15['request']['foldx_bindings']]==fact['sample_numbers']
        report=n15['result']['report']
        assert report['kind']=='N15_ENGINEERING_EVALUATION' and report['summary']['total']==24
        assert len(report['records'])==24 and report['summary']['excluded']+report['summary']['undetermined']==24
        assert report['source_receipts']['n13']['state']=='available' and report['source_receipts']['foldx']['state']=='available'
        assert rows['codon']['state'] in ('skipped','succeeded')
        for name in ('wt_foldx','wt_thermompnn','wt_reference'):
            assert records[name]['job']['started_at']>=n15['job']['finished_at']
            assert 'codon' not in records[name]['request'] and 'n16' not in records[name]['request']
        assert records['local_delivery']['job']['started_at']>=records['wt_reference']['job']['finished_at']
        assert records['local_delivery']['request']['upstream']['variant_report']['job_id']==n15['job']['job_id']
        assert records['local_delivery']['request']['upstream']['wt_reference']['job_id']==records['wt_reference']['job']['job_id']
        data=read(folder/'data.json')
        assert data['n16']['reason_code']=='NO_QUALIFIED_CANDIDATE' and data['n16']['dna'] is None
        assert data['variant_report']['kind']=='N15_ENGINEERING_EVALUATION'
    elif branch=='wt':
        assert parent['state']=='succeeded' and rows['design']['job_id'] is None
        assert not any(row['node_id']=='N15' and row.get('job_id') for row in rows.values())
        assert rows['preselection']['state']=='skipped' and rows['protection']['job_id'] is None
        assert rows['stability']['job_id'] is None and rows['variant_report']['job_id'] is None
        assert records['local_delivery']['request']['upstream']['variant_report'] is None
        assert rows['codon']['state']=='skipped' and rows['wt_reference']['state'] in ('succeeded','skipped')
    elif branch in ('failure','cancel'):
        assert parent['state'] in ('failed','cancelled','timed_out')
        assert rows['design']['job_id'] is None and rows['local_delivery']['job_id'] is None
        assert not (folder/'delivery.zip').exists()
    else:raise AssertionError('Unexpected route branch')
    return dict(branch=branch,parent_job_id=parent['job_id'],run_id=parent['run_id'],
        route='N12 -> N13 -> N14 -> N15 -> (N16,N17) -> N18' if branch=='design' else 'WT -> N18' if branch=='wt' else 'FAILED_BEFORE_DESIGN',
        unique_final_n15=branch!='design' or len([r for r in rows.values() if r['node_id']=='N15' and r.get('job_id')])==1)


def audit(folder):
    baseline=audit_p4(folder)
    strict=route_checks(folder)
    return dict(status='PH1_REAL_ROUTE_'+strict['branch'].upper()+'_PASS',baseline=baseline,
        route=strict,scientific_release_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--batch',required=True);args=ap.parse_args()
    assert args.batch.startswith('r') and args.batch[1:].isdigit()
    folder=BASE/args.batch
    result=audit(folder)
    path=folder/'route-audit-summary.json'
    assert not path.exists(), 'Preserve immutable run audit evidence'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(result['status'])


if __name__=='__main__':main()
