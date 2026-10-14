"""Same-run WT A3M reuse; preserve alignment columns and all homolog rows.

Structure ToolSpec v10.5 §2b: C12 MSA comes from WT. Only equal-length
substitutions are supported; no guessed indel realignment or online search.
"""
from .primitives import decode, encode, ensure, sha


def alignment(raw, wt, sequence):
    ensure(isinstance(raw, str), 'OUTPUT_INVALID', 'AF3 MSA must be A3M text')
    if not raw: return raw
    lines = raw.splitlines(keepends=True)
    headers = [i for i, line in enumerate(lines) if line.startswith('>')]
    ensure(headers and headers[0] == 0, 'OUTPUT_INVALID', 'MSA query header missing')
    end = headers[1] if len(headers) > 1 else len(lines)
    query = ''.join(line.strip() for line in lines[1:end])
    ensure(query == wt and len(wt) == len(sequence), 'OUTPUT_INVALID', 'WT MSA query/length differs')
    for start, stop in zip(headers, headers[1:] + [len(lines)]):
        row = ''.join(line.strip() for line in lines[start+1:stop])
        ensure(row and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-' for c in row)
               and sum(not c.islower() for c in row) == len(wt),
               'OUTPUT_INVALID', 'A3M alignment columns differ')
    return lines[0].rstrip('\r\n') + '\n' + sequence + '\n' + ''.join(lines[end:])


def extract(native, wt):
    names = [n for n in native if n.startswith('app-output/') and n.endswith('_data.json')]
    ensure(len(names) == 1, 'OUTPUT_INVALID', 'Exactly one native AF3 data output required')
    value = decode(native[names[0]])
    ensure(value.get('dialect') == 'alphafold3' and len(value.get('sequences', [])) == 1,
           'OUTPUT_INVALID', 'Single-chain native AF3 MSA required')
    protein = value['sequences'][0]['protein']
    ensure(protein['sequence'] == wt and protein['id'] in ('A', ['A']),
           'OUTPUT_INVALID', 'Native MSA WT sequence or chain differs')
    msas = {key: protein[key] for key in ('unpairedMsa', 'pairedMsa')}
    for raw in msas.values(): alignment(raw, wt, wt)
    ensure(msas['unpairedMsa'], 'OUTPUT_INVALID', 'WT unpaired MSA missing')
    return dict(sequence=wt, sequence_sha256=sha(wt.encode()), msas=msas,
                native_path=names[0], native_sha256=sha(native[names[0]]))


def folding(sequence, seed, prepared=None):
    protein = dict(id='A', sequence=sequence)
    if prepared is not None:
        wt = prepared['sequence']
        ensure(sha(wt.encode()) == prepared['sequence_sha256'], 'OUTPUT_INVALID', 'WT sequence hash differs')
        protein.update({k: alignment(v, wt, sequence) for k, v in prepared['msas'].items()})
        ensure(set(prepared['msas']) == {'unpairedMsa', 'pairedMsa'}, 'OUTPUT_INVALID', 'Exact MSA channels required')
        # Templates remain unspecified: AF3 may search local templates for this
        # variant using the supplied alignment; WT template scores are not copied.
    return dict(name='t01-af3-' + sha(sequence.encode())[:16], modelSeeds=[seed],
                sequences=[dict(protein=protein)], dialect='alphafold3', version=1)


def sources(rt, db, body, run_id):
    if 'msa_source' not in body: return {}, None
    from . import policy
    from .result import result as rebuild
    src = body['msa_source']
    job, _, value = rt._registered_result_artifact(db, src['artifact'], policy.TOOL)
    ensure(job['job_id'] == src['job_id'] and job['run_id'] == run_id and job['state'] == 'succeeded',
           'FORBIDDEN', 'WT MSA must be a successful AF3 job in this run')
    request = policy.request(rt._input(db, job['request_artifact'], run_id))
    ensure('msa_source' not in request and request['host_species'] == body['host_species']
           and len(request['protein_sequence']) == len(body['protein_sequence']),
           'FORBIDDEN', 'WT MSA source host/length or ancestry differs')
    files = {}
    for row in value['raw_artifacts']:
        ensure(row['path'] not in files and row['artifact'] in job['artifacts'], 'FORBIDDEN', 'MSA raw source registration differs')
        files[row['path']] = rt.artifact_bytes(job['job_id'], row['artifact']['artifact_id'])
    rebuilt = rebuild(job, request, files, dict(value['execution']), historical_source=True)
    ensure(rebuilt['execution'].get('error_code') is None and rebuilt['binding'] == value['binding']
           and rebuilt.get('prediction') == value.get('prediction') and rebuilt.get('msa') == value.get('msa')
           and value['scientific_signoff'] is None, 'OUTPUT_INVALID', 'WT AF3 source replay differs')
    native = {n[len('output/raw/'):]: raw for n, raw in files.items() if n.startswith('output/raw/')}
    prepared = extract(native, request['protein_sequence'])
    prepared['source'] = src
    return {'msa-source.json': encode(prepared)}, dict(source=src, native_sha256=prepared['native_sha256'],
            sequence_sha256=prepared['sequence_sha256'], staged_sha256=sha(encode(prepared)))
