"""Derive engineering inputs using existing S-27 rules and this run's facts.
Missing evidence stays restricted/unknown; failed exports never invent sites.
"""
from ...common import ensure, encode, sha
MODE = 'BACKEND_EVIDENCE_V1'


def enabled(body):
    return body.get('engineering_design') == MODE


def effective(rt, body, rows):
    if not enabled(body):return body, None
    row = rows.get('design_inputs') or {}
    if row.get('state') != 'succeeded':
        return body, row.get('reason_code') or 'DESIGN_EVIDENCE_NOT_AVAILABLE'
    audit = rt.result(row['job_id'])['audit']
    draft = audit.get('n11_request_draft')
    if draft is None and audit.get('confirmation_required'):
        pending=audit['pending_n11_request_draft']
        consent=(rows.get('design') or {}).get('confirmation')
        if consent is None:return body, 'T4_EMPTY_FIXED_CONFIRMATION_REQUIRED'
        ensure(consent['audit_job_id']==row['job_id'] and consent['draft_sha256']==sha(encode(pending)),
               'FORBIDDEN','T4 confirmation belongs to a different audit')
        if consent['decision'] is not True:return body, 'T4_DESIGN_DECLINED'
        draft=dict(pending,t4_empty_fixed_confirmation=True)
    if draft is None:return body, 'N11_MASK_EXPORT_BLOCKED' 
    ensure(draft['protein_sequence'] == body['protein_sequence'],
           'OUTPUT_INVALID', 'Audited design input sequence differs')
    from ..proteinmpnn.policy import design_options
    opts = {k: draft[k] for k in ('constraints', 'n_designs', 'sampling_temperature', 'seed', 'timeout_seconds')}
    if 't4_empty_fixed_confirmation' in draft:
        opts['t4_empty_fixed_confirmation']=draft['t4_empty_fixed_confirmation']
    design_options(opts, body['protein_sequence'])
    return dict(body, m1_test=opts), None


def request(rt, body, rows):
    from .service import m1_design_reason, source
    from ..design_backend.policy import PRODUCERS
    reason = m1_design_reason(rt, rows)
    if reason=='M1_DESIGN_DOMAIN_NOT_SUPPORTED':
        from .service import design_applicability
        gate=design_applicability(rt,rows)
        if gate and gate['status']=='SUITABLE_FOR_DESIGN' and rows.get('structure',{}).get('state')=='succeeded':
            reason=None
    if reason:return None, reason
    return dict(protein_sequence=body['protein_sequence'], user_sequence_id=body['user_sequence_id'],
                timeout_seconds=60, upstream={n: source(rt, rows.get(n)) for n in PRODUCERS},
                user_regions=[], objective='general', epitope_policy='PRESERVE', epitope_mode='both',
                membrane_design_confirm=body.get('design_context',{}).get('membrane_design_confirm',False),
                sample_numbers=[], t4_handshake=True), None
