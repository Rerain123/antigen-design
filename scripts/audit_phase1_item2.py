"""Read-only completion audit over item 2 deployment and execution evidence."""
import json
import xml.etree.ElementTree as ET

import prepare_phase1_item2 as deploy
from t01_phase1_real.common import REPO,encode,sha


def collect():
    reports=sorted(deploy.EVIDENCE.glob('*junit.xml'));latest={}
    for path in reports:
        for case in ET.parse(path).getroot().iter('testcase'):
            key=(case.get('classname'),case.get('name'))
            if case.find('skipped') is not None and key in latest:continue
            latest[key]=case
    assert len(latest)>2400
    assert all(c.find('failure') is None and c.find('error') is None for c in latest.values())
    manifest=json.loads((REPO/'legacy/project-history/expert/EXPERT_V10_5_REVISION_MANIFEST_20260902.json').read_bytes())
    root=REPO/manifest['revised_root'];originals={}
    for item in manifest['files']:
        raw=(root/item['Name']).read_bytes()
        assert len(raw)==item['NewBytes'] and sha(raw)==item['NewSHA256'].lower()
        originals[item['Name']]=sha(raw)
    scope=json.loads((REPO/'docs/project/sources/PHASE1_SCOPE_SOURCE_20260903.json').read_bytes())['source']
    raw=(REPO/scope['archived_relative_path']).read_bytes()
    assert len(raw)==scope['size_bytes'] and sha(raw)==scope['sha256'].lower()
    originals[scope['filename']]=sha(raw)
    deployed=json.loads((deploy.EVIDENCE/'deployment-r03.json').read_bytes())
    assert deployed['source_hashes']==deploy.hashes()
    native=json.loads((deploy.EVIDENCE/'pan-native-chain-r02.json').read_bytes())
    assert native['status']=='COMPLETE_PAN_N06_N07_NATIVE_PASS'
    selection=native['result']['panel_selection']
    assert selection['completed_batches']==selection['required_batches']
    assert selection['requested_counts']==dict(mhc_i=12642,mhc_ii=11069)
    assert all(c['status']=='parsed_unreviewed' for c in native['result']['channels'].values())
    assert {k:v['observed_rows'] for k,v in native['result']['channels'].items()}==dict(mhc_i=12642*35,mhc_ii=11069)
    assert all(native[k]['state']=='succeeded' for k in ('job','n06_job','n07_job'))
    assert len({native[k]['run_id'] for k in ('job','n06_job','n07_job')})==1
    iedb=json.loads((deploy.EVIDENCE/'iedb-bepi-chain-r01.json').read_bytes())
    assert iedb['status']=='REAL_IEDB_BEPI_N06_N07_PASS'
    assert iedb['n07_result']['hotspot_assessment']['status']=='NOT_PERFORMED'
    assert iedb['n07_result']['glycosylation']['shielding_risk'] is False
    assert not iedb['n03_result']['iedb_prior']['contact_residues']
    evidence={p.name:sha(p.read_bytes()) for p in sorted(deploy.EVIDENCE.iterdir()) if p.is_file()}
    return dict(status='ITEM2_DEFINED_BRANCHES_ENGINEERING_VERIFIED',generation=deployed['generation'],
        tests=dict(passed=sum(c.find('skipped') is None for c in latest.values()),
                   skipped=sum(c.find('skipped') is not None for c in latest.values()),reports=[p.name for p in reports]),
        expert_originals=dict(count=len(originals),files=originals,aggregate_sha256=sha(encode(originals))),
        complete_pan=selection,native_rows={k:v['observed_rows'] for k,v in native['result']['channels'].items()},
        iedb_e3_count=len(iedb['n03_result']['iedb_prior']['epitope_regions']),
        unresolved_scientific_branches=['OI-026 BepiPred column/peak composition','OI-029 non-20-aa hotspot conversion',
            'Normalization when prediction score unavailable or range degenerates'],
        e4=dict(implementation='LOCAL_HASHED_PDB_HEAVY_ATOMS_4_ANGSTROM_WITH_ORIGINAL_RESIDUE_IDS',
            numerical_fixture_tested=True,real_positive_asset_validation='MISSING_LOCAL_COMPLEX_COORDINATE_PACKAGE'),
        scientific_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED',
        new_design_workflow_started=False,new_candidates_generated=False,evidence_sha256=evidence)


if __name__=='__main__':
    value=collect()
    with (deploy.EVIDENCE/'closeout-r01.json').open('xb') as stream:stream.write(encode(value))
    print(json.dumps({k:value[k] for k in ('status','generation','tests','native_rows','iedb_e3_count')},ensure_ascii=False))
