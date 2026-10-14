import importlib.util
import json
from pathlib import Path


def module():
    path = Path(__file__).parents[1] / 'scripts/audit_af3_workflow_target.py'
    spec = importlib.util.spec_from_file_location('audit_af3_workflow_target', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_audit_payload_is_read_only_and_checks_required_af3_chain_evidence():
    value = module()
    parent = 't01p1r-job-' + 'a' * 32
    payload = value.remote_payload(parent)
    compile(payload, 'af3-workflow-audit-remote', 'exec')
    assert parent in payload
    assert 'workflow.report' not in payload
    assert "len(models) == 5" in payload
    assert "official_ranking_score_used" in payload
    assert "ICODE_UNKNOWN" in payload
    assert "report_publication_called': False" in payload
    assert set(value.SUCCEEDED) | set(value.SKIPPED) == {
        'prediction', 'structure', 'topology', 'blast', 'bepipred', 'netmhc',
        'epitope_map', 'glycosylation', 'homology', 'domains', 'developability',
        'design', 'rescore', 'protection', 'stability', 'wt_draft',
        'variant_report', 'codon', 'wt_reference', 'local_delivery',
    }
