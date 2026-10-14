"""Validate every repaired/mutant/WT PDB against the reversible native address map."""
import math
from ...common import decode,ensure,sha
from ..foldx.result import AA3

def check_pdb(raw,expected):
    observed={};atoms={}
    for line in raw.decode('utf-8','strict').splitlines():
        if not line.startswith('ATOM  '):continue
        ensure(len(line)>=54,'OUTPUT_INVALID','Truncated FoldX atom record')
        address=(line[21],int(line[22:26]),line[26].strip())
        residue=line[17:20].strip()
        ensure(address in expected and residue==AA3[expected[address]],'OUTPUT_INVALID','FoldX PDB sequence/address differs from exact variant')
        coords=[float(line[start:start+8]) for start in (30,38,46)]
        ensure(all(math.isfinite(v) for v in coords),'OUTPUT_INVALID','Nonfinite FoldX coordinates')
        observed[address]=residue;atoms.setdefault(address,set()).add(line[12:16].strip())
    ensure(set(observed)==set(expected) and all({'N','CA','C','O'}<=a for a in atoms.values()),
        'OUTPUT_INVALID','Incomplete FoldX chain/address/backbone coverage')
    return dict(sha256=sha(raw),residues=len(observed),sequence_and_addresses_verified=True)

def validate(body,files):
    conversion=decode(files['native/conversion.json']);payload=decode(files['native/payload.json'])
    expected={(r['chain_id'],r['tool_pdb_resseq'],''):r['residue'] for r in conversion['rows']}
    ensure(len(expected)==len(conversion['rows']),'OUTPUT_INVALID','Ambiguous FoldX canonical address map')
    checked={}
    repair='output/repair/target_Repair.pdb';checked[repair]=check_pdb(files[repair],expected)
    if payload['mapping_failures'] and not decode(files['output/runtime.json'])['tool_invoked']:return checked
    target={r['sequence_position']:(r['chain_id'],r['tool_pdb_resseq'],'') for r in conversion['rows'] if r['chain_id']==conversion['target_chain']}
    mapped={v['variant_id'] for v in payload['variants'] if not v['mapping_failed']}
    runtime=decode(files['output/runtime.json'])
    parallel=None
    if 'buildmodel_parallel' in runtime:
        from ..foldx.parallel import verified_batches
        parallel=iter(verified_batches(payload,runtime,files))
    for i,variant in enumerate((v for v in body['variants'] if v['variant_id'] in mapped),1):
        mutant=dict(expected)
        for m in variant['mutations']:
            address=target[m['position']]
            ensure(mutant[address]==m['wt'],'OUTPUT_INVALID','FoldX mutation does not match mapped WT residue')
            mutant[address]=m['mut']
        local=files; stem='output/buildmodel/'; native_index=i
        if parallel is not None:
            batch,archive,members=next(parallel)
            ensure(batch['variant_id']==variant['variant_id'],'OUTPUT_INVALID','Parallel PDB variant order differs')
            stem=archive+'!/';native_index=1;local={stem+n:v for n,v in members.items()}
        elif 'buildmodel_archives' in runtime:
            from ..foldx.scan_batches import unpack
            archive=f'output/buildmodel/batches/{i:04d}.zip'
            stem=archive+'!/';local={stem+n:v for n,v in unpack(files[archive]).items()}
        for run in range(5):
            for prefix,residues in (('',mutant),('WT_',expected)):
                name=f'{stem}{prefix}target_Repair_{native_index}_{run}.pdb'
                checked[name]=dict(variant_id=variant['variant_id'],run=run,role='wt_control' if prefix else 'mutant',
                    **check_pdb(local[name],residues))
    return checked
