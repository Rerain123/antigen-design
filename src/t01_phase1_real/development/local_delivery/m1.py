"""M1 P3 delivery of verified new scans and excluded-candidate debug results."""
from ...common import decode, encode, ensure


def scan_facts(rt, db, body, files, values):
    report = values.get('variant_report', {}).get('report', {})
    if not report.get('m1_test'):
        return
    reference = values.get('wt_reference', {}).get('reference')
    ensure(reference is not None, 'OUTPUT_INVALID', 'M1 delivery requires verified WT scans')
    request = decode(files['input/variant_report-request.json'])
    audit = rt._job(db, request['upstream']['design_audit']['job_id'])
    audit_request = decode(rt._request_bytes(audit))
    n11 = rt._job(db, audit_request['upstream']['n11']['job_id'])
    constraints = decode(rt._request_bytes(n11))['constraints']
    protected = sorted(set(constraints['fixed_positions']) |
                       {r['position'] for r in constraints['restricted_positions']})
    ref_request = decode(files['input/wt_reference-request.json'])
    final = rt._job(db, body['upstream']['variant_report']['job_id'])
    facts = {}
    workflow=decode(files['input/workflow-n17.json']) if 'input/workflow-n17.json' in files else None
    for name in ('foldx', 'thermompnn'):
        src = ref_request['upstream'][name]
        if workflow and workflow['engines'][name]['state']!='succeeded':
            facts[name]=workflow['engines'][name]
            continue
        if src is None and not constraints['open_positions']:
            facts[name] = dict(source=None, actual_calculation='NOT_EXECUTED',
                reason_code='NO_COVERED_EXPLICIT_OPEN_SCAN_POSITION', native_prediction_count=0,
                displayed_positions=[], displayed_prediction_count=0, raw_artifacts=[])
            continue
        ensure(src is not None, 'OUTPUT_INVALID', 'M1 P3 requires both applicable monomer engines')
        job = rt._job(db, src['job_id'])
        value = rt.result(job['job_id'])
        req = decode(rt._request_bytes(job))
        ensure(job['run_id'] == final['run_id'] and job['state'] == 'succeeded'
               and job['started_at'] >= final['finished_at'], 'OUTPUT_INVALID', 'M1 P3 requires new same-run scans after P2 final')
        positions = req['scan_positions']
        exclusions = req['fixed_positions'] if name == 'foldx' else req['excluded_positions']
        ensure(positions and set(positions) <= set(constraints['open_positions'])
               and not set(positions).intersection(protected) and set(protected) <= set(exclusions),
               'OUTPUT_INVALID', 'M1 scan violates explicit P1 permissions')
        engine = reference['engines'][name]
        ensure(engine['effective_positions'] == positions and engine['records'],
               'OUTPUT_INVALID', 'M1 scan returned an empty or different display scope')
        ensure(value['execution']['stopped_confirmed'] is True and
               value['execution'].get('resident_observation', {}).get('network_restriction') == 'seccomp-local-sockets-only-v1',
               'OUTPUT_INVALID', 'M1 scan must stop cleanly offline')
        native_count = len(value['ddg_results']) if name == 'foldx' else value['scan']['native_prediction_count']
        facts[name] = dict(source=src, request=req, execution=value['execution'],
            started_at=job['started_at'], finished_at=job['finished_at'],
            actual_calculation='SELECTED_POSITIONSCAN' if name == 'foldx' else 'FULL_MONOMER_SSM',
            native_prediction_count=native_count, displayed_positions=positions,
            displayed_prediction_count=len(engine['records']), raw_artifacts=value['raw_artifacts'],
            method_summary=value['method_summary'])
    if not workflow or all(e['state']=='succeeded' for e in workflow['engines'].values()):
        ensure(facts['foldx']['displayed_positions'] == facts['thermompnn']['displayed_positions'],
               'OUTPUT_INVALID', 'M1 engine display scopes differ')
    files['input/m1-p3-scans.json'] = encode(dict(
        verified_scan_jobs=sum(r['source'] is not None for r in facts.values()), assembly_scan_invocations=0, engines=facts,
        explicit_constraints=constraints, excluded_positions=protected,
        scientific_permissions_inferred=False, full_scientific_scan=False,
        combined_ddg=None, consensus_ranking=None,
        authority='AgentA_SOP_v10.5_20260902 S-31 / T-01 step22; C35/C43; M1 finite engineering scope'))


def extend(data, files):
    report = data.get('variant_report') or {}
    if not report.get('m1_test'):
        return
    ensure('input/m1-p3-scans.json' in files, 'OUTPUT_INVALID', 'M1 P3 scan receipts missing')
    rows = report['records']
    all_excluded = bool(rows) and all(r['disposition'] == 'EXCLUDED' for r in rows)
    ensure((all_excluded == (report['outcome'] == 'ALL_EXCLUDED'))
           and not report['ranked_candidates'] and not report['pareto_front'] and report['best_candidate'] is None,
           'OUTPUT_INVALID', 'Unsigned M1 candidates cannot become formal selections')
    if data['dna']:
        ensure('input/workflow-n17.json' in files and not all_excluded and
            all(r.get('scientific_pass') is None for r in data['dna']),
            'OUTPUT_INVALID','Only verified engineering workflow DNA can be delivered')
        data.update(n16=dict(state='ENGINEERING_RESULTS',reason_code=None,dna=data['dna'],
            expression_host=data['subject']['expression_host'],expression_host_inferred_from_species=False),
            n17_execution=decode(files['input/workflow-n17.json']),scientific_release_gate='CLOSED',usable_for_pipeline=False,
            agent_c_preview=dict(deliverable=False,payload=None,reason_code='NO_QUALIFIED_CANDIDATE',sent=False))
        return
    data.update(n16=dict(state='SKIPPED', reason_code='NO_QUALIFIED_CANDIDATE', dna=None,
        expression_host=data['subject']['expression_host'], expression_host_inferred_from_species=False,
        model_invocations=0, source=data['source_receipts']['variant_report']),
        n17_execution=decode(files['input/m1-p3-scans.json']),
        scientific_release_gate='CLOSED', usable_for_pipeline=False,
        agent_c_preview=dict(deliverable=False, payload=None, reason_code='ALL_CANDIDATES_EXCLUDED' if all_excluded else 'NO_QUALIFIED_CANDIDATE',
            missing_conditions=data['missing_conditions'], sent=False))
    data['missing_conditions'] = [r for r in data['missing_conditions']
                                  if r != dict(source='N16', code='DNA_NOT_PROVIDED')]
    data['missing_conditions'].append(dict(source='N16', code='NO_QUALIFIED_CANDIDATE'))


def readable(data):
    if 'n16' not in data:
        return []
    rows = data['variant_report']['m1_test']['records']
    all_excluded=data['agent_c_preview']['reason_code']=='ALL_CANDIDATES_EXCLUDED'
    lines = ['', '## P2 调试排序与重评', '',
        ('全部候选已淘汰；' if all_excluded else '候选尚无正式资格；')+'下列顺序只用于调试。未选中条目没有执行结构/变体重评，缺失不补零。', '',
        '| 候选 | 调试序号 | ESM-IF1 | 重评 | FoldX ΔΔG |', '|---|---|---|---|---|']
    for r in rows:
        score = (r['esm_if1'] or {}).get('esm_if1_score')
        ddg = (r['foldx'] or {}).get('ddg_foldx')
        lines.append(f"| {r['candidate_id']} | {r['test_rank']} | {score} | {r['recomputation_state']} | {ddg} |")
    lines += ['', '## N16 条件结果', '',
        '逐候选工程 DNA 及失败/回退见机器报告；正式科学资格未开放。' if data['dna'] else
        'SKIPPED / NO_QUALIFIED_CANDIDATE；dna=null。宿主物种不作为表达宿主。',
        '', '## N17 本轮 WT 扫描', '', '有限内部工程范围；不代表完整科学扫描。两引擎保留原始值，不跨引擎平均。', '',
        '| 引擎 | 实际计算 | 原生条数 | 展示位点 | 展示条数 |', '|---|---|---|---|---|']
    for name, r in data['n17_execution']['engines'].items():
        lines.append(f"| {name} | {r['actual_calculation']} | {r['native_prediction_count']} | {r['displayed_positions']} | {r['displayed_prediction_count']} |")
        if r.get('reason_code'):lines.append(f"\n{name}: {r['reason_code']}；失败或跳过不计作扫描完成。\n")
    lines += ['', 'WT 结构沿用 P1 可追溯工程派生输入；N08/N09 缺项没有解释为无保护位点。',
        'RSA、CamSol、标签暴露及完整科学资格仍缺失；暂定口径、逐候选缺项和原始引用见机器报告。',
        '', '## Agent C 本地预览', '', '不可交接：'+('全部候选淘汰' if all_excluded else '无正式合格候选')+'；正式载荷为空，未发送。']
    return lines
