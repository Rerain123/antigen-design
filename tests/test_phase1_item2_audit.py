"""Completion must reject partial grids, cross-run evidence and stale deployments."""
import json
import sys
import xml.etree.ElementTree as ET

import pytest

from t01_phase1_real.common import REPO

sys.path.insert(0,str(REPO/'scripts'))
import audit_phase1_item2 as audit


@pytest.fixture
def bundle(tmp_path,monkeypatch):
    monkeypatch.setattr(audit.deploy,'EVIDENCE',tmp_path)
    monkeypatch.setattr(audit.deploy,'hashes',lambda:dict(module='current'))
    suite=ET.Element('testsuite')
    for i in range(2401):ET.SubElement(suite,'testcase',classname='recorded',name=str(i))
    ET.ElementTree(suite).write(tmp_path/'full.junit.xml')
    def write(name,value):(tmp_path/name).write_text(json.dumps(value),encoding='utf8')
    write('deployment-r03.json',dict(generation=90,source_hashes=dict(module='current')))
    native=dict(status='COMPLETE_PAN_N06_N07_NATIVE_PASS',
        result=dict(panel_selection=dict(completed_batches=738,required_batches=738,
            requested_counts=dict(mhc_i=12642,mhc_ii=11069)),
            channels={k:dict(status='parsed_unreviewed',observed_rows=count) for k,count in [('mhc_i',12642*35),('mhc_ii',11069)]}),
        **{k:dict(state='succeeded',run_id='same-run') for k in ('job','n06_job','n07_job')})
    write('pan-native-chain-r02.json',native)
    write('iedb-bepi-chain-r01.json',dict(status='REAL_IEDB_BEPI_N06_N07_PASS',
        n07_result=dict(hotspot_assessment=dict(status='NOT_PERFORMED'),glycosylation=dict(shielding_risk=False)),
        n03_result=dict(iedb_prior=dict(contact_residues=[],epitope_regions=[dict(source_iedb_id='test-fixture')]))))
    return tmp_path,native,write


def test_complete_evidence_remains_engineering_and_lists_missing_scientific_branches(bundle):
    result=audit.collect()
    assert result['tests']['passed']==2401
    assert result['expert_originals']['count']==22
    assert result['scientific_gate']=='CLOSED' and result['usable_for_pipeline'] is False
    assert result['unresolved_scientific_branches'] and result['e4']['real_positive_asset_validation'].startswith('MISSING_')


@pytest.mark.parametrize('damage',['partial_grid','missing_batch','cross_run','stale_code','failed_test'])
def test_completion_rejects_incomplete_or_misbound_evidence(bundle,damage):
    directory,native,write=bundle
    if damage=='partial_grid':native['result']['channels']['mhc_i']['observed_rows']-=1
    elif damage=='missing_batch':native['result']['panel_selection']['completed_batches']-=1
    elif damage=='cross_run':native['n06_job']['run_id']='another-run'
    elif damage=='stale_code':write('deployment-r03.json',dict(generation=90,source_hashes=dict(module='old')))
    else:
        path=directory/'full.junit.xml';tree=ET.parse(path);ET.SubElement(next(tree.getroot().iter('testcase')),'failure');tree.write(path)
    write('pan-native-chain-r02.json',native)
    with pytest.raises(AssertionError):audit.collect()
