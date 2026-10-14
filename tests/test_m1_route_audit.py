"""Historical P4 evidence remains engineering evidence, never a strict route pass."""
import sys
import pytest
from t01_phase1_real.common import REPO

sys.path.insert(0,str(REPO/'scripts'))
from audit_m1_route import check_node_labels, route_checks


def test_stage_labels_keep_subtool_receipt_identity():
    rows={name:{'node_id':stage} for name,stage in (
        ('rep1_prediction','N12'),('rep1_bepipred','N13'),
        ('wt_foldx','N17'),('variant_report','N15'))}
    records={name:{'job':{'node_id':tool}} for name,tool in (
        ('rep1_prediction','N01'),('rep1_bepipred','N04'),
        ('wt_foldx','N14'),('variant_report','N15'))}
    check_node_labels(rows, records)
    rows['wt_foldx']['node_id']='N16'
    with pytest.raises(AssertionError):
        check_node_labels(rows, records)


def test_old_target_design_cannot_pass_corrected_route_audit():
    with pytest.raises(AssertionError):
        route_checks(REPO/'discovery/t01-phase1-real/m1-p4-20260922/r16')
