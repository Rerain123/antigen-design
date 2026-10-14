"""Independent numerical evidence and scientific-boundary regression checks, no Docker needed."""
import copy
import importlib.util
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
BATCH=ROOT/'discovery/t01-phase1-real/w1/freesasa-reference-20260905'


def verifier():
    spec=importlib.util.spec_from_file_location('w1_numerical_reference',BATCH/'verify_reference.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_independent_reference_is_intact_but_not_a_scientific_release():
    result=verifier().verify()
    assert result['numeric_delta_checks']=='PASS'
    assert result['accepted_project_rsa'] is False
    assert result['out_of_domain'][0]['selected_raw_ratio']>1.4
    assert result['production_status']=='NOT_DEPLOYED'


def substitute(module,monkeypatch,filename,mutate):
    original=module.read
    def replacement(path):
        value=original(path)
        if path.name==filename:
            value=copy.deepcopy(value); mutate(value)
        return value
    monkeypatch.setattr(module,'read',replacement)


def test_saved_comparison_cannot_be_replaced_with_pass_numbers(monkeypatch):
    module=verifier()
    substitute(module,monkeypatch,'comparison.json',lambda d:d['comparisons'][0].update(max_abs_rsa_delta=0.0))
    with pytest.raises(ValueError,match='Saved comparison differs'):
        module.assess()


def test_numerical_success_cannot_grant_scientific_approval(monkeypatch):
    module=verifier()
    substitute(module,monkeypatch,'PHASE1_REAL_W1_FREESASA_PROFILE.json',lambda d:d.update(production_approved=True))
    with pytest.raises(ValueError,match='Cannot infer scientific approval'):
        module.assess()


def test_uncovered_s09_branch_cannot_gain_a_fabricated_quality(monkeypatch):
    module=verifier()
    def change(data):
        next(d for d in data['decisions'] if d['case_id']=='S09-D03a')['proposed_expected']['quality_result']={'confidence':'low'}
    substitute(module,monkeypatch,'PHASE1_REAL_W1_S09_DECISION_PROPOSAL.json',change)
    with pytest.raises(ValueError,match='Uncovered branch gained invented confidence'):
        module.assess()


def test_parameter_budget_cannot_be_relaxed_after_observing_results(monkeypatch):
    module=verifier()
    substitute(module,monkeypatch,'PHASE1_REAL_W1_FREESASA_PROFILE.json',lambda d:d['numerical_acceptance_proposal'].update(per_residue_absolute_rsa_error_max=.1))
    with pytest.raises(ValueError,match='Predeclared target changed'):
        module.assess()


def test_out_of_domain_reference_cannot_be_silently_clamped(monkeypatch):
    module=verifier()
    def change(data):
        data['residues'][-1]['absolute_sasa_a2']=104.0
    substitute(module,monkeypatch,'Biopython-SR-61440.json',change)
    with pytest.raises(ValueError,match='Residue sum mismatch'):
        module.assess()
