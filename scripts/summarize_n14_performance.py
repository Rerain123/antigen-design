"""Summarize measured N14 evidence; no runtime submission or scientific decision."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/n14-performance-20260928'


def table(path):
    header = None
    rows = []
    for line in path.read_text().splitlines():
        if line.startswith('Pdb\t'):
            header = line.split('\t')
        elif header and line.strip():
            values = line.split('\t')
            assert len(values) == len(header)
            rows.append(dict(zip(header, values)))
    return rows


def main():
    stop = json.loads((OUT / 'stop-confirmation.json').read_bytes())
    probe = OUT / 'parallel-native-probe-r03'
    measured = json.loads((probe / 'comparison.json').read_bytes())
    serial = table(probe / 'serial/Average_target_Repair.fxout')
    comparisons = []
    for index, expected in enumerate(serial):
        actual = table(probe / f'parallel-{index}/Average_target_Repair.fxout')[0]
        comparisons.append(dict(candidate_index=index + 1,
            serial_mean=float(expected['total energy']), parallel_mean=float(actual['total energy']),
            serial_std=float(expected['SD']), parallel_std=float(actual['SD'])))
    inputs = [OUT / 'stop-confirmation.json', probe / 'comparison.json',
              OUT / 'streaming-tests.junit.xml']
    value = dict(
        parent_state=stop['parent']['state'], child_state=stop['child']['state'],
        tree_stopped=stop['execution']['tree_stopped'],
        mutation_counts=[len(v['mutations']) for v in stop['before']['request']['variants']],
        native_budget_seconds=stop['before']['request']['timeout_seconds'],
        native_probe_scope='9-aa engineering fixture, not PCV2 throughput or scientific acceptance',
        serial_seconds=measured['serial_seconds'], parallel_seconds=measured['parallel_seconds'],
        serial_repeat=measured['serial-repeat'], screen_false=measured['serial-quiet'],
        mean_std_comparison=comparisons, parallel_equivalence=measured['status'],
        decision='Parallel production implementation awaits user decision on observed numerical differences',
        local_change='Stream native diagnostics to files; no native command or process-group change',
        deployed=False, restarted=False,
        caveats=['No verified explanation of native batch-order numerical dependence',
                 'No evidence that two-way parallelism completes PCV2 within 4-hour tool budget',
                 'No reduction of candidates, mutations, five runs, or scientific thresholds'],
        evidence_sha256={p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})
    (OUT / 'diagnosis.json').write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
