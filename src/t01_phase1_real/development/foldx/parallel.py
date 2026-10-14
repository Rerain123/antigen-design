"""Temporary candidate-level execution, not a claim of serial numerical equivalence."""
import concurrent.futures
import json
import threading
import time

try:
    from .scan_batches import seal, unpack, model_names
except ImportError:
    from scan_batches import seal, unpack, model_names

WORKERS = 2
MARKER = 'N14_PARALLEL_TEMPORARY_EXPERT_REVIEW_REQUIRED'
NOTICE = ('N14 临时工程调整：按候选独立进程并行，复用同一 RepairPDB 基座，每候选仍执行 5 轮。'
          '原生小样例已观察到与整批串行的数值及结构差异，不宣称结果逐值等价；用户同意先行采用，待专家确认。')


def command(directory):
    return ['/app/foldx_20270131', '--command=BuildModel', '--pdb=target_Repair.pdb',
            '--pdb-dir=/out/repair', '--mutant-file=individual_list.txt', '--numberOfRuns=5',
            '--output-dir=/out/' + directory]


def plan(payload):
    variants = [v for v in payload['variants'] if not v['mapping_failed']]
    if not variants or len(variants) != len(payload['variant_lines']):
        raise ValueError('Parallel BuildModel mapping/list count differs')
    return dict(marker=MARKER, notice=NOTICE, workers=WORKERS, repair_reused=True,
                serial_equivalence=False, expert_signoff=None,
                batches=[dict(index=i, variant_id=v['variant_id'], mutation_line=line)
                         for i, (v, line) in enumerate(zip(variants, payload['variant_lines']), 1)])


def execute(out, payload, run):
    planned = plan(payload)
    (out / 'buildmodel/batches').mkdir(parents=True)
    (out / 'buildmodel-plan.json').write_text(json.dumps(planned, ensure_ascii=False), encoding='utf8')
    completed = {}; active = set(); lock = threading.Lock(); failed = threading.Event()

    def progress():
        temporary = out / 'buildmodel-progress.json.tmp'
        temporary.write_text(json.dumps(dict(marker=MARKER, total=len(planned['batches']),
            active=sorted(active), completed=[completed[k] for k in sorted(completed)])), encoding='utf8')
        temporary.replace(out / 'buildmodel-progress.json')

    def one(batch):
        if failed.is_set():
            return
        index = batch['index']; directory = f'buildmodel/batches/{index:04d}'
        folder = out / directory; folder.mkdir()
        (folder / 'individual_list.txt').write_text(batch['mutation_line'] + '\n', encoding='utf8')
        with lock:
            active.add(index); progress()
        started = time.monotonic()
        try:
            argv = command(directory)
            # No new session/process group: the resident supervisor retains ownership.
            result = run(argv, str(folder), directory + '/stdout.txt')
            record = dict(batch, argv=argv, exit_code=result.returncode,
                          seconds=time.monotonic() - started, archive=directory + '.zip')
            if result.returncode:
                raise RuntimeError('FoldX candidate failed: ' + str(index))
            record.update(seal(folder, out / record['archive']))
            with lock:
                completed[index] = record; active.remove(index); progress()
            print('N14 FoldX candidate', index, '/', len(planned['batches']), 'completed', flush=True)
        except BaseException:
            failed.set()
            raise

    progress()
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(one, b) for b in planned['batches']]
        for future in concurrent.futures.as_completed(futures):
            future.result()
    if len(completed) != len(planned['batches']):
        raise RuntimeError('Incomplete parallel BuildModel batch')
    return [completed[k] for k in sorted(completed)]


def verified_batches(payload, runtime, files):
    """Yield original raw members with explicit global-candidate/local-index mapping."""
    from ...common import decode, ensure, sha
    planned = plan(payload); records = runtime['buildmodel_parallel']
    ensure(decode(files['output/buildmodel-plan.json']) == planned and
           isinstance(records, list) and len(records) == len(planned['batches']),
           'OUTPUT_INVALID', 'Parallel BuildModel plan/count differs')
    ensure(decode(files['output/buildmodel-progress.json']) == dict(marker=MARKER,
           total=len(records), active=[], completed=records), 'OUTPUT_INVALID', 'Parallel progress incomplete')
    ensure({n for n in files if n.startswith('output/buildmodel/')} ==
           {f'output/buildmodel/batches/{i:04d}.zip' for i in range(1, len(records) + 1)},
           'OUTPUT_INVALID', 'Parallel archive coverage differs')
    for batch, record in zip(planned['batches'], records):
        directory = f"buildmodel/batches/{batch['index']:04d}"; name = 'output/' + directory + '.zip'
        raw = files[name]
        ensure(all(record.get(k) == v for k, v in batch.items()) and record.get('exit_code') == 0 and
               record.get('argv') == command(directory) and record.get('archive') == directory + '.zip' and
               record.get('sha256') == sha(raw) and record.get('size_bytes') == len(raw),
               'OUTPUT_INVALID', 'Parallel candidate identity/command/hash differs')
        members = unpack(raw)
        ensure({n for n in members if n.endswith('.pdb')}==set(model_names(1)),
               'OUTPUT_INVALID','Parallel native PDB coverage differs')
        ensure(len(members) == record.get('members') and sum(map(len, members.values())) == record.get('expanded_bytes') and
               members.get('individual_list.txt') == (batch['mutation_line'] + '\n').encode(),
               'OUTPUT_INVALID', 'Parallel candidate members/mutations differ')
        yield batch, name, members
