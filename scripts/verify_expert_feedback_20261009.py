"""Offline adoption evidence; never submits or resumes a scientific workflow."""
import copy
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from t01_phase1_real.common import decode,encode,ensure,sha
from t01_phase1_real.development.expert_feedback import authority,ROOT as EXPERT
from t01_phase1_real.development.design_backend import permissions,policy as design_policy
from t01_phase1_real.development.bepipred.postprocessing import project
from t01_phase1_real.development.developability import camsol
from t01_phase1_real.development.epitope_map.result import compute,prediction_type_join,literature_prediction_norm
from t01_phase1_real.development.epitope_map.composition import synthesize
from t01_phase1_real.development.netmhc.host_panel import readiness
from t01_phase1_real.service_api.native_report import build,peak_table
from t01_phase1_real.service_api.user_report import CSS,table,esc,number
from t01_phase1_mock.dify.campaign import verify_freeze_manifest
import version_bundle

OUTPUT=ROOT/'reports/expert-feedback-20261009'


def main():
    receipt=authority();source=ROOT/'reports/himat-report-review-20261009/backend-evidence.json'
    original=source.read_bytes();data=decode(original);original_sha=sha(original)
    expert_receipt=decode((EXPERT/'receipt.json').read_bytes())
    ensure(sha((OUTPUT/'original-camsol-package.zip').read_bytes())==expert_receipt['source_zip_sha256'],
           'HASH_MISMATCH','Original CamSol zip changed')
    sequence=data['request']['protein_sequence'];draft=data['results']['wt_draft']['draft']
    values={k:v['observations'] for k,v in draft['assessments'].items() if v and v.get('observations')}
    body=dict(protein_sequence=sequence,user_sequence_id='offline-expert-boundary-verification',
        upstream={n:None for n in design_policy.PRODUCERS},user_regions=[],objective='general',
        epitope_policy='PRESERVE',epitope_mode='both',membrane_design_confirm=False,sample_numbers=[],timeout_seconds=30)
    inputs={n:dict(state='available' if n in values else 'missing',artifact=None) for n in design_policy.PRODUCERS}
    current=permissions.assemble(body,values,inputs,decode((design_policy.HERE/'scales.json').read_bytes()))
    old=data['results']['design_inputs']['audit']['permissions']
    ensure(len(old['fixed_positions'])==233 and current['fixed_positions']==list(range(1,48)),
           'OUTPUT_INVALID','Archived/current boundary check differs')
    processed=project(values['bepipred']['raw_scores'])
    # The audit contains raw rows and N06 literature projections, not all N04/
    # BLAST native bytes. Exercise the arithmetic without forging an admitted
    # artifact chain or claiming a new registered producer result.
    prediction=dict(tool_id='t01.real.bepipred',status='raw_scores_unreviewed',
        binding=dict(sequence_sha256=sha(sequence.encode())),raw_scores=values['bepipred']['raw_scores'],postprocessing=processed)
    map_body=dict(protein_sequence=sequence,blast_input=dict(state='not_executed',artifact=None,
        reason_code='OFFLINE_ARITHMETIC_ONLY_NO_NATIVE_SOURCE_REPLAY'))
    mapped=compute(map_body,dict(bepipred=prediction,netmhc=data['results']['netmhc']))
    old_maps=data['results']['epitope_map']['epitopes'];bmap=mapped['epitopes']['b_cell_epitope_map']
    tmap=mapped['epitopes']['t_cell_presentation_map']
    prior=data['results']['epitope_map']['blast_similarity']['iedb_evidence']
    if prior:
        prediction_type_join(bmap,prior)
        for region in copy.deepcopy((old_maps['b_cell_epitope_map'] or {}).get('regions') or []):
            bmap['regions'].append(dict(region,**literature_prediction_norm(bmap,region,None)))
        tmap['evidence_regions']+=copy.deepcopy([r for r in (old_maps['t_cell_presentation_map'] or {}).get('evidence_regions',[])
                                               if r['epitope_level'] in ('E3-region','E4-contact')])
    composition=synthesize(len(sequence),bmap,tmap)
    # Formula-only offline comparison, not a new registered tool/workflow result.
    params,identity=camsol.registered_parameters();sol=camsol.assess(sequence)
    panel=readiness('猪');calibration=decode((camsol.CURRENT_ASSETS/'calibration.json').read_bytes())
    archive,manifest=version_bundle.build(ROOT/'src')
    package_prefix='t01_phase1_real/development/'
    ensure(all(package_prefix+p in manifest for p in (
        'expert_feedback.py','assets/expert-feedback-20261009/handoff.md',
        'developability/camsol_kernel.py','developability/assets/camsol-20261009-v1/camsol_params.json',
        'developability/assets/camsol-20261009-v1/calibration.json')), 'OUTPUT_INVALID','New rule assets missing from source bundle')
    ensure(source.read_bytes()==original,'HASH_MISMATCH','Original run evidence changed')
    value=dict(status='LOCAL_IMPLEMENTED_NOT_DEPLOYED',authority=receipt,
        archived_job=data['job']['job_id'],archived_evidence_sha256=original_sha,archived_evidence_unchanged=True,
        permissions=dict(original_fixed_count=233,current_fixed_count=47,current_restricted_count=len(current['restricted_positions']),
            current_open_count=len(current['open_positions']),current=current,
            qualification='OFFLINE_RULE_REPLAY_NOT_A_NEW_DESIGN_RUN'),
        bepipred=dict(postprocessing=processed,
            input_qualification='OFFLINE_SNAPSHOT_ARITHMETIC_NOT_REGISTERED_ARTIFACT_REPLAY',
            composition_status=composition['status'],composition_reason_codes=composition['reason_codes'],b_cell_map=bmap,
            hotspots=composition['hotspots'],density_per_residue=composition['density']),
        camsol=dict(identity=identity,normalization=params['random_normalization'],validation_status='NOT_ASSESSED',
            mode=sol['mode'],formula_only_global_score=sol['global_score'],consistency_status=sol['consistency_status'],
            validation_groups=sol['method_summary']['validation_groups'],scientific_consumption=False),
        pig_panel=panel,source_bundle=dict(file_count=len(manifest),manifest_sha256=sha(version_bundle.encode(manifest)),
            archive_sha256=sha(archive),archive_bytes=len(archive),asset_inclusion_verified=True),
        frozen_assets=verify_freeze_manifest(),deployment_performed=False,new_scientific_jobs=0,cancelled_jobs_resumed=0,
        remaining=dict(bepipred_parameter_backtest='NOT_COMPLETED',
            evidence_region_normalization='AVAILABLE_PREDICTOR_INTERVALS_COMPUTED;MISSING_OR_DEGENERATE_OPERANDS_NOT_ASSESSED',
            pig_mhc_ii='NO_BUILTIN_SLA_II_AND_NO_PROJECT_ALPHA_BETA_PAIRED_PANEL',
            camsol_reference_validation='NOT_COMPLETED',n08='UNCHANGED_WAITING_FOR_USER_EXPERT_CONCLUSION'),
        no_expert_original_modified=True,source_hashes=manifest)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/'verification.json').write_bytes(encode(value))
    node=dict(node_id='N11',state='succeeded',origin='INTERNAL_FACT',result=dict(audit=dict(permissions=current)))
    preview=build({}, {},dict(nodes={'design_inputs':node},run_id='OFFLINE_VERIFICATION',job_id='NOT_A_WORKFLOW_JOB',
        workflow_package_sha256='NOT_A_WORKFLOW_PACKAGE'))
    html='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>专家反馈落实核对</title><style>'+CSS+'</style><body><main>'
    html+='<h1>专家反馈落实核对</h1><p>本页为既有233 aa输入的离线工程核对，不是新的设计报告。原任务的233个固定位置、零候选及全部原始产物保留；此页不赋予科学消费资格。</p>'
    html+=preview['permissions']+peak_table(processed,table,esc,number)
    html+='<h3>CamSol 归一化计算</h3>'+table(['主参考位置数','均值 μ','总体标准差 σ','独立验证集','状态'],
        [[str(calibration['main']['count']),number(calibration['main']['mean'],12),number(calibration['main']['population_std'],12),'2组，各2000万位置','候选统计量；未判定科学验收通过']])
    html+='<p>已接入逐残基剖面与全序列公式计算；独立参考验证未完成，数值不纳入综合评分。</p>'
    html+='<h3>猪 MHC-II 与合成热点</h3><p>猪II面板缺失：一期未评估，命中为未知，未应用0.85折减。现有76个SLA-I作为探索性面板，品种覆盖未评估。</p>'
    html+='<p>连续预测候选区段已经生成。文献区段沿用S-19规则，以可用预测分数的序列内归一化及区间均值参与合成；缺预测或极差为零时保持未评估。此离线输入的合成状态：'+esc(composition['status'])+'。</p>'
    if composition['hotspots'] is not None:
        html+='<p>离线公式合成热点数：'+str(len(composition['hotspots']))+'。仍属工程核对，不代表实验证实。</p>'
        html+=table(['起点–终点','合成分数'],[[str(r['start'])+'–'+str(r['end']),number(r['weighted_score'],6)] for r in composition['hotspots']])
    html+='<p>本轮未部署、未提交新工作流，也未恢复已取消任务。</p></main></body></html>'
    (OUTPUT/'adoption-preview.html').write_text(html,encoding='utf8')
    print(json.dumps(dict(status=value['status'],old_fixed=233,new_fixed=47,restricted=len(current['restricted_positions']),
        threshold_regions=len(processed['linear_peaks_threshold']),top20_regions=len(processed['linear_peaks_top20']),
        composition_status=composition['status'],source_files=len(manifest),frozen=value['frozen_assets']),ensure_ascii=False))


if __name__=='__main__':main()
