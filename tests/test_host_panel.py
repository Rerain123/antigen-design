"""Temporary host panel coverage, absent-channel truthfulness and lifecycle safety."""
import copy
import json
from pathlib import Path
import pytest

from t01_phase1_real.common import RuntimeFault, encode, sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.netmhc import host_panel, pan, policy, service
from test_phase1_item2 import SEQ, channel, finish_fixture


def test_full_supported_sla_list_is_four_lossless_batches_and_version_bound():
    p=host_panel.manifest('猪');parts=pan.batches('A'*233,p)
    names=[a for part in parts for a in part['mhc_i_alleles']]
    supported=[a for a in pan.manifest()['channels']['mhc_i']['alleles'] if a.startswith('SLA-')]
    assert names==supported and len(names)==76 and len(parts)==4
    assert all(not part['mhc_ii_alleles'] for part in parts)
    assert p['panel_document']['project_spec_annex_provided'] is False
    assert host_panel.options('pig')==host_panel.options('Sus scrofa')==host_panel.options('猪')
    assert host_panel.options('human')['panel_mode']==pan.MODE
    assert host_panel.options('猪')['timeout_seconds']==900


@pytest.mark.parametrize('change', ['host','digest','foreign_allele','absent_context','empty_both'])
def test_host_child_cannot_invent_or_substitute_missing_channel(change):
    p=host_panel.manifest('猪');part=pan.batches(SEQ,p)[0]
    b=dict(protein_sequence=SEQ,host_species='猪',user_sequence_id='test',timeout_seconds=900,
           mhc_i_alleles=part['mhc_i_alleles'],mhc_ii_alleles=[],host_panel_sha256=p['sha256'])
    assert policy.request(encode(b))==b
    if change=='host':b['host_species']='human'
    if change=='digest':b['host_panel_sha256']='0'*64
    if change=='foreign_allele':b['mhc_ii_alleles']=['HLA-DPA10202-DPB11901']
    if change=='absent_context':b.pop('host_panel_sha256')
    if change=='empty_both':b['mhc_i_alleles']=[]
    with pytest.raises(RuntimeFault):policy.request(encode(b))


def test_host_aggregate_absent_ii_is_unavailable_not_zero_hits():
    p=host_panel.manifest('猪');rows=[]
    for part in pan.batches(SEQ,p):
        req=dict(protein_sequence=SEQ,**{k+'_alleles':part[k+'_alleles'] for k in p['channels']})
        result=dict(binding=dict(sequence_sha256=sha(SEQ.encode())),panel_selection=dict(mode='explicit_alleles'),
            channels={k:channel(SEQ,k,req[k+'_alleles']) for k in p['channels']})
        rows.append((req,result,dict(job_id=str(part['index']))))
    channels,refs=pan.aggregate(SEQ,p,rows)
    assert len(refs)==4 and channels['mhc_i']['status']=='parsed_unreviewed'
    assert channels['mhc_ii']['status']=='unavailable' and channels['mhc_ii']['residue_summary'] is None
    assert channels['mhc_ii']['hits'] is channels['mhc_ii']['observed_rows'] is None
    assert channels['mhc_ii']['assessment_status']=='NOT_ASSESSED'


def test_host_controller_provenance_four_batches_resume_and_no_hidden_ii(tmp_path,monkeypatch):
    rt=Runtime(tmp_path/'rt');original=rt.dispatch
    monkeypatch.setattr(rt,'dispatch',lambda jid:original(jid) if service.selected(rt,rt.get(jid)) else rt.get(jid))
    b=dict(protein_sequence=SEQ,host_species='猪',user_sequence_id='test',**host_panel.options('猪'))
    parent=rt.submit_sequence(encode(b),'host-panel',policy.TOOL);jid=parent['job_id']
    for count in range(4):
        rt.dispatch(jid);ids=list(rt.execution(jid)['batches']);assert len(ids)==count+1
        rt.recover(jid);assert rt.execution(jid)['batches']==ids
        req=json.loads(rt._request_bytes(rt.get(ids[-1])))
        assert req['mhc_ii_alleles']==[] and req['host_panel_sha256']==b['panel_manifest_sha256']
        finish_fixture(rt,ids[-1])
    rt.recover(jid);result=rt.result(jid)
    assert rt.get(jid)['state']=='succeeded' and result['status']=='partial_unreliable'
    assert result['scope']=='N05_NETMHC_HOST_PANEL'
    assert result['panel_selection']['completed_batches']==4
    assert result['panel_selection']['mhc_tier'] is None and result['panel_selection']['provisional']
    assert not result['panel_selection']['pan_allele_warning']
    assert result['panel_selection']['pig_mhc_ii_degraded'] is False
    assert result['panel_selection']['pig_mhc_ii_assessment']=='NOT_ASSESSED'
    assert not result['panel_selection']['degradation_factor_applied']
    assert result['panel_selection']['breed_coverage']=='NOT_ASSESSED'
    assert any(w['code']=='PROVISIONAL_HOST_PANEL' for w in result['warnings'])
    service.verify_sources(rt,rt.get(jid),result)


def test_low_remaining_time_skips_n05_but_finishes_delivery(tmp_path,monkeypatch):
    from test_local_workflow import body,run
    from t01_phase1_real.development.workflow import confirmation
    b=body();b['host_species']='猪';b['analysis']['netmhc']=host_panel.options('猪')
    monkeypatch.setattr(confirmation,'elapsed',lambda _:275)
    rt=Runtime(tmp_path/'rt');final=run(rt,b)
    assert final['state']=='succeeded'
    nodes=rt.workflow(final['job_id'])['nodes']
    assert nodes['netmhc']['reason_code']=='N05_DOWNSTREAM_TIME_RESERVE'
    assert nodes['netmhc']['job_id'] is None and nodes['local_delivery']['state']=='succeeded'


def test_downloaded_official_snapshot_sla_index_hashes():
    root=Path(__file__).resolve().parents[1]/'var/t01-phase1-real/host-panels/ipdmhc-20260726'
    receipt=json.loads((root/'sla-index.json').read_bytes())
    assert receipt['commit']==host_panel.document()['ipdmhc_reference']['commit']
    assert len(receipt['sla_records']['MHC_prot.fasta'])==523
    for row in receipt['files']:
        raw=(root/row['name']).read_bytes()
        assert len(raw)==row['bytes'] and sha(raw)==row['sha256']


@pytest.mark.parametrize('change',['none','timeout','panel','sequence','run'])
def test_wt_reuse_requires_identical_science_inputs_and_same_run(monkeypatch,change):
    from types import SimpleNamespace
    from t01_phase1_real.development.workflow import service as workflow
    b=dict(protein_sequence=SEQ,host_species='猪',user_sequence_id='test',**host_panel.options('猪'))
    req=copy.deepcopy(b)
    if change=='timeout':req['timeout_seconds']=50
    if change=='panel':req['panel_manifest_sha256']='a'*64
    if change=='sequence':req['protein_sequence']='A'*20
    job=dict(job_id='n05',run_id='foreign' if change=='run' else 'run')
    # verified() handles artifact integrity; this isolates the additional reuse fences.
    monkeypatch.setattr(workflow,'verified',lambda *args:job)
    rt=SimpleNamespace(_request_bytes=lambda _:encode(b))
    args=(rt,{},dict(netmhc=dict(state='succeeded',job_id='n05')),'run',req)
    if change=='run':
        with pytest.raises(RuntimeFault):workflow.reusable_wt_netmhc(*args)
    else:
        assert workflow.reusable_wt_netmhc(*args)==('n05' if change in ('none','timeout') else None)


def test_report_exposes_provisional_panel_and_missing_ii():
    from t01_phase1_real.service_api.user_report import render
    d=dict(wt_draft=dict(assessments=dict(netmhc=dict(observations=dict(panel_selection=dict(
        provisional=True,panel_id='pig-tool-supported-v1',unavailable_reasons=dict(mhc_ii='NO_VALIDATED_PANEL')))))))
    html=render(d).decode()
    assert '临时宿主等位基因面板' in html and 'MHC-II 未评估' in html and '尚未验证猪群覆盖' in html


def test_deploy_updates_worker_and_service_together_without_resource_changes():
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
    import prepare_host_panel_deploy as deploy
    from test_n13_deployment import live
    before=live();before['spec']['template']['spec']['containers'].append(dict(name='worker-netmhc',
        volumeMounts=[dict(name='runtime',mountPath='/var/lib/t01')],resources={'limits':{'cpu':'2'}}))
    original=copy.deepcopy(before);cm,patch,rollback=deploy.render(before)
    assert before==original and cm['immutable'] and len(cm['binaryData'])==len(deploy.FILES)
    replacements=[op for op in patch if op['op']=='replace']
    assert len(replacements)==2 and replacements[-1]['value'][-1]['mountPath'].endswith('/netmhc/worker.py')
    assert all('resources' not in op['path'] for op in patch) and len(rollback)==4
