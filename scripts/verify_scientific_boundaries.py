"""Offline rule-gap evidence from the user's archived run; no task submission."""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from t01_phase1_real.common import sha
from t01_phase1_real.development.design_backend.boundary import describe
from t01_phase1_real.development.bepipred.postprocessing import inspect
from t01_phase1_real.development.netmhc.host_panel import readiness
from t01_phase1_real.development.developability.calibration import assets, MANIFEST_SHA
from t01_phase1_real.service_api.native_report import build
from t01_phase1_real.service_api.user_report import CSS
from t01_phase1_mock.dify.campaign import verify_freeze_manifest


def main():
    output = ROOT/'reports/scientific-boundaries-20261009'
    output.mkdir(parents=True, exist_ok=True)
    evidence = ROOT/'reports/himat-report-review-20261009/backend-evidence.json'
    raw = evidence.read_bytes(); data = json.loads(raw)
    results = data['results']; draft = results['wt_draft']['draft']
    permissions = results['design_inputs']['audit']['permissions']
    boundary = describe(permissions, results['domains']['analysis']['functional_domains'])
    bepipred = draft['assessments']['bepipred']['observations']
    postprocessing = inspect(bepipred['raw_scores'])
    panel = readiness('猪')
    base = ROOT/'var/t01-phase1-real/host-panels/ipdmhc-20260726'
    index = json.loads((base/'sla-index.json').read_bytes())
    for item in index['files']:
        content = (base/item['name']).read_bytes()
        assert sha(content) == item['sha256'] and len(content) == item['bytes']
    catalogue = Counter(row['header'].split()[1].split('*')[0]
                        for row in index['sla_records']['MHC_prot.fasta'])
    nodes = json.loads(json.dumps(data['nodes']))
    for name, result in results.items():
        if name in nodes:
            nodes[name]['result'] = result
    native = dict(nodes=nodes, run_id=data['job']['run_id'], job_id=data['job']['job_id'],
                  workflow_package_sha256='未在本地审计快照中保存；此页不是原始报告',
                  revision_config=data['request']['revision_config'])
    sections = build(dict(wt_draft=draft), dict(expert_revision=data['revision_state']), native)
    html = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>规则边界核对</title><style>'+CSS+'</style><body><main>'
    html += '<h1>规则边界核对</h1><p>离线重放既有任务事实，不是新运行或重新计算的正式报告。</p>'
    html += sections['permissions']+sections['appendix']+'</main></body></html>'
    (output/'boundary-preview.html').write_text(html, encoding='utf8')
    expert = ROOT/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902'
    originals = [expert/n for n in ('AgentA_SOP_v10.5_20260902.md', 'ToolSpec_A3_BepiPred_v10.5.md',
                 'ToolSpec_A1_NetMHCpan_v10.5.md', 'ToolSpec_C44_CamSol重实现_v10.5.md', 'camsol_params.json')]
    originals += [ROOT/'工作流设计/01-业务依据/计算流程修订_20260929/Agent A 一期计算规则与流程修订方案_v2_20260929.md']
    prepared = assets()
    value = dict(status='ENGINEERING_PARTIAL_SCIENTIFIC_DECISIONS_REQUIRED',
        job_id=data['job']['job_id'], source_evidence_sha256=sha(raw), source_evidence_unchanged=evidence.read_bytes()==raw,
        source_hashes={p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in originals},
        mature_chain=boundary, bepipred_defined_operations=postprocessing,
        pig_panel=panel, ipdmhc_protein_records_by_locus=dict(catalogue),
        ipdmhc_commit=index['commit'], camsol_preparation_manifest_sha256=MANIFEST_SHA,
        camsol_remaining=prepared['blocked'], numerical_kernels='IMPLEMENTED_NOT_CONNECTED_TO_PRODUCTION_ASSESSMENT',
        calibration_published=False, formal_permissions_changed=False, deployment_performed=False,
        new_scientific_jobs=0, cancelled_jobs_resumed=0, frozen_assets=verify_freeze_manifest(),
        expert_questions=[
            dict(source='SOP S-16/S-27; v2 §3/§15', question='高置信 mature_chain 是否从逐残基 validated_functional/HARD 集合排除，只保留 S-45 链范围约束？其他独立功能域、E4、二硫键及用户固定依据是否仍逐项保留？', impact='当前233位点全固定，其中186位点仅有成熟链HARD依据；此分组不代表这186位点已获准变更。'),
            dict(source='A3 §2/§3; SOP S-17', question='请给出一条明确的项目后处理管线：采用哪列分数、Top20与阈值如何组合、先桥接还是先过滤短段、mean_score是否包含桥接残基，以及是否沿用当前CLI关闭长度特征。', fixed='0.1512、minlen=6、gap=2已明确；原包Top20使用round和稳定同分顺序已核验，不重新询问这些工具事实。'),
            dict(source='A1 §2/§7; 2026-09-26用户临时宿主面板', question='请提供猪SLA-DR/DQ的有版本等位基因及alpha/beta配对清单，并确认各配对可消费的%Rank校准来源；原始受体序列和异种HLA列表不等同于猪II预测结果。', reference='https://services.healthtech.dtu.dk/services/NetMHCIIpan-4.3/'),
            dict(source='C44 §2b/§7', question='I_pat是否仅计重叠的固定5残基窗口（7位交替段中心=3），还是枚举所有长度>=5子段（中心=6）？Roseman符号/变换如何记录？pH模式Arg缺pKa、Tyr在表中但不在酸性枚举，请给项目口径。', note='P2主文Methods已复核；PMC附件下载返回浏览器验证，未取得其Table S1，不声称附件检索已完成。', reference='https://pmc.ncbi.nlm.nih.gov/articles/PMC10025429/')])
    (output/'review.json').write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(dict(status=value['status'], mature_only=len(boundary['fixed_only_by_mature_chain']),
                         independently_fixed=len(boundary['also_fixed_by_independent_evidence']),
                         new_scientific_jobs=0, frozen=value['frozen_assets']), ensure_ascii=False))


if __name__ == '__main__':
    main()
