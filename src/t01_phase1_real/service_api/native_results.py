"""Read-only presentation/export of registered native outputs, never a new run.

The caller supplies Service.report's verified workflow package. Historical package
bytes and scientific decisions remain unchanged. Batch-backed MHC rows are read
from their registered producers, rather than interpreting hits=None as no result.
"""
import io
import re
import zipfile
from collections import Counter
from pathlib import PurePosixPath

from ..common import decode, encode, ensure, sha

MAX_MEMBER = 32 * 1024**2
MAX_EXPORT = 1024 * 1024**2
MAX_ARCHIVE = 128 * 1024**2


def safe_path(path):
    ensure(isinstance(path, str) and '\\' not in path and ':' not in path,
           'OUTPUT_INVALID', 'Native export path is invalid')
    parts = PurePosixPath(path)
    ensure(path and not parts.is_absolute() and all(p not in ('', '.', '..') for p in path.split('/')),
           'OUTPUT_INVALID', 'Native export path is outside the result namespace')
    return path


def mhc_summary(value, batches):
    """Count native BindLevel labels only; do not assign new classifications."""
    out = {}
    for kind, channel in value.get('channels', {}).items():
        direct = channel.get('hits')
        children = [b['channels'].get(kind, {}) for b in batches]
        available = channel.get('status') == 'parsed_unreviewed'
        complete = available and (isinstance(direct, list) or bool(children) and
                    all(c.get('status') == 'parsed_unreviewed' and isinstance(c.get('hits'), list) for c in children))
        rows = direct if isinstance(direct, list) else [h for c in children for h in c.get('hits') or []]
        counts = Counter(h['classification'] for h in rows)
        by_allele = {}
        for hit in rows:
            ensure(hit['classification'] in ('SB', 'WB', 'NB'), 'OUTPUT_INVALID', 'Unknown native BindLevel')
            by_allele.setdefault(hit['allele'], Counter())[hit['classification']] += 1
        if complete:
            skipped = channel.get('skipped_inverted_rows', 0)
            ensure(len(rows) + skipped == channel['observed_rows'], 'OUTPUT_INVALID', 'Native MHC batch coverage differs')
        strong = sorted((h for h in rows if h['classification'] == 'SB'),
                        key=lambda h: (h['percent_rank'], h['allele'], h['start'], h['end'], h['peptide_seq']))[:20]
        out[kind] = dict(status=channel.get('status'), counts_complete=complete,
                        observed_rows=channel.get('observed_rows'), parsed_rows=len(rows),
                        counts={k: counts.get(k, 0) if complete else None for k in ('SB', 'WB', 'NB')},
                        allele_counts=[dict(allele=a, **{k: c.get(k, 0) for k in ('SB', 'WB', 'NB')})
                                       for a, c in sorted(by_allele.items())],
                        strong_binding_examples=strong, example_scope='first 20 native SB rows by percent_rank; not a candidate recommendation')
    return out


def collect(rt, job_id, report, *, include_raw=False):
    """Compress each verified member immediately; never retain the raw file set."""
    if not include_raw:
        return _collect(rt, job_id, report)
    with io.BytesIO() as out:
        with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            snapshot, _ = _collect(rt, job_id, report, archive=archive)
        if snapshot is None:
            return None, None
        ensure(out.tell() <= MAX_ARCHIVE, 'OUTPUT_INVALID', 'Compressed native export is too large')
        return snapshot, out.getvalue()


def _collect(rt, job_id, report, *, archive=None):
    """Return a deterministic snapshot and optional full native-output archive.

    Ownership has been checked by Service.report; scoped Runtime access and exact
    producer/run/request/artifact bindings are checked again here. No submit,
    recover, schedule or scientific calculation is performed.
    """
    include_raw = archive is not None
    package = report['content']
    ensure(sha(package) == report['sha256'] and report['job_id'] == job_id,
           'HASH_MISMATCH', 'Verified report identity differs')
    with zipfile.ZipFile(io.BytesIO(package)) as z:
        info = z.getinfo('workflow.json')
        ensure(info.file_size <= MAX_MEMBER, 'OUTPUT_INVALID', 'Workflow snapshot is too large')
        workflow = decode(z.read(info))
    # Legacy packages without producer bindings cannot be expanded safely.
    # Scientific rule version does not determine access to common WT results.
    if not all(key in workflow for key in ('parent_at_assembly', 'sequence_sha256', 'nodes')):
        return None, None
    parent = rt.get(job_id)
    ensure(parent['tool_id'] == 't01.real.local_workflow' and parent['state'] == 'succeeded',
           'FORBIDDEN', 'Terminal workflow producer required')
    assembled = workflow['parent_at_assembly']
    ensure(assembled['job_id'] == job_id and assembled['run_id'] == parent['run_id'],
           'FORBIDDEN', 'Workflow package belongs to another run')
    original = decode(rt._request_bytes(parent))
    ensure(sha(original['protein_sequence'].encode()) == workflow['sequence_sha256'],
           'HASH_MISMATCH', 'Report input sequence differs')
    files = set(); inventory = []; total = 0

    def add(path, raw, ref=None, producer=None):
        nonlocal total
        safe_path(path)
        ensure(path not in files and len(raw) <= MAX_MEMBER, 'OUTPUT_INVALID', 'Native file is duplicate or too large')
        total += len(raw)
        ensure(total <= MAX_EXPORT, 'OUTPUT_INVALID', 'Native export exceeds the bounded result size')
        info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, raw)
        ensure(archive.fp.tell() <= MAX_ARCHIVE, 'OUTPUT_INVALID', 'Compressed native export is too large')
        files.add(path)
        item = dict(path=path, size_bytes=len(raw), sha256=sha(raw))
        if ref is not None: item['artifact'] = ref
        if producer is not None: item['producer'] = producer
        inventory.append(item)
        return item

    def load(jid, name, ref=None, row=None, sequence_sha=None):
        ensure(re.fullmatch('[a-z0-9_]+', name) is not None, 'OUTPUT_INVALID', 'Invalid tool export name')
        job = rt.get(jid)
        ensure(job['run_id'] == parent['run_id'], 'FORBIDDEN', 'Tool result belongs to another run')
        if row is not None:
            ensure(row['state'] == job['state'] and row['artifacts'] == job['artifacts'],
                   'OUTPUT_INVALID', 'Tool snapshot differs from registered producer')
        if ref is None:
            candidates = [a for a in job['artifacts'] if a['role'] in ('result', 'diagnostic')]
            ref = next((a for a in candidates if a['role'] == 'result'), candidates[0] if candidates else None)
        if ref is None: return job, None, None
        ensure(ref in job['artifacts'] and ref['job_id'] == jid and ref['run_id'] == parent['run_id']
               and ref['size_bytes'] <= MAX_MEMBER, 'FORBIDDEN', 'Unregistered tool result')
        raw = rt.artifact_bytes(jid, ref['artifact_id'])
        ensure(len(raw) == ref['size_bytes'] and sha(raw) == ref['sha256'], 'HASH_MISMATCH', 'Tool result bytes differ')
        value = decode(raw); binding = value['binding']
        request = rt._request_bytes(job)
        req = decode(request)
        ensure(binding['job_id'] == jid and binding['run_id'] == parent['run_id']
               and binding['input_sha256'] == sha(request), 'OUTPUT_INVALID', 'Tool result request binding differs')
        if sequence_sha is not None:
            ensure(binding['sequence_sha256'] == sequence_sha and sha(req['protein_sequence'].encode()) == sequence_sha,
                   'OUTPUT_INVALID', 'Batch sequence differs from its controller')
        if include_raw:
            add('tools/' + name + '/result.json', raw, ref, jid)
            for item in value.get('raw_artifacts', []):
                artifact = item['artifact']
                ensure(artifact in job['artifacts'] and artifact['job_id'] == jid and artifact['run_id'] == parent['run_id']
                       and artifact['size_bytes'] <= MAX_MEMBER, 'FORBIDDEN', 'Unregistered native output')
                content = rt.artifact_bytes(jid, artifact['artifact_id'])
                ensure(len(content) == artifact['size_bytes'] and sha(content) == artifact['sha256'],
                       'HASH_MISMATCH', 'Native output bytes differ')
                add('tools/' + name + '/' + safe_path(item['path']), content, artifact, jid)
        return job, ref, value

    nodes = {}; batches_inventory = []
    for name, row in sorted(workflow['nodes'].items()):
        item = dict(node_id=row['node_id'], state=row['state'], job_id=row.get('job_id'),
                    reason_code=row.get('reason_code') or row.get('error_code'), origin=row.get('origin'))
        if row.get('job_id'):
            job, ref, value = load(row['job_id'], name, row=row)
            item.update(tool_id=job['tool_id'], started_at=job.get('started_at'), finished_at=job.get('finished_at'),
                        source_artifact=ref, result=value, native_file_count=len((value or {}).get('raw_artifacts', [])),
                        native_bytes=sum(a['artifact']['size_bytes'] for a in (value or {}).get('raw_artifacts', [])))
            if value is not None and value.get('batch_sources'):
                native_batches = []
                expected = rt.execution(job['job_id'])['batches']
                ensure(len(value['batch_sources']) == len(expected), 'OUTPUT_INVALID', 'MHC batch list differs')
                for source in value['batch_sources']:
                    index = source['index']; batch_ref = source['artifact']
                    ensure(type(index) is int and 0 <= index < len(expected) and batch_ref['job_id'] == expected[index],
                           'FORBIDDEN', 'MHC batch is not owned by the named controller')
                    bjob, bref, bv = load(expected[index], name + '_batch' + str(index), ref=batch_ref,
                                           sequence_sha=value['binding']['sequence_sha256'])
                    ensure(bjob['tool_id'] == 't01.real.netmhc' and bv is not None,
                           'FORBIDDEN', 'Unexpected MHC batch producer')
                    native_batches.append(bv)
                    batches_inventory.append(dict(controller=name, index=index, job_id=bjob['job_id'], state=bjob['state'],
                                                  source_artifact=bref, native_file_count=len(bv.get('raw_artifacts', []))))
                ensure(sorted(s['index'] for s in value['batch_sources']) == list(range(len(expected))),
                       'OUTPUT_INVALID', 'MHC batches are repeated or missing')
                item['mhc_summary'] = mhc_summary(value, native_batches)
            elif value is not None and 'channels' in value:
                item['mhc_summary'] = mhc_summary(value, [])
        nodes[name] = item
    snapshot = dict(kind='REGISTERED_NATIVE_TOOL_RESULTS', version='1.0', job_id=job_id, run_id=parent['run_id'],
                    parent_state=parent['state'], finished_at=parent.get('finished_at'),
                    revision_config=original.get('revision_config'),
                    workflow_package_sha256=report['sha256'], sequence_sha256=workflow['sequence_sha256'],
                    nodes=nodes, mhc_batches=batches_inventory, scientific_gate='CLOSED',
                    scientific_signoff=None, production_status='NOT_DEPLOYED', usable_for_pipeline=False,
                    new_model_calls=0, historical_results_modified=False)
    if not include_raw: return snapshot, None
    add('tool-results.json', encode(snapshot))
    add('original-workflow-package.zip', package)
    add('manifest.json', encode(dict(kind='REGISTERED_NATIVE_OUTPUT_EXPORT', version='1.0',
                                    job_id=job_id, run_id=parent['run_id'], source_package_sha256=report['sha256'],
                                    files=inventory.copy(), original_results_modified=False, new_model_calls=0,
                                    models_and_tool_installations_copied=False, scientific_gate='CLOSED')))
    return snapshot, None
