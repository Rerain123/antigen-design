"""Explain existing S16/S27 masks without resolving their scientific ambiguity.

This is an observation of a verified audit, never an alternative permission set.
It also works on archived audits without changing their bytes or fingerprints.
"""


def describe(permissions, domains):
    mature_paths = {f'analysis.functional_domains[{i}]' for i, row in enumerate(domains)
                    if row.get('type') == 'mature_chain'}
    mature = []; sole = []; independent = []; overridden = []
    for row in permissions.get('per_residue') or []:
        hard = [e for e in row.get('evidence_source', []) if e.get('constraint_state') == 'HARD']
        chain = [e for e in hard if e.get('source') == 'domains' and e.get('source_path') in mature_paths]
        if not chain:
            continue
        position = row['position']
        if row.get('design_permission') != 'FIXED':
            overridden.append(position)
            continue
        mature.append(position)
        user_fixed = any(r.get('permission') == 'FIXED' for r in row.get('user_sources') or [])
        (independent if len(hard) > len(chain) or user_fixed else sole).append(position)
    total = len(permissions.get('per_residue') or [])
    return dict(status='EXPERT_CLARIFICATION_REQUIRED' if mature else 'NO_MATURE_CHAIN_FIXED_EVIDENCE',
                source_sections=['SOP v10.5 S-16', 'SOP v10.5 S-27', 'expert v2 20260929 §3/§15'],
                sequence_length=total,
                all_positions_fixed=bool(total) and len(permissions.get('fixed_positions') or []) == total,
                mature_chain_fixed_positions=mature, fixed_only_by_mature_chain=sole,
                also_fixed_by_independent_evidence=independent,
                explicit_override_positions=overridden,
                permissions_changed=False, alternative_permissions=None,
                qualification='DIAGNOSTIC_ONLY_NOT_PERMISSION_TO_MUTATE')
