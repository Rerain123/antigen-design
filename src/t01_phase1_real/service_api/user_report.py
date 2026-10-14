"""Offline user presentation of existing, verified delivery facts (no scoring).

Basis: expert SOP v10.5 S-42 and T-01 step 27; Schema FailureReport and C29.
The current engineering delivery is not relabelled as a signed CandidateRecord.
All dynamic text is escaped; no scripts, remote assets or arbitrary input links.
"""
from html import escape
import io
import json
import math
import zipfile

VERSION = '2.1'
LABELS = {'structure':'结构质量','topology':'跨膜与信号肽','blast':'文献表位证据',
    'bepipred':'B 细胞表位预测','netmhc':'T 细胞表位预测','epitope_map':'综合表位图谱',
    'glycosylation':'糖基化位点','homology':'同源保守性','domains':'功能区域',
    'developability':'可开发性','solubility':'溶解性','aggregation':'聚集倾向',
    'ph_stability':'pH 稳定性','expressibility':'表达倾向','tag_exposure':'标签暴露',
    'stability':'结构稳定性','stability_ddg':'稳定性 ΔΔG','prediction':'结构预测','design':'候选生成',
    'protection':'表位保护复评','variant_report':'候选结果汇总','wt_draft':'原始蛋白评估',
    'wt_reference':'原始蛋白稳定性参考','codon':'密码子优化','local_delivery':'结果整理'}
REASONS = {'R35_DETERIORATION_EXCEEDED':'序列与结构适配性评分未通过当前筛选规则',
    'NO_DESIGNABLE_POSITIONS':'所有位点均被当前权限规则固定，可修改位点为 0，未调用原生候选生成器。',
    'DESIGN_NOT_EXECUTED':'候选生成未执行，依赖候选的计算未启动',
    'DEVELOPABILITY_OVERALL_UNAVAILABLE':'可开发性总分尚未取得',
    'S40_COMPONENTS_UNAVAILABLE':'可开发性分项数据不足，无法重算总分',
    'N13_NOT_COMPUTED':'尚未完成候选表位保护复评',
    'N13_STRUCTURAL_INCOMPLETE':'表位保护所需结构验证不完整',
    'N13_EPITOPE_VIOLATION':'未通过表位结构保护检查',
    'NON_STANDARD_CONSTRAINT_OVERRIDE':'用户覆盖保护约束，候选单列，不参与标准排序',
    'CONSTRAINT_AUDIT_UNAVAILABLE':'缺少设计约束核验结果',
    'SOFT_CONSTRAINT_MAP_INCOMPLETE':'缺少突变位点的完整约束信息',
    'BURDEN_DIMENSIONS_INCOMPLETE':'突变负担仍有维度未完成',
    'N12_S28_NOT_VERIFIED':'候选尚未通过完整的序列与结构验证',
    'OBJECTIVE_SOURCE_UNAVAILABLE':'缺少已核验的设计目标',
    'PLDDT_BELOW_0_50':'预测结构的平均置信度低于 0.50，未通过结构验证',
    'S28_PREDICTION_FAILED_RETAIN_R35':'结构预测失败；保留序列评分结果，尚无结构验证',
    'R04_ROUTE_UNRESOLVED':'当前突变数和比例的结构路由尚待明确，未完成验证',
    'STRUCTURE_VALIDATION_NOT_EXECUTED':'结构工具未执行，未完成验证',
    'WT_MSA_ASSET_UNAVAILABLE':'原始蛋白比对准备所需的本地资源不可用，候选 AF3 复核未执行',
    'WT_MSA_ASSET_MISSING':'原始蛋白比对准备缺少本地资源，候选 AF3 复核未执行',
    'WT_MSA_TOOL_FAILED':'原始蛋白比对准备失败，候选 AF3 复核未执行',
    'WT_MSA_TIMEOUT':'原始蛋白比对准备超时，候选 AF3 复核未执行',
    'ENGINEERING_BURDEN_EXCEEDED':'突变负担超过当前试运行筛选范围',
    'TOOL_FAILED':'工具计算未成功，相关结论暂不可用', 'TIMEOUT':'计算超时，相关结论暂不可用',
    'ASSET_MISSING':'所需模型、数据或运行资源暂不可用',
    'OUTPUT_INVALID':'结果校验未通过，未采纳该结果',
    'HASH_MISMATCH':'结果完整性校验未通过，未采纳该结果',
    'NO_QUALIFIED_CANDIDATE':'当前没有可用于后续处理的合格候选',
    'EXPRESSION_HOST_NOT_PROVIDED':'未提供表达宿主，未进行密码子优化',
    'UNOPTIMIZED_DNA_FALLBACK':'优化约束未能全部满足；展示的是未优化 DNA，需人工复核',
    'UNSUPPORTED_EXPRESSION_HOST':'该表达宿主尚未配置可用的密码子表，未生成 DNA',
    'N16_SOURCE_UNAVAILABLE':'密码子优化没有可用结果',
    'N11_MASK_EXPORT_BLOCKED':'当前设计约束未形成可执行输入，候选设计未执行',
    'STRUCTURE_UNAVAILABLE':'原始蛋白结构未能取得，候选设计未执行',
    'DESIGN_APPLICABILITY_INPUT_INSUFFICIENT':'设计判断所需输入不足，候选设计未执行',
    'T4_EMPTY_FIXED_CONFIRMATION_REQUIRED':'缺少固定保护位点，候选设计等待用户确认',
    'T4_DESIGN_DECLINED':'用户未同意本次候选设计',
    'PARTIAL_DEVELOPABILITY':'可开发性只完成部分维度，无法给出完整综合判断',
    'DNA_NOT_PROVIDED':'本次未提供优化后的 DNA 序列',
    'NO_NATIVE_SCAN_EXECUTED':'本次未完成原始蛋白稳定性扫描',
    'N14_TOP40_REQUIRES_COMPLETE_RELIABLE_FIVE_DIMENSION_SCORES':'候选超过 40 个，缺少完整可靠的五维可开发性分数，未任意截取评分池',
    'N14_S28_VALIDATION_REQUIRED':'尚无完整候选验证结果，未启动变体稳定性评分',
    'NO_VALIDATED_MUTANT_FOR_N14':'没有通过当前验证且发生突变的候选，未启动变体稳定性评分',
    'N14_LOW_CONFIDENCE_WT_SKIPPED':'原始蛋白结构置信度低，按规则跳过变体稳定性评分',
    'N14_MEMBRANE_WT_SKIPPED':'原始蛋白为膜蛋白，按规则跳过变体稳定性评分',
    'N14_MEMBRANE_STATUS_UNAVAILABLE':'膜蛋白属性未明确，变体稳定性评分未执行',
    'N14_MAPPING_FAILED_BATCH_UNAVAILABLE':'结构编号映射失败，本批候选未取得可用稳定性分数',
    'N14_MAPPING_PARTIAL_VARIANTS_SKIPPED':'部分候选结构编号无法映射，已跳过；其余候选保留已核验的五轮稳定性分数',
    'NO_USABLE_NATIVE_SCAN_RESULT':'本次未取得可用的原始蛋白稳定性扫描结果',
    'R39_MULTICHAIN_THERMOMPNN_SKIPPED':'该结构包含多条蛋白链，按规则仅使用 FoldX',
    'N17_DOWNSTREAM_TIME_RESERVE':'剩余时间不足，保留时间整理已有结果',
    'NO_COVERED_EXPLICIT_OPEN_SCAN_POSITION':'结构覆盖范围内没有允许扫描的位点',
    'LOW_CONFIDENCE_SCAN_SKIPPED':'结构置信度低，本次未执行稳定性扫描',
    'MEMBRANE_SCAN_DOMAIN_NOT_SUPPORTED':'膜蛋白适用扫描区域尚未接通，本次未执行',
    'VARIANT_PREDICTION_UNAVAILABLE_S28_WARNING':'候选结构预测不可用，依赖结构的检查未完成'}
STATES = {'succeeded':'已完成计算','failed':'计算失败','timed_out':'计算超时',
    'cancelled':'已取消','skipped':'未执行','unavailable':'暂不可用', 'missing':'缺少输入',
    'not_executed':'未执行','running':'计算中','reconciling':'处理中','queued':'等待执行',
    'awaiting_confirmation':'等待确认','available':'已有结果','pending':'尚未完成'}


def esc(value):
    return escape(str(value), quote=True)


def number(value, digits=2):
    return f'{value:.{digits}f}' if type(value) in (int,float) and math.isfinite(value) else '未评估'


def obs(data, name):
    return (((data.get('wt_draft') or {}).get('assessments') or {}).get(name) or {}).get('observations') or {}


def reason(code):
    return REASONS.get(code, '该项尚不具备完整判断条件，详细依据保留在原始附件中。')


def table(headers, rows):
    return '<div class="table-wrap"><table role="table"><thead><tr role="row">'+''.join('<th scope="col" role="columnheader">'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr role="row">'+''.join('<td role="cell" data-label="'+esc(headers[i])+'">'+c+'</td>' for i,c in enumerate(row))+'</tr>' for row in rows)+'</tbody></table></div>'


def series_svg(series, title):
    """Plot original numbers on labelled axes; never infer thresholds or gaps."""
    finite=[v for _,values,_ in series for v in values if type(v) in (int,float) and math.isfinite(v)]
    if not finite:return '<p class="empty">暂无可绘制的逐残基数据。</p>'
    low,high=min(finite),max(finite)
    if low==high:low-=.05;high+=.05
    n=max(len(v) for _,v,_ in series);items=[]
    for frac in (0,.5,1):
        y=180-140*frac
        items.append(f'<path d="M52 {y}H852" stroke="#e0e7e9"/><text x="42" y="{y+4}" text-anchor="end">{number(low+(high-low)*frac)}</text>')
    for label,values,color in series:
        paths=[];current=[]
        for i,v in enumerate(values):
            if type(v) not in (int,float) or not math.isfinite(v):
                if current:paths.append(current);current=[]
                continue
            x=52+800*i/max(1,n-1);y=180-140*(v-low)/(high-low)
            current.append((x,y))
        if current:paths.append(current)
        for points in paths:
            if len(points)==1:
                x,y=points[0];items.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="{color}"/>')
            else:
                d='M'+' L'.join(f'{x:.2f} {y:.2f}' for x,y in points)
                items.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.2"/>')
    items.extend([f'<text x="52" y="204">1</text><text x="852" y="204" text-anchor="end">{n}</text>',
        '<text x="452" y="225" text-anchor="middle">氨基酸位置</text>'])
    legend=''.join(f'<span><i style="background:{color}"></i>{esc(label)}</span>' for label,_,color in series)
    return f'<figure><figcaption class="chart-title">{esc(title)}</figcaption><div class="chart-scroll" tabindex="0" role="region" aria-label="{esc(title)}，窄屏可横向滚动"><svg viewBox="0 0 880 240" role="img" aria-label="{esc(title)}"><title>{esc(title)}</title>'+''.join(items)+'</svg></div><div class="legend">'+legend+'</div><p class="chart-hint">左右滑动查看完整曲线</p></figure>'


CSS = '''
:root{color-scheme:light;--ink:#20334a;--muted:#627389;--line:#dce5ea;--accent:#147d83;--paper:#fff;--navy:#122d45}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:28px}body{margin:0;background:#edf2f5;color:var(--ink);font:15px/1.85 'Segoe UI','Microsoft YaHei',sans-serif;-webkit-font-smoothing:antialiased}a{color:var(--accent)}header{background:var(--navy);color:white}.bar{max-width:1280px;margin:auto;padding:20px 44px;display:flex;align-items:center;justify-content:space-between;gap:20px}.brand{font-size:12px;letter-spacing:2px}.brand b{font-weight:800}.edition{font-size:11px;color:#bbd2dc;letter-spacing:1.5px}main{max-width:1280px;margin:0 auto 56px;padding:0 44px}.hero{background:var(--navy);color:white;margin:0 -44px;padding:44px 44px 38px;position:relative;border-bottom:4px solid #42b7af}.kicker{font-size:11px;letter-spacing:3px;color:#8ed4cf;margin:0 0 12px}h1{font-family:'SimSun','Songti SC',serif;font-size:42px;line-height:1.4;letter-spacing:3px;margin:0 0 28px;font-weight:600}.hero .lead{font-size:23px;font-weight:600;margin:0 0 10px}.hero .note{max-width:850px;color:#cad9e3;font-size:14px;margin:0}.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0;background:white;border:1px solid var(--line);border-top:0;border-radius:0 0 12px 12px;box-shadow:0 8px 25px #1a35420a;margin:0 0 26px;padding:24px 8px}.stat{padding:0 24px;border-right:1px solid var(--line)}.stat:last-child{border:0}.stat strong{display:block;font-size:29px;font-weight:650;line-height:1.4;letter-spacing:.4px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}.stat span{display:block;margin-top:6px;font-size:12px;color:var(--muted)}.report-layout{display:grid;grid-template-columns:164px minmax(0,1fr);gap:28px;align-items:start}.report-body{min-width:0}nav{position:sticky;top:24px;display:flex;flex-direction:column;gap:6px;padding:16px 0}nav:before{content:'报告目录';display:block;color:var(--muted);font-size:11px;letter-spacing:2px;padding:0 14px 12px}nav a{font-size:13px;text-decoration:none;color:#52687d;min-height:44px;display:flex;align-items:center;border-radius:7px;padding:8px 14px;border:1px solid transparent}nav a:hover{background:white;color:var(--accent);border-color:var(--line)}.panel{background:white;border:1px solid var(--line);border-radius:12px;padding:30px;margin-bottom:22px;box-shadow:0 5px 20px #20334a04;scroll-margin-top:24px}.section-head{display:flex;align-items:center;gap:14px;padding-bottom:20px;margin-bottom:23px;border-bottom:1px solid var(--line)}.section-no{width:38px;height:38px;display:grid;place-items:center;border-radius:9px;background:#eaf5f3;color:var(--accent);font-family:Georgia,serif;font-size:21px;flex-shrink:0}h2{font-size:23px;line-height:1.45;letter-spacing:.5px;margin:0}h3{font-size:17px;line-height:1.6;margin:28px 0 12px}h3:first-child{margin-top:0}h4{font-size:14px;margin:23px 0 10px;color:#476178}p{margin:9px 0}.subtle{color:var(--muted);font-size:13px}.wide-note{padding:14px 17px;background:#f3f7f9;border-radius:8px;margin:18px 0;font-size:13px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:25px}.grid>*{min-width:0}.fact-list{margin:0}.fact-list div{display:flex;justify-content:space-between;gap:18px;padding:11px 0;border-bottom:1px solid #eef2f4}.fact-list dt{color:var(--muted);font-size:13px}.fact-list dd{margin:0;text-align:right;overflow-wrap:anywhere;font-weight:550;font-size:13px}.finding{padding:17px;background:#f1f7f7;border:1px solid #dfebea;border-radius:8px;margin:15px 0;font-size:13px}.finding strong{display:block;color:#176e73;font-size:15px;margin-bottom:8px}.badge{display:inline-block;padding:3px 9px;white-space:nowrap;border-radius:5px;background:#e9f5f2;color:#187168;font-size:12px;font-weight:600}.badge.warn{background:#faf1dc;color:#89631f}.badge.danger{background:#f9e9e6;color:#a64d42}.notice{padding:15px 18px;border-left:3px solid #c9a14d;border-radius:0 7px 7px 0;background:#fcf7ec;color:#79612e;font-size:13px;margin:22px 0}.empty{padding:22px;background:#f6f8fa;color:var(--muted);border-radius:8px}.table-wrap{overflow-x:auto;margin:16px 0;border:1px solid var(--line);border-radius:8px}table{width:100%;border-collapse:collapse;font-size:12px}th{background:#edf3f6;text-align:left;color:#405b70;font-weight:650;padding:12px 11px;border-bottom:1px solid #d4e0e6;line-height:1.65}td{padding:12px 11px;border-bottom:1px solid #e8eef1;vertical-align:top;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}tr:last-child td{border-bottom:0}tbody tr:nth-child(even){background:#f9fbfc}tbody tr:hover{background:#f1f8f7}td:first-child{font-weight:550}td a{white-space:nowrap}details{border:1px solid var(--line);border-radius:8px;margin:13px 0;background:#fff;padding:0 16px}summary{cursor:pointer;min-height:48px;align-content:center;color:#36576c;font-size:13px;padding:11px 0}details[open]>summary{border-bottom:1px solid var(--line);margin-bottom:14px}details[open]{padding-bottom:14px}summary::marker{color:var(--accent)}summary:focus-visible,a:focus-visible,.chart-scroll:focus-visible{outline:2px solid #168f94;outline-offset:3px}.candidate-card{padding:0 18px;margin:14px 0;border-left:3px solid #548e99;background:#fcfefe}.candidate-card>summary{font-size:16px;font-weight:650;line-height:1.6;padding:16px 0}.candidate-meta{font-size:12px;color:var(--muted);font-weight:400;float:right;padding-top:3px}.candidate-card:target>.candidate-body{display:block;content-visibility:visible}.candidate-card:target::details-content{display:block;content-visibility:visible}.candidate-card:target{border-color:var(--accent);box-shadow:0 0 0 3px #1784881c}.candidate-body{padding:3px 0 7px}.candidate-body h4{border-left:3px solid #9ecbc9;padding-left:10px}.candidate-body .mono{background:#edf5f5;border-radius:6px;padding:13px;color:#286571;font-size:13px}pre{white-space:pre-wrap;word-break:break-word;background:#f5f7f9;padding:16px;font-size:12px;max-height:380px;overflow:auto}.seq{display:grid;grid-template-columns:35px minmax(0,1fr);gap:5px 14px;font:13px/1.9 Consolas,monospace;overflow-wrap:anywhere;padding:12px 0}.seq span{color:#8293a4}.seq code{letter-spacing:1px;word-break:break-all}figure{margin:22px 0;padding:18px 12px 15px;background:#f8fbfc;border:1px solid #e2ebef;border-radius:9px}.chart-title{font-size:13px;font-weight:600;color:#405d70;padding:0 10px 5px}svg{width:100%;display:block;font:12px 'Segoe UI','Microsoft YaHei',sans-serif;fill:#627389}.chart-scroll{overflow-x:auto;overscroll-behavior-x:contain}.chart-hint{display:none}.legend{display:flex;gap:20px;justify-content:center;flex-wrap:wrap;font-size:11px;color:var(--muted)}.legend i{display:inline-block;width:18px;height:3px;vertical-align:middle;margin-right:7px}.limitations{padding-left:20px;font-size:14px}.limitations li{padding:6px 0}.footer{display:flex;justify-content:space-between;gap:20px;padding:25px 0;color:var(--muted);font-size:11px;border-top:1px solid var(--line)}.mono{font-family:Consolas,monospace;overflow-wrap:anywhere}small{font-size:12px}.takeaways{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:0 0 24px}.takeaway{border:1px solid var(--line);border-top:3px solid #21878b;background:white;border-radius:8px;padding:17px}.takeaway strong{display:block;font-size:14px;margin-bottom:6px;color:#235f6b}.takeaway p{font-size:12px;color:var(--muted);margin:0}.note{overflow-wrap:anywhere}
@media screen and (max-width:1050px){main{padding:0 26px}.bar{padding:20px 26px}.hero{margin:0 -26px;padding:36px 26px}.report-layout{grid-template-columns:1fr;gap:0}nav{position:static;flex-direction:row;flex-wrap:wrap;padding:0 0 20px;gap:3px}nav:before{display:none}nav a{padding:7px 11px;background:#ffffff88}.panel{padding:26px}}
@media screen and (max-width:680px){main{padding:0 16px;margin-bottom:25px}.bar{padding:17px 20px;gap:10px}.hero{margin:0 -16px;padding:30px 22px}.brand{font-size:11px;letter-spacing:1px}.edition{font-size:10px;max-width:108px;text-align:right}h1{font-size:31px;letter-spacing:2px;margin-bottom:23px}.hero .lead{font-size:20px}.hero .note{font-size:13px}.stats{grid-template-columns:1fr 1fr;padding:17px 0;gap:22px 0}.stat{padding:0 19px}.stat:nth-child(2){border:0}.stat strong{font-size:26px}.stat span{font-size:11px}.takeaways{grid-template-columns:1fr;gap:9px;margin-bottom:17px}.takeaway{padding:13px 16px}.takeaway strong{margin-bottom:3px}.panel{padding:22px 17px;border-radius:9px;margin-bottom:16px}.section-head{gap:11px;margin-bottom:18px;padding-bottom:17px}.section-no{width:32px;height:32px;font-size:19px}h2{font-size:20px}h3{font-size:16px;margin-top:25px}.grid{grid-template-columns:1fr;gap:10px}.fact-list div{font-size:13px}.chart-scroll svg{min-width:620px}.chart-hint{display:block;font-size:11px;color:var(--muted);padding:0 10px}.legend{justify-content:flex-start;gap:6px 14px;padding:0 10px}.table-wrap{overflow:visible;border:0;border-radius:0;margin:13px 0}table,tbody,tr,td{display:block;width:100%}thead{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}tbody tr,tbody tr:nth-child(even){display:grid;grid-template-columns:1fr 1fr;gap:0 14px;padding:12px 14px;border:1px solid var(--line);border-radius:7px;margin-bottom:10px;background:#f8fbfc}td{border:0;padding:5px 0;font-size:13px;min-height:28px}td:before{content:attr(data-label);display:block;font-size:11px;color:var(--muted);font-weight:400;margin-bottom:2px}td:first-child,td:last-child{grid-column:1 / -1}td:first-child{font-size:14px;font-weight:650;margin-bottom:3px}.candidate-meta{display:block;float:none;margin-left:16px}.candidate-card{padding:0 12px}.candidate-card>summary{font-size:15px}.notice{font-size:12px;padding:13px}.footer{display:block;line-height:2}.footer span{display:block}.seq{font-size:12px;gap:4px 8px;grid-template-columns:25px minmax(0,1fr)}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
@media print{body{background:white;font-size:10px}main{max-width:none;margin:0;padding:0}header,nav{display:none}.report-layout{display:block}.hero{margin:0;padding:15px 0;color:#122d45;background:white;border-bottom:2px solid #147d83}.hero .kicker,.hero .note{color:#52687d}h1{font-size:27px;margin-bottom:14px}.hero .lead{font-size:18px}.hero .note{font-size:11px}.stats{box-shadow:none;border:0;border-bottom:1px solid var(--line);border-radius:0;padding:15px 0;margin-bottom:18px}.stat strong{font-size:21px}.stat span{font-size:10px}.panel{border:0;border-radius:0;box-shadow:none;padding:20px 0;margin:0;break-inside:auto}.section-head{margin-bottom:14px;padding-bottom:10px}h2{font-size:19px}h3{font-size:14px}h2,h3,h4,.section-head{break-after:avoid}tr,.finding,figure,.takeaways{break-inside:avoid}details:not([open]):not(.candidate-card){display:none}.candidate-card{break-inside:auto;padding:10px 0;border:0;border-top:1px solid var(--line)}.candidate-card>summary{font-size:15px}.candidate-card>.candidate-body{display:block!important;content-visibility:visible!important}.candidate-card::details-content{content-visibility:visible!important;display:block!important}.table-wrap{overflow:visible}table{font-size:9px}th,td{padding:7px 6px}figure{padding:10px;margin:15px 0}pre{max-height:none}.takeaway{padding:11px}.takeaway p,.subtle,.notice{font-size:10px}.footer{font-size:9px}.badge{-webkit-print-color-adjust:exact;print-color-adjust:exact}@page{size:A4;margin:15mm}}
'''


def render(data, workflow=None, *, preview_note='', native_results=None):
    """Render a current LOCAL_ENGINEERING_DELIVERY_PACKAGE without inventing results."""
    workflow=workflow or {};nodes=workflow.get('nodes') or {}
    if isinstance(workflow.get('job'),dict):workflow={**workflow['job'],**workflow}
    subject=data.get('subject') or {};seq=subject.get('protein_sequence') or ''
    report=data.get('variant_report') or {};records=report.get('records') or []
    assessments=(data.get('wt_draft') or {}).get('assessments') or {}
    fact=data.get('design_execution') or {}
    if 'design' in nodes or 'revision_design' in nodes:
        from ..development.workflow.reporting import design_fact
        fact=design_fact(nodes)
    excluded=sum(r.get('disposition')=='EXCLUDED' for r in records)
    failed=[(n,r) for n,r in nodes.items() if r.get('state') in ('failed','timed_out','cancelled')]
    if workflow.get('state') in ('running','queued','reconciling'):
        headline='分析仍在进行，当前为阶段性结果';summary='尚不能据此给出完整候选结论。'
    elif workflow.get('state') in ('failed','cancelled','timed_out'):
        headline='本次分析未完整完成';summary='下文保留已经得到的结果，并说明未完成的部分。'
    elif fact.get('status')=='NOT_EXECUTED':
        headline='本次未生成设计候选';summary=reason(fact.get('reason_code'))
    elif records and excluded==len(records):
        headline='本轮暂无可推荐候选';summary=f'共记录 {len(records)} 个设计候选，全部被当前筛选规则排除。原始蛋白结果及排除原因保留如下。'
    elif records:
        headline='已获得候选计算结果，仍需复核';summary='候选按原始记录顺序展示；尚未形成可用于实验决策的正式推荐排名。'
    else:
        headline='已整理原始蛋白分析，暂无候选结论';summary='本报告展示已有计算结果；未执行或缺失的项目均单独标注。'
    if workflow.get('expert_revision') and workflow.get('state') not in ('failed','cancelled','timed_out','running','queued','reconciling'):
        revision=workflow['expert_revision'];count=len(revision['formal_records'])
        from .native_report import CHECKS, unique_candidates
        unique=len(unique_candidates(revision['formal_records']))
        headline='候选科学结果汇总' if count else '本次未形成正式设计候选'
        summary=f'正式生成 {count} 条记录，去重后 {unique} 条。以下展示候选序列、计算数值和逐项检查结果。'
    if failed:summary+=f' 本次有 {len(failed)} 个内部计算步骤失败或停止。'
    def badge(label,kind=''):return f'<span class="badge {kind}">{esc(label)}</span>'
    def section(index,title,content):return f'<section class="panel" id="s{index}"><div class="section-head"><span class="section-no">0{index}</span><h2>{title}</h2></div>{content}</section>'
    def facts(rows):return '<dl class="fact-list">'+''.join(f'<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k,v in rows)+'</dl>'
    quality=obs(data,'structure').get('analysis') or {};quality=quality.get('quality') or {}
    structure=quality.get('structure') or {};topology=obs(data,'topology').get('topology') or {}
    dev=obs(data,'developability').get('developability') or {};glyco_obs=obs(data,'glycosylation')
    glyco=glyco_obs.get('glycosylation') or {};glyco_assess=glyco_obs.get('hotspot_assessment') or {}
    structure_name={'user_experimental':'用户提供的实验结构（来源待核验）','esmfold2_predicted':'ESMFold2 预测结构','af3_predicted':'AlphaFold3 预测结构'}.get(structure.get('source'),'结构来源未提供')
    confidence={'high':'高','medium':'中','low':'低'}.get((quality.get('quality') or {}).get('confidence'),'未评估')
    overview='<div class="grid">'+facts([('分析对象','原始蛋白（WT）'),('氨基酸长度',f'{len(seq)} aa' if seq else '未提供'),('免疫宿主',subject.get('host_species') or '未提供'),('表达宿主',subject.get('expression_host') or '未提供')])+facts([('结构来源',structure_name),('结构置信分档',confidence),('平均 pLDDT',number(structure.get('mean_plddt'))),('跨膜区数量',str(topology['tm_count']) if topology.get('tm_count') is not None else '未评估')])+'</div>'
    declaration=structure.get('declaration') or {}
    if declaration.get('note'):
        overview+='<p class="notice">结构来源说明：'+esc(declaration['note'])+'</p>'
    overview+='<details><summary>查看输入氨基酸序列</summary><div class="seq">'+''.join(f'<span>{i+1}</span><code>{esc(seq[i:i+50])}</code>' for i in range(0,len(seq),50))+'</div></details>'
    epitope=obs(data,'epitope_map').get('epitopes') or {}
    hotspot=epitope.get('b_cell_antigenic_hotspot_map') or {};hotspots=hotspot.get('hotspots')
    raw=obs(data,'bepipred').get('raw_scores') or []
    # Each tool column remains distinct. OI-026 does not permit selecting a peak rule.
    curves=[('BepiPred-3.0 score',[r.get('ensemble_probability') for r in raw],'#344f80'),
            ('Linear epitope score',[r.get('linear_epitope_score') for r in raw],'#a58b69')]
    epitope_content='<p>预测分数用于观察序列中的相对变化，不能直接等同于实验免疫效果。</p>'+series_svg(curves,'BepiPred 两列原始逐残基分数')
    epitope_content+='<p class="subtle">保留两列工具原始分数；本报告不据曲线自行选峰、设阈值或补算热点。断点表示缺失值。</p>'
    channels=obs(data,'netmhc').get('channels') or {};channel_rows=[]
    for key,title in (('mhc_i','MHC I'),('mhc_ii','MHC II')):
        channel=channels.get(key) or {};hits=channel.get('hits')
        valid=channel.get('status')=='parsed_unreviewed'
        sb=sum(h.get('classification')=='SB' for h in hits) if valid and isinstance(hits,list) else None
        native_channel=(((native_results or {}).get('nodes',{}).get('netmhc') or {}).get('mhc_summary') or {}).get(key) or {}
        if native_channel.get('counts_complete'):sb=native_channel['counts']['SB']
        channel_rows.append([title,'已有预测' if valid else '暂无完整结果',esc(str(sb) if sb is not None else '未汇总')])
    epitope_content+=table(['T 细胞预测通道','当前状态','强结合肽条目（SB）'],channel_rows)
    panel=obs(data,'netmhc').get('panel_selection') or {}
    if panel.get('provisional'):
        epitope_content+='<p class="wide-note">本次使用临时宿主等位基因面板，来源为本地工具支持清单，尚未验证猪群覆盖。'
        if (panel.get('unavailable_reasons') or {}).get('mhc_ii'):
            epitope_content+=' MHC-II 未评估：尚无经过验证、可返回所需分数的猪 SLA-II 配置。'
        epitope_content+='</p>'
    epitope_content+='<p class="subtle">SB 为工具给出的强结合分类，条目数不等于实验表位数量。面板覆盖以实际运行配置为准，不将通用面板解释为宿主专用验证。</p>'
    epitope_content+='<div class="grid"><div class="finding"><strong>综合抗原热点</strong>'+('已记录 '+str(len(hotspots))+' 个热点。' if isinstance(hotspots,list) else '热点尚未形成可用结论。')+(' 空结果不代表不存在实验表位。' if hotspots==[] else '')+'</div><div class="finding"><strong>糖基化</strong>'+(f'检测到 {glyco["site_count"]} 个序列位点。' if glyco.get('site_count') is not None else '序列位点尚未评估。')+(' 遮蔽风险未完成判定。' if glyco_assess.get('status')!='EVALUATED' or not glyco_assess.get('windows') else '遮蔽判定仅覆盖已评估窗口。')+'</div></div>'
    dims=dev.get('dimensions') or {};dimension_rows=[]
    for key in ('solubility','aggregation','ph_stability','expressibility','tag_exposure','stability'):
        dimension=dims.get(key) or {};score=dimension.get('normalized_score')
        label='已纳入本次综合计算' if dimension.get('included_in_overall') else '有局部观察，未纳入综合计算' if dimension.get('value') is not None else '尚未得到可用结果'
        dimension_rows.append([esc(LABELS[key]),esc(number(score)),esc(label)])
    dev_content='<p class="wide-note">综合可开发性分数：<strong>'+esc(number(dev.get('overall_score')))+'</strong>。缺失值不按零分处理。</p>'+table(['维度','归一化分数','可用性'],dimension_rows)
    engines=(data.get('wt_reference') or {}).get('engines') or {}
    if engines:
        scan_rows=[]
        terminals=(data.get('n17_execution') or {}).get('engines') or {}
        for name,item in engines.items():
            coverage=item.get('coverage') or {};requested=item.get('requested_positions')
            terminal=terminals.get(name) or {};state=terminal.get('state') or (item.get('source') or {}).get('job_state') or item.get('state')
            status={'succeeded':'已执行','available':'已执行','failed':'失败','timed_out':'超时','skipped':'按条件跳过','missing':'未提供结果'}.get(state,'未核验')
            failure=terminal.get('reason_code') or (item.get('source') or {}).get('error_code')
            if failure:status+='：'+reason(failure)
            scan_rows.append([esc(name),str(len(requested)) if requested is not None else '未执行',
                str(len(item.get('effective_positions') or [])),
                '已覆盖本次请求的全部位点及氨基酸替换' if coverage.get('complete') else '未完成或覆盖未核验',esc(status)])
        dev_content+='<h3>原始蛋白稳定性扫描</h3><p class="subtle">仅扫描结构覆盖且权限允许的位点，排除固定和受限位置。长序列按适用区域选择；完整性只针对本次请求范围，不表示全蛋白或科学验证通过。失败、超时不会被计作扫描完成。</p>'+table(['工具','请求位点','已得到结果的位点','覆盖状态','执行状态与原因'],scan_rows)
    n14=(data.get('variant_report') or {}).get('n14_execution')
    if n14:
        coverage=n14.get('coverage') or {};pool=n14.get('pool') or {}
        dev_content+='<h3>候选稳定性评分</h3><p>评分要求：以原始蛋白结构为共同基座，每个候选执行 FoldX BuildModel 5 轮。实际完成数量见下表；未返回结果的候选稳定性保持未评估。</p>'
        dev_content+=table(['验证后突变候选','本次请求','返回结果','执行状态'],[[
            str(pool.get('eligible_count','未评估')),str(coverage.get('requested',0)),str(coverage.get('returned',0)),
            esc(STATES.get(n14.get('state'),'未评估'))]])
        if n14.get('reason_code'):dev_content+='<p class="subtle">'+esc(reason(n14['reason_code']))+'</p>'
        if pool.get('n13_scope'):dev_content+='<p class="subtle">稳定性评分范围独立于表位保护复评范围；尚未完成保护复评的候选不会因此被标记为合格。</p>'
    candidate_dev=(data.get('variant_report') or {}).get('candidate_developability')
    for note in (data.get('variant_report') or {}).get('engineering_adjustments',[]):
        dev_content+='<h3>结果适用范围</h3><p class="notice">'+esc(note['message'])+'</p>'
    if candidate_dev:
        dev_content+='<h3>候选六维可开发性汇总</h3><p>未指定权重时使用专家建议的等权起始配置，仍需回测；仅对可用且可靠的维度重新归一权重。缺少可靠溶解性时不生成综合分。稳定性缺失不会在六维汇总中补成中性分。</p>'
        dev_rows=[]
        for item in candidate_dev['records']:
            d=item.get('developability') or {}
            dev_rows.append([esc(item['id']),number(d.get('overall_score')),str(d.get('dev_dims_available',0))+'/6',
                number(d.get('stability_ddg')),
                '默认等权（待回测）' if d.get('weight_policy')=='S40_EQUAL_INITIAL_PENDING_BACKTEST' else '显式权重' if d else '未计算',
                esc('、'.join(LABELS.get(n,n) for n in d.get('missing_dimensions',[]))) if d else '缺少候选计算结果'])
        dev_content+=table(['候选','综合分','可靠维度','ΔΔG (kcal/mol)','权重','缺失维度'],dev_rows)
    candidate_rows=[]
    for record in records:
        mutations=record.get('mutations');score=record.get('esm_if1') or {};foldx=record.get('foldx') or {}
        disposition='已排除' if record.get('disposition')=='EXCLUDED' else '候选记录'
        validation=record.get('s28_validation')
        if disposition!='已排除' and validation is not None and validation['passed'] is None:disposition='未完成验证'
        explanations=[reason(r.get('code')) for r in record.get('exclusion_reasons') or []]
        if validation is not None and validation['degraded']:explanations.append(reason(validation['reason']))
        mutations_text=', '.join(str(m.get('wt',''))+str(m.get('position',''))+str(m.get('mut','')) for m in mutations or [])
        details='<details><summary>查看突变与依据</summary><p class="mono">'+esc(mutations_text or '无突变记录')+'</p><p>'+esc('；'.join(dict.fromkeys(explanations)) or '尚未形成完整筛选结论')+'</p></details>'
        candidate_rows.append([esc(record.get('id','未命名')),str(len(mutations)) if isinstance(mutations,list) else '未记录',esc(number(score.get('esm_if1_score'),3)),esc(number(foldx.get('ddg_foldx'))),badge(disposition,'danger' if disposition=='已排除' else 'warn')+details])
    candidates=('<p class="subtle">按原始记录顺序展示，共 '+str(len(records))+' 项。ESM-IF1 为序列/结构适配性原始分数，不是综合排名或实验效果。ΔΔG 单位 kcal/mol，负值表示预测更稳定。</p>'+table(['候选','突变数','ESM-IF1','FoldX ΔΔG','当前结论'],candidate_rows)) if records else '<div class="empty">本次没有可展示的设计候选。原始蛋白分析保留在上方；缺少候选不表示已完成设计验证。</div>'
    selection=report.get('engineering_selection') or {}
    if selection:
        computed={r['id']:r for r in selection.get('computed',[])}
        selected=selection.get('top20',[])
        selection_rows=[]
        for item in selection.get('inventory',[]):
            value=computed.get(item['id']) or {}
            label='参考序位 '+str(selected.index(item['id'])+1) if item['id'] in selected else {
                'EXCLUDED':'已排除','UNDETERMINED':'必要结果不完整','RANKABLE':'已评分，未入选'}.get(item['state'],'未评估')
            selection_rows.append([esc(item['id']),esc(number(value.get('score'),3)),esc(label),
                esc('；'.join(reason(code) for code in item.get('exclusion_reasons',[])+item.get('missing',[]))) or '—'])
        candidates+='<h3>综合筛选参考</h3><p class="subtle">按可开发性、稳定性、表位保留和突变负担综合计算。只使用已核验的逐候选复评证据；家族分类尚不完整，安全性及宿主同源检查本期未执行，不代表正式推荐或实验放行。</p>'
        candidates+=table(['候选','目标加权分','参考结果','未入选／缺项原因'],selection_rows)
        if (selection.get('sc10') or {}).get('overall_pass') is False:
            candidates+='<p class="notice">参考首选的可开发性总分低于 0.30，未达到交付阈值；保留 WT 分析，不自动交接候选。</p>'
        elif not selected:
            candidates+='<p class="subtle">当前没有可形成综合参考序位的候选。缺少必要总分或验证时不补分、不生成排名。</p>'
    validations=data.get('n12_validation') or []
    revision=workflow.get('expert_revision')
    native_parts=None
    if revision or native_results:
        from .native_report import build
        native_parts=build(data,workflow,native_results)
        if revision:candidates=native_parts['candidates']
        candidates+=native_parts['permissions']
        overview+=native_parts['overview'];epitope_content+=native_parts['epitope']
        dev_content+=native_parts['developability']
    if validations:
        validation_rows=[]
        for index,validation in enumerate(validations,1):
            validation_rows.append([str(index),str(len(validation['records'])),str(len(validation['review_pool'])),
                str(len(validation['rejected'])),str(len(validation['unavailable']))])
        candidates='<h3>逐轮候选验证</h3><p class="subtle">逐条核对序列评分和适用的结构检查。预测失败时保留评分通过者并注明缺结构；未验证项不当作淘汰。进入复核池仍需后续筛选。</p>'+table(
            ['轮次','候选数','进入复核池','已淘汰','未完成验证'],validation_rows)+candidates
    dna_rows=[]
    for item in data.get('dna') or []:
        d=item.get('dna') or {}
        sequence=d.get('optimized_dna') or d.get('initial_dna')
        dna_rows.append([esc(item.get('subject')),esc(item.get('source_status') or '未完成'),
            esc(reason(item['reason'])) if item.get('reason') else '已完成计算优化',
            '<details><summary>查看 DNA</summary><pre>'+esc(sequence)+'</pre></details>' if sequence else '无可用 DNA'])
    if dna_rows:
        candidates+='<h3>表达序列</h3><p>按明确提供的表达宿主生成。优化失败时展示未优化回退及原因；本结果不代表实验放行。</p>'+table(['候选','状态','说明','DNA'],dna_rows)
    consensus=(data.get('wt_reference') or {}).get('consensus_ranking')
    if consensus and consensus.get('records'):
        labels={'high_consensus':'高共识','medium_consensus':'中共识','low_consensus':'低共识','single_engine':'单引擎','no_consensus':'无共识'}
        consensus_counts={k:sum(r.get('consensus_rank')==k for r in consensus['records']) for k in labels}
        dev_content+='<h3>原蛋白稳定性扫描共识</h3><p>比较两个引擎各自比较集中的排名，不平均能量值。WT 自身替换不列作突变建议；规则未定义或覆盖不足时保持未评估。</p>'
        dev_content+=table(['共识','突变数'],[[labels[k],str(v)] for k,v in consensus_counts.items()]+[['未形成共识',str(sum(r.get('consensus_rank') is None for r in consensus['records']))]])
        mutation_rows=[]
        for row in consensus['records']:
            energy=row.get('ddg') or {}
            mutation_rows.append([esc(str(row.get('wt',''))+str(row.get('position',''))+str(row.get('mut',''))),
                number(energy.get('foldx'),6),number(energy.get('thermompnn'),6),
                esc(labels.get(row.get('consensus_rank'),'未评估'))])
        dev_content+='<details><summary>逐突变稳定性与共识</summary>'+table(
            ['突变','FoldX ΔΔG（kcal/mol）','ThermoMPNN ΔΔG（kcal/mol）','共识'],mutation_rows)+'</details>'
    limitations=['本报告展示计算预测结果。',
        '候选按原始样本次序展示；各项数值的计算方法与缺项见对应说明。',
        '未提供表达宿主时，不以免疫宿主代替；不据此生成密码子优化结论。']
    if report.get('m1_test'):
        selected=[r for r in report['m1_test'].get('records',[]) if r.get('selected_for_recomputation')]
        limitations.append(f'本次仅有 {len(selected)} 个代表候选进入后续复评，其余候选未完成同等检查；被排除者的复评仅供诊断。')
    for name,row in failed:limitations.append(LABELS.get(name,name)+'：'+reason(row.get('reason_code') or row.get('error_code')))
    limits='<ul class="limitations">'+''.join('<li>'+esc(t)+'</li>' for t in limitations)+'</ul>'
    states=[]
    for name,assessment in assessments.items():
        state=assessment.get('execution_state') or ('succeeded' if assessment.get('executed') else 'not_executed')
        states.append([esc(LABELS.get(name,name)),esc(STATES.get(state,'状态待核实'))])
    appendix='<p>本报告汇总本次计算获得的科学结果。预测结果尚需实验验证；未评估项不按零分或通过处理。</p>'+table(['分析项目','计算完成情况'],states)
    if native_parts:appendix=native_parts['appendix']+appendix
    title='抗原设计科学报告'
    stats=[(f'{len(seq)} aa' if seq else '未提供','输入蛋白'),(subject.get('host_species') or '未提供','免疫宿主'),(str(len(records)) if report else '无记录','候选记录'),('计算预测','结果来源')]
    if revision and native_parts:stats[2]=(str(native_parts['unique_count']),'唯一候选')
    elif fact.get('reason_code')=='NO_DESIGNABLE_POSITIONS':stats[2]=('0','生成候选')
    takeaways=''
    if revision:
        from .native_report import unique_candidates, geometry_status
        unique_records=unique_candidates(revision.get('formal_records',[]))
        geometry_failed=sum(geometry_status(r)=='FAIL' for r in unique_records)
        geometry_unknown=sum(geometry_status(r) not in ('PASS','FAIL','NOT_APPLICABLE') for r in unique_records)
        geometry_passed=sum(geometry_status(r)=='PASS' for r in unique_records)
        unassessed=sum((r.get('l4') or {}).get('check_status') not in ('PASS','FAIL','NOT_APPLICABLE') for r in unique_records)
        insights=[('候选设计',f"{len(unique_records)} 条唯一候选，编号保留原样本次序。"),
                  ('结构保护',f"局部几何检查：{geometry_passed} 条通过，{geometry_failed} 条未通过，{geometry_unknown} 条未评估。"),
                  ('表位保留',f"{unassessed} 条候选的预测表位保留尚未完成评价。")]
        takeaways='<div class="takeaways">'+''.join('<div class="takeaway"><strong>'+esc(k)+'</strong><p>'+esc(v)+'</p></div>' for k,v in insights)+'</div>'
    identity = ''
    parent = workflow.get('parent_at_assembly') or {}
    if parent.get('job_id') and parent.get('created_at'):
        from .object_storage import report_name, StorageError
        try:
            name = report_name(parent['job_id'], parent['created_at'])
        except StorageError:
            identity = '<p class="note">报告身份信息不完整，请核对来源附件。</p>'
        else:
            identity = '<p class="note">报告编号：' + esc(name) + ' · 提交时间（北京时间）：' + esc(name[:4]+'-'+name[4:6]+'-'+name[6:8]+' '+name[9:11]+':'+name[11:13]+':'+name[13:15]) + '。本报告仅对应此任务，下载时间不代表重新计算。</p>'
    return ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:; base-uri \'none\'; form-action \'none\'">'
        '<title>'+title+'</title><style>'+CSS+'</style></head><body><header><div class="bar"><div class="brand"><b>ANTIGEN</b> / 抗原设计</div><div class="edition">科学结果报告 · V'+VERSION+'</div></div></header><main>'
        +('<div class="notice">'+esc(preview_note)+'</div>' if preview_note else '')
        +'<div class="hero"><p class="kicker">SEQUENCE · EVIDENCE · DESIGN</p><h1>'+title+'</h1><p class="lead">'+esc(headline)+'</p><p class="note">'+esc(summary)+'</p>'+identity+'</div>'
        +'<div class="stats">'+''.join('<div class="stat"><strong>'+esc(v)+'</strong><span>'+esc(k)+'</span></div>' for v,k in stats)+'</div>'
        +takeaways+'<div class="report-layout"><nav aria-label="报告目录">'+''.join(f'<a href="#s{i}">0{n} {t}</a>' for n,(i,t) in enumerate(((4,'候选结果'),(1,'分析对象'),(2,'表位与糖基化'),(3,'可开发性'),(5,'结果局限'),(6,'方法说明')),1))+'</nav><div class="report-body">'
        +section(4,'候选结果与比较',candidates).replace('>04</span>','>01</span>')
        +section(1,'分析对象与结构概况',overview).replace('>01</span>','>02</span>')
        +section(2,'表位与糖基化',epitope_content).replace('>02</span>','>03</span>')
        +section(3,'可开发性评估',dev_content).replace('>03</span>','>04</span>')
        +section(5,'结果局限与适用范围',limits)+section(6,'方法与阅读说明',appendix)
        +'</div></div><footer class="footer"><span>抗原设计 · 科学报告 V'+VERSION+'</span><span>可离线阅读 · 可使用浏览器打印 / 保存为 PDF</span></footer></main></body></html>').encode('utf-8')



def from_workflow_package(raw, *, native_results=None):
    """Read bounded known members only; never extract paths or rewrite the archive."""
    def member(archive,name,limit):
        info=archive.getinfo(name)
        if info.file_size>limit:raise ValueError('Report member exceeds the allowed size')
        return archive.read(name)
    with zipfile.ZipFile(io.BytesIO(raw)) as outer:
        workflow=json.loads(member(outer,'workflow.json',32*1024**2)) if 'workflow.json' in outer.namelist() else {}
        if 'local-delivery.zip' not in outer.namelist():return None
        nested=member(outer,'local-delivery.zip',32*1024**2)
        with zipfile.ZipFile(io.BytesIO(nested)) as delivery:
            if 'data.json' not in delivery.namelist():return None
            data=json.loads(member(delivery,'data.json',16*1024**2))
    return render(data,workflow,native_results=native_results)
