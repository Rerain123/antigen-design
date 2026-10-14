"""Record a source-backed comparison, not a replacement delivery plan."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'discovery/t01-phase1-real/m1-p4-20260922/n11-confirm-r01'
AUTH='工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/'
SOP=AUTH+'AgentA_SOP_v10.5_20260902.md'
GRAPH=AUTH+'一期裁剪算法图（一期 18 节点 + 落地优先级）.md'


def main():
    rows=[]
    def add(node,status,required,actual,impact,code,authority=SOP):
        rows.append(dict(node=node,status=status,expert_requirement=required,observed_implementation=actual,
            impact=impact,authority=authority,code=['src/t01_phase1_real/'+p for p in code]))
    add('输入','USER_APPROVED_SCOPE','序列、宿主、可选目标和表达宿主',
        'HiMat 只开放序列和宿主；默认 general，表达宿主为空。用户此前要求暂不新增两个可选入口。',
        '这是已确认的入口边界；不能把宿主物种当作表达宿主。',['service_api/himat.py'],GRAPH)
    add('N01','PARTIAL_ENTRY','本地 AF3/ESMFold2；最新用户决定禁止 RCSB/AFDB 联网查询',
        '两种预测工具均在 resident 注册表；HiMat 固定 ESMFold2、9–999 aa，未开放结构上传/引擎选择；新报告 233 aa 预测成功。',
        '后端能力与 HiMat 入口不同。禁止联网属于用户认可裁剪。',['service_api/himat.py','development/workflow/service.py'],GRAPH)
    add('N02','PARTIAL','DeepTMHMM 拓扑及 FreeSASA 暴露分析',
        '拓扑和绝对 SASA 可执行；RSA 出域报错不截断。该报告首末位约 1.073/1.079，正常 RSA 为空。',
        '影响 N10 标签暴露和 N13 RSA 对比；不能称暴露分析全部完成。',['development/structure/normalization.py','development/developability/compute.py'],GRAPH)
    add('N03','PARTIAL','C20：IEDB 本地 BLAST 70%/80% query 覆盖；E3 区间及 E4 4Å 重原子接触证据',
        'IEDB 蛋白库 202501 条；61 条 E3 经本次结果回连。仅无 gap 且区间残基完全相同才转移，较一般同源映射保守；无坐标提取 E4。',
        '本地检索/E3 接入已完成，E4 和部分同源区间覆盖不足；并非 C20 全能力完成。',['development/blast/iedb.py','development/blast/result.py'],AUTH+'ToolSpec_C20_IEDB镜像_BLAST_v10.5.md')
    add('N04','PARTIAL','BepiPred 3.0 分数、峰/区间及来源进入 S-19',
        '原工具可运行；项目峰选分数列、处理次序等 OI-026 未签收，N06 b_cell 峰处理仍 review_required。',
        '原始分数不等于已形成规范要求的重点表位。',['development/epitope_map/result.py'],GRAPH)
    add('N05','NOT_CONNECTED_IN_HIMAT','NetMHCpan 4.2 / NetMHCIIpan 4.3 与明确等位基因面板',
        'netmhc Worker 已登记；HiMat analysis.netmhc=null，未提供宿主面板。',
        '该入口不执行 T 细胞预测，猪物种名称不能自动替代面板。',['service_api/himat.py'],GRAPH)
    add('N06','PARTIAL','S-19 多来源 B/T 三图、权重合成、热点和逐残基密度',
        '已接收 IEDB E3 来源和 B/T 分流；有 E3 时热点=null/review_required；density=null。',
        '影响权限、糖基化遮蔽及表位保护；不是只缺发布签字。',['development/epitope_map/result.py'],GRAPH)
    add('N07','PARTIAL','糖基化 sequon 与热点遮蔽风险',
        'sequon 扫描可运行；热点不可用时判定 NOT_PERFORMED，shielding_risk=false 为 Schema 占位。',
        '不能把占位 false 解释成无风险。',['development/glycosylation/result.py'],GRAPH)
    add('N08','NOT_CONNECTED_IN_HIMAT','本地同源收集、MMseqs2/补充 BLAST、MAFFT、保守性',
        'homology Worker 已登记，但服务未设置 homology_database_root，HiMat 分支为 null；nr 库存在不等于 N08 已接通。',
        '没有本任务保守性证据及对应约束。',['service_api/himat.py','development/workflow/service.py'],GRAPH)
    add('N09','NOT_CONNECTED_IN_HIMAT','功能域与关键结构区域，供 S-27 约束消费',
        '服务 domains_database_root=null，HiMat 分支关闭；工程实现 core_map 仍 null。',
        '功能域/深层核心约束不完整。',['service_api/himat.py','development/domains/compute.py'],GRAPH)
    add('N10','PARTIAL','原蛋白可开发性多维基线及综合分',
        '表达性、A3D、PROPKA 有工程计算；CamSol 参数缺口、RSA 出域和部分科学消费未闭合；overall=null。',
        '不能完成依赖综合分的正式候选排序/SC-10。',['development/developability/compute.py'],GRAPH)
    add('Gate','PARTIAL','R-57 适用性分支和低质量/膜蛋白确认',
        '三态 Gate 已实现；HiMat 工程设计限制为已知适合且无额外约束的分支，科学释放关闭。',
        '适合设计不代表已执行；膜蛋白/低置信度确认后的完整设计域仍未开放。',['development/workflow/service.py','development/wt_draft/compute.py'])
    add('N11','T4_FIXED_ENGINEERING_SCOPE','S-27 证据权限；空 FIXED 且无 epitope_peaks 时 WARNING+用户确认',
        '本次新增同 run 待确认与接续、拒绝及审计绑定；新握手输入支持 mmCIF→PDB 三位小数转换并记录逐原子舍入来源；其余仍为保守 RESTRICTED 工程掩码，缺失 E4/core_map 等不会补造。',
        '本次修复确认机制，不等于完整科学权限合成已验收；已结束的旧任务不重开。',['development/workflow/confirmation.py','development/workflow/engineering.py','development/proteinmpnn/mapping.py','development/design_backend/permissions.py'],AUTH+'ToolSpec_C15_ProteinMPNN_v10.5.md')
    add('N12','PARTIAL','T-01 step17：24/0.1，全部淘汰后48/0.3、64/0.5重试；结构验证与保守突变检查',
        '仅一轮最多24、温度0.1；有 ESM-IF1 阈值放宽，但无追加48/64的重生成。最多3条代表重折叠/重评。',
        '阈值放宽不能算规范要求的自动重试；工程代表池不是完整验证候选池。',['development/proteinmpnn/policy.py','development/esm_if1/rules.py','development/variant_report/m1.py'])
    add('N13','PARTIAL','一期图：L1同一性、L2 RSA、L3局部叠合RMSD<2Å、L4预测画像，验证区=热点∪E4',
        'L1/L2/L4 部分工程逻辑；L3 当前计算 Cα 成对距离变化而非叠合 RMSD。WT/变体重评使用未检索的 BLAST 输入，未沿用本轮 IEDB 先验；域未接入。',
        '不能宣称完整表位保护验证通过，N03证据接续到N13仍有缺口。',['development/epitope_protection/compute.py','development/workflow/m1.py'],GRAPH)
    add('N14','PARTIAL_POOL','FoldX 5.0，以原始 WT 为设计基座的候选稳定性比较',
        '已部署 FoldX 原生及五轮 BuildModel 工程接续，WT 基座保留；只对最多3个代表候选计算。',
        '工具能力已有证据，但未覆盖专家要求的完整候选评分池。',['development/workflow/m1.py'],GRAPH)
    add('N15','NOT_FULLY_CONNECTED','Hard Filter→四维Pareto→目标权重→家族/序列多样性top20→SC-10',
        '有排除原因与 ESM-IF1 调试排序；Pareto算术仅隔离夹具，正式ranked_candidates/pareto_front/best_candidate保持空。',
        '排序不只是展示问题，生产候选池/打分/多样性和门控链仍缺失。',['development/variant_report/compute.py','development/variant_report/ranking.py','development/variant_report/m1.py'],GRAPH)
    add('N16','CONDITIONAL_NOT_CONNECTED','有表达宿主且有候选时密码子优化',
        '独立工具存在；HiMat未开放表达宿主，主链保持NO_QUALIFIED_CANDIDATE或N16_BUSINESS_LINEAGE_UNAPPROVED。',
        '当前不产候选DNA，不能把猪物种当作表达宿主填入。',['development/workflow/m1.py'],GRAPH)
    add('N17','LIMITED_ENGINEERING_SCOPE','WT可扫描覆盖位点，排除FIXED∪RESTRICTED，FoldX/ThermoMPNN参考',
        '调度 scan_scope 将可用 OPEN 位点截为[:1]；无 OPEN 就跳过。ThermoMPNN原生可全扫描但仅展示所选位点。',
        '有限工程验证不等于完整可扫描位点参考结果。',['development/workflow/m1.py'],GRAPH)
    add('N18','PARTIAL_DELIVERY','候选清单、WT对照、来源/缺项/风险，正式Schema及交接',
        '可交付带hash的本地工程ZIP；本次修复N11执行事实优先显示。正式CandidateRecord/Agent C协议与科学资格仍关闭。',
        '报告生成成功不等于科学流程完整或候选合格。',['development/local_delivery/compute.py','service_api/himat.py'],GRAPH)
    refs=sorted({r['authority'] for r in rows}|{GRAPH,SOP})
    source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in refs}
    live=json.loads((OUT/'live-source-before.json').read_bytes())
    for row in rows:
        row['code_before']=[dict(path=p,live_sha256=live['files'].get(p.removeprefix('src/t01_phase1_real/')),
             local_sha256=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()) for p in row['code']]
    evidence=dict(kind='EXPERT_DEPLOYED_CODE_COMPARISON',baseline_generation=83,
        post_fix_deployment_evidence='../n11-confirm-deployment-r15.json',
        method='Expert originals + observed deployment source hashes/registry/arguments + user-provided run. No new scientific workflow started.',
        source_hashes=source_hashes,rows=rows,
        user_scope_exclusions=['RCSB/AFDB联网回退','S-23安全三联筛','MD','其他一期图明确裁剪能力'],
        scientific_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')
    (OUT/'expert-comparison.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(rows=len(rows),file=str(OUT/'expert-comparison.json')),ensure_ascii=False))


if __name__=='__main__':main()
