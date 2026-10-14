import io
import pytest
from Bio.PDB.MMCIF2Dict import MMCIF2Dict
from t01_phase1_real.common import REPO, RuntimeFault, sha
from t01_phase1_real.development.esmfold2.standard import tool_structure
from t01_phase1_real.development.esmfold2.quality import assess

RAW=(REPO/'discovery/t01-phase1-real/esmfold2-target-20260917/r03/structure.cif').read_bytes()


def test_derivative_preserves_every_original_field_and_tracks_hashes():
    derived,record=tool_structure(RAW)
    original=MMCIF2Dict(io.StringIO(RAW.decode()))
    parsed=MMCIF2Dict(io.StringIO(derived.decode()))
    assert parsed.pop('_atom_site.occupancy')==['1.0']*601
    assert parsed==original
    assert record['original_sha256']==sha(RAW) and record['derived_sha256']==sha(derived)
    with pytest.raises(RuntimeFault,match='existing occupancy'): tool_structure(derived)


def test_quality_boundaries_and_mask_dual_write():
    assert assess([0.7]*9,0.5)['quality']['confidence']=='high'
    assert assess([0.5]*9,None)['quality']['confidence']=='medium'
    scores=[0.4]*5+[0.8]*3+[0.4]*5+[0.8]*4+[0.4]*4
    q=assess(scores,0.49)
    assert q['quality']['low_confidence_regions']==[dict(start=1,end=13)]
    assert q['structure']['low_confidence_regions']==q['quality']['low_confidence_regions']
    assert not q['quality']['topology_reliable'] and not q['usable_for_pipeline']
