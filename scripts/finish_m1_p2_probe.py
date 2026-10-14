"""Refresh N12 after the executor profile change; retain all original evidence."""
import copy
import json
import run_m1_p2_probe as p


def main():
    task=p.context()
    score=p.run_step(task,'esm-if1-r08','t01.real.esm_if1',p.local('esm-if1')['request'])
    body=copy.deepcopy(p.local('design-audit')['request'])
    body['upstream']['esm_if1']=p.ref(score)
    audit=p.run_step(task,'design-audit-r08','t01.real.design_audit',body)
    body=copy.deepcopy(p.local('base-report')['request'])
    body['upstream']['design_audit']=p.ref(audit)
    base=p.run_step(task,'base-report-r08','t01.real.variant_report',body)
    from t01_phase1_real.development.variant_report.m1 import selection
    numbers=selection(base['result']['report']['records'])
    original=json.loads((p.OUT/'selection.json').read_bytes())['sample_numbers']
    assert numbers==original,'Refreshed scoring changed representatives; requires actual recomputation'
    n13=copy.deepcopy(p.local('protection')['request'])
    n13['upstream']['base_report']=p.ref(base)
    protection=p.run_step(task,'protection-r08','t01.real.epitope_protection',n13)
    body['n13_source']=p.ref(protection)
    names=('epitope_map','glycosylation','developability')
    body['m1_test']=dict(wt={n:p.ref(p.local('wt-'+n.replace('_','-'))) for n in names},
        representatives=[dict(sample_number=i,**{n:p.ref(p.local('sample-'+str(i)+'-'+n.replace('_','-')))
            for n in ('prediction','structure',*names)}) for i in numbers])
    p.run_step(task,'final-report','t01.real.variant_report',body)


if __name__=='__main__':main()
