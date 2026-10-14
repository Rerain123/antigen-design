"""Summarize retained cancellation evidence; no runtime calls or scientific compute."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/n14-scope-audit-20260928'
source = OUT / 'stop-confirmation.json'
data = json.loads(source.read_bytes())
nodes = data['execution']['nodes']
records = nodes['validation']['fact']['records']
counts = [len(v['mutations']) for v in data['before']['request']['variants']]
rows = []
for record in records:
    thresholds = record['mutation_burden']['engineering_thresholds']
    rows.append(dict(sample_number=record['sample_number'],
                     validation_passed=record['passed'],
                     burden_exceeded=record['burden_exceeded'],
                     objective=thresholds['objective'],
                     count_limit=thresholds['limits']['count'],
                     count_exceeded=thresholds['per_dimension_exceeded']['count'],
                     known_exceeded=thresholds['known_exceeded']))
assert len(rows) == len(counts) == 24
assert all(r['count_exceeded'] and r['burden_exceeded'] for r in rows)
confirmation = nodes['design']['confirmation']
result = dict(
    source=str(source.relative_to(ROOT)).replace('\\', '/'),
    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    checked_at=data['checked_at'],
    parent_state=data['parent']['state'], child_state=data['child']['state'],
    tree_stopped=data['execution']['tree_stopped'],
    generator='N11 / ProteinMPNN / C15',
    generator_job_id=nodes['design']['job_id'],
    permissions={k:confirmation[k] for k in ('fixed_count','restricted_count','open_count')},
    mutation_counts=counts, min_count=min(counts), max_count=max(counts),
    sequence_length=len(data['before']['request']['protein_sequence']),
    validation=rows,
    finding='All 24 exceed the existing general count limit; N12 passed is not final eligibility. SOP step19b scores before step20 burden hard filter.',
    expert_sources=['ToolSpec_C15_ProteinMPNN_v10.5 sections 2-3',
                    'AgentA_SOP_v10.5_20260902 S-27, S-28, T-01 steps19b-20',
                    'ToolSpec_C35_FoldX_v10.5 section 2c'],
    external_sources=[
        'https://foldxsuite.crg.eu/parameter/mutant-file',
        'https://foldxsuite.crg.eu/command/BuildModel',
        'https://academic.oup.com/bioinformatics/article/41/2/btaf064/8003679'],
    applicability='Multi-mutation input support does not establish predictive validity for this mutation burden; the 2025 FoldX paper describes a rigid backbone and excluded multiple mutations from its curated force-field benchmark.',
    disposition='Stopped, evidence retained. No restart, threshold changes, generator changes, or scientific qualification.')
(OUT / 'audit-summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({k:result[k] for k in ('parent_state','child_state','tree_stopped','min_count','max_count','permissions')}, ensure_ascii=False))
