"""Record item 3 engineering progress without closing unresolved science."""
import json
import xml.etree.ElementTree as ET

import prepare_phase1_item3 as deploy
from t01_phase1_real.common import REPO,encode,sha


def collect():
    cases={}
    for path in sorted(deploy.EVIDENCE.glob('*junit.xml')):
        for case in ET.parse(path).getroot().iter('testcase'):
            key=(case.get('classname'),case.get('name'))
            if case.find('skipped') is not None and key in cases:continue
            cases[key]=case
    assert len(cases)>2400
    assert all(c.find('failure') is None and c.find('error') is None for c in cases.values())
    deployed=json.loads((deploy.EVIDENCE/'deployment-r01.json').read_bytes())
    assert all(sha((REPO/'src/t01_phase1_real'/n).read_bytes())==digest
               for n,digest in deployed['source_hashes'].items())
    original=json.loads((REPO/'legacy/project-history/expert/EXPERT_V10_5_REVISION_MANIFEST_20260902.json').read_bytes())
    originals={}
    for row in original['files']:
        raw=(REPO/original['revised_root']/row['Name']).read_bytes()
        assert len(raw)==row['NewBytes'] and sha(raw)==row['NewSHA256'].lower()
        originals[row['Name']]=sha(raw)
    return dict(status='ITEM3_PARTIAL_ENGINEERING_VERIFIED_SCIENTIFIC_BRANCHES_PENDING',
        generation=deployed['generation'],source_hashes=deployed['source_hashes'],
        tests=dict(passed=sum(c.find('skipped') is None for c in cases.values()),
                   skipped=sum(c.find('skipped') is not None for c in cases.values())),
        expert_originals=originals,
        completed=['C44 immutable expert parameter verification and defined intrinsic intermediate terms',
            'N10 explicit C44 unavailable output with concrete dependencies; no fabricated score',
            'S40 score normalization and weighted subset calculation; unreliable observed dimensions excluded',
            'N10 same-run structure verification and corrected PROPKA pending-step disclosure'],
        preserved=['N02 raw RSA, out-of-domain rejection and null missing positions',
            'N09 exact Swiss-Prot annotations, structural components and guarded S27 inputs'],
        remaining=['OI-025 alternating-pattern convention, Roseman asset and derived calibration; full C44 unavailable',
            'OI-006/031 formal core_map and unresolved geometry semantics',
            'OI-015/027 structure/RSA scientific acceptance',
            'OI-032 sequence AGGRESCAN asset and spatial classification',
            'OI-033 flat-curve weighting'],
        actual_overall_score=deployed['result']['developability']['overall_score'],
        scientific_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED',
        new_design_workflow_started=False,new_candidates_generated=False,
        evidence_sha256={p.name:sha(p.read_bytes()) for p in deploy.EVIDENCE.iterdir() if p.is_file()})


if __name__=='__main__':
    value=collect()
    with (deploy.EVIDENCE/'closeout-r01.json').open('xb') as stream:stream.write(encode(value))
    print(json.dumps({k:value[k] for k in ('status','generation','tests')}))
