"""Canonical MCP tool and scenario catalogs for T-01 v10.

The names in ``STEP_TOOLS`` mirror the reviewed mapping document.  Keeping the
catalog in one module lets tests prevent accidental Dify/MCP name drift.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolSpec:
    step_id: str
    group: str
    description: str


STEP_TOOLS: dict[str, ToolSpec] = {
    # Start and T-layer routing.
    "t01.validate_request": ToolSpec("START", "t01", "Validate collected T-01 input without scientific calculation."),
    "t01.evaluate_length_guard": ToolSpec("G-LENGTH", "t01", "Return HALT, WARNING, or PASS from sequence length and epitope mode."),
    "t01.route_context_scores": ToolSpec("G0B", "t01", "Route context injection as NONE, HIGH, or NON_HIGH."),
    "t01.inject_context_scores": ToolSpec("0b", "t01", "Validate and unpack injected sequence/structure context."),
    "t01.prepare_permission_inputs": ToolSpec("step11", "t01", "Prepare fixed/degraded/epitope inputs for permissions."),
    "t01.evaluate_mutable_length": ToolSpec("step15", "t01", "Evaluate mutable-length routing values."),
    "t01.build_evidence_bundle": ToolSpec("step16", "t01", "Build the required six-key evidence bundle."),
    # Phase 0.
    "structure.fetch": ToolSpec("S-07", "phase0", "Fetch an existing structure or return no_structure."),
    "t01.route_existing_structure": ToolSpec("EX", "phase0", "Route existing structure versus prediction."),
    "structure.predict": ToolSpec("S-08", "phase0", "Predict a structure (mock only in this service)."),
    "structure.assess_quality": ToolSpec("S-09", "phase0", "Classify structure confidence as high, medium, or low."),
    "topology.predict": ToolSpec("S-04", "phase0", "Predict membrane topology (mock only)."),
    "t01.route_rsa": ToolSpec("G-RSA", "phase0", "Skip RSA when structure confidence is low."),
    "structure.compute_rsa": ToolSpec("S-11", "phase0", "Compute RSA with sequence-alignment validation (mock only)."),
    "t01.route_pathogen_type": ToolSpec("G-BACTERIA", "phase0", "Run S-06 only when pathogen_type equals bacteria."),
    "localization.predict_bacteria": ToolSpec("S-06", "phase0", "Predict bacterial localization (mock only)."),
    # Phase 1.
    "epitope.query_iedb_prior": ToolSpec("S-03", "phase1", "Query prior IEDB evidence (mock only)."),
    "epitope.predict_bcell": ToolSpec("S-17", "phase1", "Predict B-cell epitopes (mock only)."),
    "epitope.predict_tcell": ToolSpec("S-18", "phase1", "Predict T-cell presentation (mock only)."),
    "epitope.synthesize_maps": ToolSpec("S-19", "phase1", "Synthesize the three required epitope maps."),
    "glyco.scan": ToolSpec("S-12", "phase1", "Scan glycosylation context (mock only)."),
    "safety.assess_triple": ToolSpec("S-23", "phase1", "Assess allergenicity, toxicity, and host similarity (mock only)."),
    # Phase 2.
    "conservation.collect_homologs": ToolSpec("S-13", "phase2", "Collect homologs and confidence (mock only)."),
    "conservation.compute": ToolSpec("S-14", "phase2", "Compute per-position conservation (mock only)."),
    "conservation.extract_regions": ToolSpec("S-15", "phase2", "Extract conserved regions."),
    "conservation.analyze_within_type": ToolSpec("R-11", "phase2", "Run within-type degradation analysis."),
    "domain.identify": ToolSpec("S-16", "phase2", "Identify domains and four-component core_map (mock only)."),
    # Phase 3.
    "developability.predict_solubility": ToolSpec("S-36", "phase3", "Predict solubility (mock only)."),
    "developability.compute_expressibility": ToolSpec("S-36a", "phase3", "Compute expressibility features (mock only)."),
    "developability.predict_aggregation": ToolSpec("S-37", "phase3", "Predict aggregation propensity (mock only)."),
    "developability.predict_ph_stability": ToolSpec("S-38", "phase3", "Predict pH stability (mock only)."),
    "developability.assess_tag_exposure": ToolSpec("S-39", "phase3", "Assess tag exposure."),
    "developability.assess": ToolSpec("S-40", "phase3", "Assemble baseline/coarse/final developability assessment."),
    "t01.evaluate_design_applicability": ToolSpec("R-57", "phase3", "Apply membrane and low-confidence design confirmation gates."),
    # Branch 4.
    "t01.route_stability_rescue": ToolSpec("B4", "branch4", "Run rescue only for poor non-membrane baseline."),
    "stability.scan_mutations": ToolSpec("S-31", "branch4", "Scan mutations (mock only)."),
    "stability.screen_rescue_top3": ToolSpec("B4-TOP3", "branch4", "Coarsely screen three rescue candidates (mock only)."),
    # Phase 4.
    "design.generate_mutations": ToolSpec("S-27", "phase4", "Generate permission-constrained mutations (mock only)."),
    "design.validate": ToolSpec("S-28", "phase4", "Validate generated designs (mock only)."),
    "t01.evaluate_design_retry": ToolSpec("S-28-RETRY", "phase4", "Route initial/48/64 design attempts."),
    "design.check_conservative_mutations": ToolSpec("S-29", "phase4", "Exclude conservative-region violations."),
    # Phase 5.
    "variant.reassess_developability": ToolSpec("step19", "phase5", "Batch-reassess variants (mock only)."),
    "epitope.validate_presentation": ToolSpec("step19-L1-L4", "phase5", "Apply four-layer epitope preservation validation."),
    "t01.select_stability_score_pool": ToolSpec("step19b", "phase5", "Select stability score pool under cost gates."),
    "stability.score_variants": ToolSpec("S-31-variant", "phase5", "Score variant stability (mock only)."),
    "ranking.rank_variants": ToolSpec("step20", "phase5", "Apply hard filters, Pareto ranking, diversity, and SC-10."),
    # Phase 6.
    "sequence.optimize_codons": ToolSpec("S-30", "phase6", "Optimize codons only when expression host is supplied (mock only)."),
    "t01.evaluate_md_gate": ToolSpec("G-MD", "phase6", "Run MD only when every documented condition passes."),
    "dynamics.run_md_validation": ToolSpec("S-32", "phase6", "Run top-three MD validation (mock only)."),
    # Phase 7.
    "output.assemble_candidate_json": ToolSpec("S-42", "phase7", "Assemble the minimum Candidate JSON contract."),
    "t01.route_visualization": ToolSpec("VIS", "phase7", "Route optional visualization and explanation."),
    "output.render_comparison_report": ToolSpec("C29", "phase7", "Render a mock comparison report."),
    "output.prepare_explanation": ToolSpec("C30", "phase7", "Prepare a factual backend summary for LLM explanation."),
    "t01.route_handoff": ToolSpec("step26", "phase7", "Route variant, design-skipped WT, or failure-report WT handoff."),
    "handoff.assemble_agent_c": ToolSpec("S-43", "phase7", "Assemble a mock Agent-C handoff package."),
    "handoff.deliver_agent_c": ToolSpec("S-44", "phase7", "Mock delivery because the target interface is undefined."),
}


JOB_TOOLS = {
    "jobs.get_status",
    "jobs.get_result",
    "jobs.cancel",
}


CONTROL_TOOLS = {
    "mock.configure_run",
    "mock.configure_run_from_json",
    "mock.get_run",
    "mock.list_scenarios",
}


SCENARIOS: dict[str, tuple[str, str]] = {
    "MOCK-HAPPY-PATH": ("全部通过", "best候选交接"),
    "MOCK-SHORT-MHC-HALT": ("小于9aa且需MHC", "长度守卫停止"),
    "MOCK-SHORT-WARNING": ("9至29aa", "WARNING后继续"),
    "MOCK-CONTEXT-HIGH": ("高置信注入", "S-16后step15"),
    "MOCK-CONTEXT-NONHIGH": ("非高置信注入", "S-16后step12"),
    "MOCK-NO-STRUCTURE": ("S-07无结构", "进入S-08"),
    "MOCK-LOW-STRUCTURE": ("S-09 low", "S-11跳过；R-57等待或跳过"),
    "MOCK-BACTERIA": ("bacteria", "执行S-06并解析flag"),
    "MOCK-MEMBRANE-SKIP": ("膜且未确认", "WT+design_skipped"),
    "MOCK-MEMBRANE-CONFIRMED": ("膜且确认", "继续设计，后续结构步骤按规则降级"),
    "MOCK-POOR-RESCUE-SUCCESS": ("poor且非膜", "分支4成功后继续"),
    "MOCK-POOR-RESCUE-FAIL": ("poor且非膜", "分支4失败但按原图继续到EBB"),
    "MOCK-DESIGN-RETRY-48": ("首轮全淘汰、48轮通过", "一次重试后继续"),
    "MOCK-DESIGN-RETRY-64": ("首轮与48全淘汰、64通过", "两次重试后继续"),
    "MOCK-DESIGN-ALL-REJECTED": ("三轮全淘汰", "WT+failure_report"),
    "MOCK-EPITOPE-STRUCTURAL-FAIL": ("L2/L3 structural失败", "epitope_violation硬排除"),
    "MOCK-EPITOPE-PREDICTION-FAIL": ("L4失败", "soft_penalty降权"),
    "MOCK-VARIANT-SAFETY-FAIL": ("变体安全非PASS", "safety_excluded硬排除"),
    "MOCK-19B-SKIPPED": ("low或膜或空池", "不执行变体FoldX"),
    "MOCK-SC10-WARNING": ("best.overall小于0.30", "WARNING并按待确认规则降级"),
    "MOCK-MD-RUN": ("MD门控全部满足", "top3执行S-32"),
    "MOCK-MD-SKIP": ("任一MD条件不满足", "直接阶段7"),
    "MOCK-TOOL-TIMEOUT": ("任一工具超时", "标准TIMEOUT错误与重试策略"),
    "MOCK-OUTPUT-MISSING": ("exit_code=0但无输出", "OUTPUT_MISSING，不得视为成功"),
    "MOCK-OUTPUT-INVALID": ("文件存在但解析失败", "OUTPUT_INVALID"),
}


FAULT_SCENARIOS = {
    "MOCK-TOOL-TIMEOUT",
    "MOCK-OUTPUT-MISSING",
    "MOCK-OUTPUT-INVALID",
}

FAULT_TOOL = "structure.fetch"
