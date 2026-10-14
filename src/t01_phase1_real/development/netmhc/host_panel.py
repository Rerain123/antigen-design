"""Versioned, explicitly provisional host panel; replace asset after Spec annex delivery."""
from ...common import decode, encode, ensure, sha
from ...files import no_links, read_locked
from . import policy

MODE='registered_host_panel'
NODE_TIMEOUT_SECONDS=900  # Engineering budget, not a scientific threshold.


def document():
    value=decode(read_locked(no_links(policy.HERE/'host-panel.json'),65536))
    ensure(value.get('schema_version')==1 and value.get('qualification')=='USER_AUTHORIZED_PROVISIONAL'
           and value.get('project_spec_annex_provided') is False,
           'PROFILE_NOT_APPROVED','Host panel qualification requires explicit review')
    ensure(value.get('host_aliases') and value.get('panel_id'),'OUTPUT_INVALID','Host panel identity absent')
    return value


def supports(host):
    return host.casefold() in document()['host_aliases']


def manifest(host):
    from .pan import manifest as package_manifest
    doc=document()
    ensure(host.casefold() in doc['host_aliases'],'INVALID_REQUEST','Host differs from registered panel')
    package=package_manifest();channels={}
    ensure(doc['source_inventory_sha256']==package['channels']['mhc_i']['inventory_sha256'],
           'HASH_MISMATCH','Host panel source inventory changed')
    for kind in ('mhc_i','mhc_ii'):
        names=doc[kind+'_alleles'];available=package['channels'][kind]
        ensure(isinstance(names,list) and len(names)==len(set(names)) and set(names)<=set(available['alleles']),
               'HASH_MISMATCH','Host panel contains unsupported or duplicate alleles')
        ensure(names or doc['unavailable_reasons'].get(kind),'OUTPUT_INVALID','Missing channel requires a reason')
        channels[kind]=dict(available,alleles=names,count=len(names),unavailable_reason=doc['unavailable_reasons'].get(kind))
    ensure(any(c['count'] for c in channels.values()),'ASSET_MISSING','No executable host channel')
    value=dict(mode=MODE,source='USER_AUTHORIZED_PROVISIONAL_HOST_PANEL',channels=channels,
               panel_document=doc,package_support_sha256=package['package_support_sha256'])
    return dict(value,sha256=sha(encode(value)))


def options(host):
    if supports(host):
        return dict(panel_mode=MODE,panel_manifest_sha256=manifest(host)['sha256'],timeout_seconds=NODE_TIMEOUT_SECONDS)
    from .pan import options as pan_options
    return pan_options(timeout_seconds=NODE_TIMEOUT_SECONDS)


def readiness(host):
    """Read-only host-channel gap inventory; does not alter the panel identity.

    A receptor sequence catalogue alone does not provide a ranked MHC-II panel.
    No heterologous allele or unranked Score_EL is silently substituted.
    """
    panel = manifest(host)
    from .pan import manifest as package_manifest
    from ..expert_feedback import authority
    supported=package_manifest()
    channels = {}
    for kind, item in panel['channels'].items():
        available = bool(item['count'])
        channels[kind] = dict(status='REGISTERED_PROVISIONAL' if available else 'UNAVAILABLE',
            assessment_status='PREDICTED_UNREVIEWED' if available else 'NOT_ASSESSED',
            package_sla_supported_count=sum(n.upper().startswith('SLA') for n in supported['channels'][kind]['alleles']),
            allele_count=item['count'], tool_version=item['version'],
            inventory_sha256=item['inventory_sha256'], reason_code=item['unavailable_reason'],
            missing_requirements=[] if available else [
                'VERSIONED_SLA_DR_DQ_PANEL_WITH_ALPHA_BETA_PAIRING',
                'LOCAL_MODEL_AND_PERCENT_RANK_SUPPORT_FOR_EACH_PAIR',
                'NATIVE_OUTPUT_MAPPING_AND_REFERENCE_VALIDATION'],
            scientific_consumption=False)
    return dict(panel_id=panel['panel_document']['panel_id'], panel_manifest_sha256=panel['sha256'],
                expert_authority=authority(),breed_coverage='NOT_ASSESSED',
                pig_mhc_ii_degraded=False if not panel['channels']['mhc_ii']['count'] else None,
                degradation_factor_applied=False,
                channels=channels, reference_catalogue_used_for_prediction=False,
                substitution_applied=False, model_invoked=False)
