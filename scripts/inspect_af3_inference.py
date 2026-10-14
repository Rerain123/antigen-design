"""Read-only audit of five native single-chain AF3 samples and their receipts."""
import hashlib
import json
import math
from pathlib import Path
import shlex

RUN = Path('/runtime/inference-r01')
SEQ_HASH = '233b4b0b8c4616095bc3249f9375fc345d32af7deaef07117d0383c51d6f19aa'
AA = dict(zip('ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL'.split(), 'ARNDCQEGHILKMFPSTWYV'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atom_rows(text):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() != 'loop_':
            continue
        fields = []
        j = i + 1
        while j < len(lines) and lines[j].startswith('_'):
            fields.append(lines[j].strip())
            j += 1
        if not fields or not fields[0].startswith('_atom_site.'):
            continue
        tokens = []
        while j < len(lines):
            line = lines[j].strip()
            if line == '#' or line == 'loop_' or line.startswith('_'):
                break
            if line.startswith(';'):
                raise ValueError('Unexpected multiline atom field')
            tokens.extend(shlex.split(line))
            j += 1
        if len(tokens) % len(fields):
            raise ValueError('Incomplete atom row')
        return [dict(zip(fields, tokens[k:k+len(fields)])) for k in range(0,len(tokens),len(fields))]
    raise ValueError('No atom_site loop')


def audit_sample(sample):
    prefix = sample.parent.name + '_' + sample.name + '_'
    atoms = atom_rows((sample / (prefix + 'model.cif')).read_text())
    confidence = json.loads((sample / (prefix + 'confidences.json')).read_bytes())
    scores = confidence['atom_plddts']
    if len(atoms) != len(scores):
        raise ValueError('Atom/confidence counts differ')
    residues = {}
    ca = {}
    for atom, score in zip(atoms, scores):
        def field(name):
            return atom['_atom_site.' + name]
        if field('label_asym_id') != 'A':
            raise ValueError('Unexpected chain')
        if not isinstance(score, (float,int)) or not math.isfinite(score) or not 0 <= score <= 100:
            raise ValueError('Invalid per-atom confidence')
        if abs(float(field('B_iso_or_equiv')) - score) > 0.011:
            raise ValueError('Native CIF/JSON confidence mismatch')
        if not all(math.isfinite(float(field('Cartn_' + xyz))) for xyz in 'xyz'):
            raise ValueError('Nonfinite coordinates')
        rid = int(field('label_seq_id'))
        residue = residues.setdefault(rid, {'aa': AA[field('label_comp_id')], 'atoms': set()})
        if residue['aa'] != AA[field('label_comp_id')]:
            raise ValueError('Inconsistent residue identity')
        name = field('label_atom_id')
        if name in residue['atoms']:
            raise ValueError('Duplicate atom identity')
        residue['atoms'].add(name)
        if name == 'CA':
            ca[rid] = score / 100
    if set(residues) != set(range(1,77)) or set(ca) != set(residues):
        raise ValueError('Incomplete 76-residue chain')
    sequence = ''.join(residues[i]['aa'] for i in range(1,77))
    if hashlib.sha256(sequence.encode()).hexdigest() != SEQ_HASH:
        raise ValueError('Sequence differs')
    if any(not {'N','CA','C','O'} <= r['atoms'] for r in residues.values()):
        raise ValueError('Incomplete backbone')
    summary = json.loads((sample / (prefix + 'summary_confidences.json')).read_bytes())
    ptm = summary['ptm']
    if not isinstance(ptm,(int,float)) or not math.isfinite(ptm) or not 0 <= ptm <= 1:
        raise ValueError('Invalid pTM')
    return {'sample':sample.name,'atoms':len(atoms),'residues':76,'ptm':ptm,
            'mean_ca_plddt':sum(ca.values()) / 76,
            'native_iptm':summary.get('iptm'), 'native_ranking_score':summary.get('ranking_score')}


def inspect():
    # r01's native computation completed, but its wrapper expected unprefixed names.
    # Independently audit originals; retain the Failed Job and failure.json unchanged.
    recovery = not (RUN / 'receipt.json').exists()
    manifest_path = RUN / 'files-manifest.json'
    if recovery:
        failure = json.loads((RUN / 'failure.json').read_bytes())
        if failure.get('error') != 'Missing native output: /runtime/inference-r01/output/t01-1ubq-af3-data-r01/seed-1_sample-0/model.cif':
            raise ValueError('Unexpected failure; recovery rejected')
        if 'Done running 1 fold jobs.' not in (RUN / 'inference.log').read_text():
            raise ValueError('Native completion evidence missing')
        rows = [{'path':p.relative_to(RUN).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
                for p in sorted(RUN.rglob('*')) if p.is_file()]
    else:
        receipt = json.loads((RUN / 'receipt.json').read_bytes())
        if receipt['status'] != 'AF3_FIVE_NATIVE_SAMPLES_GENERATED_PENDING_INDEPENDENT_AUDIT':
            raise ValueError('Inference not complete')
        if sha(manifest_path) != receipt['files_manifest_sha256']:
            raise ValueError('Manifest hash mismatch')
        rows = json.loads(manifest_path.read_bytes())['files']
    command = json.loads((RUN / 'command.json').read_bytes())
    for flag in ('--run_data_pipeline=false','--run_inference=true','--num_diffusion_samples=5'):
        if flag not in command['command']:
            raise ValueError('Unexpected inference command')
    source = Path('/runtime/data-search-r01/output/t01-1ubq-af3-data-r01/t01-1ubq-af3-data-r01_data.json')
    if sha(RUN / 'input.json') != command['input_sha256'] or sha(source) != command['input_sha256']:
        raise ValueError('Prepared MSA/template input mismatch')
    seen = set()
    for row in rows:
        relative = Path(row['path'])
        if relative.is_absolute() or '..' in relative.parts or row['path'] in seen:
            raise ValueError('Unsafe or duplicate path')
        seen.add(row['path'])
        path = RUN / relative
        if path.is_symlink() or path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise ValueError('File identity mismatch: ' + str(path))
    actual = {p.relative_to(RUN).as_posix() for p in RUN.rglob('*') if p.is_file()}
    if actual != (seen if recovery else seen | {'receipt.json','files-manifest.json'}):
        raise ValueError('Unlisted files or missing manifest members')
    directories = sorted((RUN / 'output').glob('*/seed-1_sample-*'))
    if {p.name for p in directories} != {f'seed-1_sample-{i}' for i in range(5)}:
        raise ValueError('Missing samples')
    samples = [audit_sample(path) for path in directories]
    highest = max(s['ptm'] for s in samples)
    result = {'status':'AF3_FIVE_SAMPLES_INDEPENDENTLY_VERIFIED_ENGINEERING_ONLY',
              'file_count':len(rows),'total_bytes':sum(r['bytes'] for r in rows),
              'files':rows,'wrapper_failure_preserved':recovery,
              'samples':samples, 'highest_ptm_samples':[s['sample'] for s in samples if s['ptm'] == highest],
              'scientific_gate':'CLOSED','usable_for_pipeline':False,'production_status':'NOT_DEPLOYED'}
    print('AF3_INFERENCE_AUDIT_PASS', json.dumps(result, sort_keys=True), flush=True)
    return result


if __name__ == '__main__':
    inspect()
