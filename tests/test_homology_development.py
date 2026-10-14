"""N08 reference mathematics, source isolation, request and artifact guards."""
import math
import sys
from pathlib import Path

import pytest

from t01_phase1_real.common import RuntimeFault, encode
from t01_phase1_real.development import Runtime, docker
from t01_phase1_real.development.homology import compute as c, policy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_homology_acceptance import make_database


def test_gap_excluded_entropy_and_query_mapping():
    msa={c.ANCHOR:'AC-D', 'one':'AC-D', 'two':'AD-D', 'three':'A--D'}
    result=c.conservation(msa,['one','two','three'],'ACD')
    assert result['entropy']==[0,1,None,0]
    assert result['score_per_residue']==[1,1-1/math.log2(20),1]
    assert result['unreliable_positions']==[3]
    assert result['msa_column_to_query_position']==[1,2,None,3]
    assert result['query_position_to_msa_column']==[1,2,4]
    assert result['query_anchor_counted'] is False


def test_uniform_twenty_amino_acids_has_zero_conservation():
    msa={c.ANCHOR:'A',**{aa:aa for aa in sorted(c.AA)}}
    value=c.conservation(msa,sorted(c.AA),'A')
    assert value['entropy'][0]==pytest.approx(math.log2(20))
    assert value['score'][0]==pytest.approx(0,abs=1e-12)
    assert value['class']==['variable']


@pytest.mark.parametrize('scores,quality,length', [([1.]*15,'standard',15),([.8]*10,'relaxed',10),([.6]*8,'minimal',8),([.4]*20,'failed',0)])
def test_region_tiers_independent_reference(scores,quality,length):
    result=c.regions(dict(score_per_residue=scores,unreliable_query_positions=[]))
    assert result['quality_flag']==quality
    assert result['fixed_positions']==list(range(1,length+1))
    assert result['relaxation_history']


def test_bridge_ambiguity_cannot_generate_fixed_constraints():
    result=c.regions(dict(score_per_residue=[1.]*6+[.2]+[1.]*7,unreliable_query_positions=[]))
    assert result['regions'] is None and result['fixed_positions'] is None
    assert 'SHORT_FRAGMENT_BRIDGE_ORDER_UNRESOLVED' in result['review_reasons']


def test_unreliable_and_all_gap_never_become_empty_success():
    msa={c.ANCHOR:'ACD','a':'A-D','b':'A-D'}
    value=c.conservation(msa,['a','b'],'ACD')
    assert value['score_per_residue']==[1,None,1]
    assert value['unreliable_query_positions']==[2]
    assert c.regions(value)['status']=='review_required'
    assert c.regions(value,query_range=[1,3])['statistics'] is None


def test_range_statistics_no_global_scan():
    result=c.regions(dict(score_per_residue=[.1,.8,1.,.2],unreliable_query_positions=[]),query_range=[2,3])
    assert result['statistics']==dict(mean=.9,min=.8,max=1.,**{'class':None})
    assert result['review_reasons']==['QUERY_RANGE_CLASS_AGGREGATION_UNRESOLVED']
    assert result['regions'] is None and result['relaxation_history']==[]


@pytest.mark.parametrize('raw', ['>a\nACD\n>a\nACD\n','ACD\n','>a\nAXD\n','>a\n\n'])
def test_fasta_integrity_rejects(raw):
    with pytest.raises(ValueError):c.fasta(raw)


def test_database_identity_and_late_tamper(tmp_path):
    body,folder=make_database(tmp_path)
    receipt=policy.verify_database(tmp_path,body)
    assert receipt['qualification']=='ENGINEERING_FIXTURE'
    with (folder/'annotations.json').open('ab') as stream:stream.write(b' ')
    with pytest.raises(RuntimeFault,match='bytes changed'):policy.verify_database(tmp_path,body)


@pytest.mark.parametrize('change',[dict(database_id='../escape'),dict(database_manifest_sha256='x'*64),
    dict(protein_sequence='ACDX'),dict(timeout_seconds=True),dict(query_range=[0,4]),dict(query_range=[2,1]),
    dict(sequence_weighting='henikoff'),dict(source_filter='all'),dict(command='arbitrary')])
def test_exact_request_rejects_unapproved_inputs(tmp_path,change):
    body,_=make_database(tmp_path)
    with pytest.raises(RuntimeFault):policy.request(encode(dict(body,**change)))


def test_unknown_subtypes_do_not_manufacture_confidence(tmp_path):
    body,folder=make_database(tmp_path,missing=True)
    import json
    records=json.loads((folder/'annotations.json').read_text())[:24]
    groups=c.annotation_groups(records,'subtype')
    value=c.confidence(records,groups,dict(unreliable_positions=[],score=[1]*120),'subtype','ENGINEERING_FIXTURE')
    assert value['lineage_coverage']==1 and value['conservation_confidence']=='LOW'
    assert groups['subtype_parse_stats']['missing_rate']==1


def test_exact_incremental_registration_idempotency_and_cancel(tmp_path):
    body,_=make_database(tmp_path/'data')
    runtime=Runtime(tmp_path/'run',homology_database_root=tmp_path/'data')
    job=runtime.submit_sequence(encode(body),'n08',policy.TOOL)
    assert job['node_id']=='N08' and job['rule_profile']==policy.registered_rules()
    assert runtime.submit_sequence(encode(body),'n08',policy.TOOL)['job_id']==job['job_id']
    with pytest.raises(RuntimeFault):runtime.submit_sequence(encode(dict(body,user_sequence_id='different')),'n08',policy.TOOL)
    final=runtime.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=job['job_id'],idempotency_key='cancel')))
    assert final['state']=='cancelled' and final['usable_for_pipeline'] is False


def test_native_command_is_offline_and_separate_slot(tmp_path):
    body,_=make_database(tmp_path/'data')
    runtime=Runtime(tmp_path/'run')
    job=runtime.submit_sequence(encode(body),'n08',policy.TOOL)
    for key in ('attempt_id','execution_identity'):job[key]='t01p1r-test'
    argv=docker.command(runtime.root,job,'attempt-test',120,str(tmp_path/'data'/'engineering-n08'))
    assert '--network' in argv and argv[argv.index('--network')+1]=='none'
    assert policy.SLOT in argv and policy.IMAGE in argv and '--read-only' in argv
    assert '/tmp:rw,exec,nosuid,size=2g' in argv  # native MMseqs workflow scripts require exec
    assert docker.labels(runtime.root,job)['t01.worker']=='homology-development'
