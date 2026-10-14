"""PDB format adaptation is separate from N11 consent; preserve source ledger."""
import copy
import pytest
from t01_phase1_real.common import RuntimeFault,decode
from t01_phase1_real.development.proteinmpnn import mapping
from test_proteinmpnn_development import source,request


def test_foldx_format_projection_matches_confirmed_n11_and_retains_rounding(tmp_path,monkeypatch):
    src,raw,facts=source(tmp_path,'normal-cif');original=mapping.prepare
    def precise(*args,**kwargs):
        ledger=copy.deepcopy(original(*args,**kwargs))
        for atom in ledger['atoms']:atom['coordinate_tool'][0]+=0.00042
        return ledger
    monkeypatch.setattr(mapping,'prepare',precise)
    body=request();unchanged=copy.deepcopy(body)
    with pytest.raises(RuntimeFault,match='source precision'):mapping.project(body,src,raw,facts)
    foldx=mapping.project(body,src,raw,facts,pdb_format_projection=True)
    n11=mapping.project(dict(body,t4_empty_fixed_confirmation=True),src,raw,facts)
    assert foldx==n11 and body==unchanged and 't4_empty_fixed_confirmation' not in body
    audit=decode(foldx['native/conversion.json'])['coordinate_projection']
    assert audit['source_coordinates_preserved_in_original'] is True
    assert audit['rounded_atoms'] and audit['max_absolute_delta_angstrom']<=0.0005+1e-12


def test_foldx_explicit_format_route_does_not_invent_t4(monkeypatch):
    from t01_phase1_real.development.foldx import source as module
    from test_foldx_development import scan_body
    class Reached(Exception):pass
    def structure(rt,db,body,expected_run_id=None,**kwargs):
        assert kwargs=={'pdb_format_projection':True} and 't4_empty_fixed_confirmation' not in body
        assert expected_run_id=='run'
        raise Reached
    monkeypatch.setattr(module,'structure_sources',structure)
    with pytest.raises(Reached):module.sources(None,None,scan_body(),'run')


def test_n14_projection_retry_requires_exact_pre_admission_provenance(monkeypatch):
    from test_n14_capacity import checkpoint
    from t01_phase1_real.development.workflow import continuation
    rt,j,ex,_=checkpoint(monkeypatch)
    ex['nodes'].pop('stability');ex['fatal_detail']='Coordinate projection would lose source precision'
    with pytest.raises(RuntimeFault):continuation.prepare_stability(rt,'source')
