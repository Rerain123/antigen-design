"""Read-only N13 source preflight while the independent native FoldX batch runs."""
import json
import run_m1_p2_probe as p


def main():
    task=p.context();numbers=json.loads((p.OUT/'selection.json').read_bytes())['sample_numbers']
    wt_structure=p.ref(json.loads((p.P1/'structure.json').read_bytes()))
    task['body']=dict(protein_sequence=task['sequence'],user_sequence_id='P2 read-only source preflight',timeout_seconds=60,
        upstream=dict(base_report=p.ref(p.local('selection-report'))),pairs=[dict(variant_id='sample-'+str(n),
        wt=dict(structure=wt_structure,epitope_map=p.ref(p.local('wt-epitope-map')),domains=None),
        variant=dict(structure=p.ref(p.local('sample-'+str(n)+'-structure')),
                     epitope_map=p.ref(p.local('sample-'+str(n)+'-epitope-map')),domains=None)) for n in numbers])
    code=r'''
from t01_phase1_real.development.epitope_protection.source import sources
from t01_phase1_real.development.epitope_protection.compute import evaluate
with rt._db() as db:files,values,receipts=sources(rt,db,task['body'])
result=evaluate(task['body'],files)
print(json.dumps(dict(status='N13_REGISTERED_SOURCE_PREFLIGHT_PASS',registered_task=False,
    not_a_substitute_for_final_n13=True,records=[dict(variant_id=r['variant_id'],observation=r['observation']) for r in result['records']])))
'''
    result=p.deploy.remote(p.PREAMBLE+code,task)
    p.save('n13-source-preflight.json',result)
    print(result['status'])


if __name__=='__main__':main()
