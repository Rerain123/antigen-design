"""Official ProteinMPNN CPU parser/featurizer probe only; never loads a model or samples."""
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import torch


def main():
    sys.path.insert(0,'/app')
    from protein_mpnn_utils import tied_featurize
    result=subprocess.run([sys.executable,'-B','/app/helper_scripts/parse_multiple_chains.py','--input_path','/native/',
        '--output_path','/out/parsed.jsonl'],capture_output=True,check=True)
    parsed=json.loads(Path('/out/parsed.jsonl').read_bytes())
    read=lambda n:json.loads(Path('/native/'+n).read_bytes())
    conversion=read('conversion.json');body=read('request.json')
    features=tied_featurize([parsed],torch.device('cpu'),read('chain_id.jsonl'),read('fixed_positions.jsonl'),read('omit_AA.jsonl'))
    _,_,mask,_,chains,_,order,_,_,_,positions,omits,*_=features
    order=order[0];target=conversion['target_chain'];offset=sum(len(conversion['chain_sequences'][c]) for c in order[:order.index(target)])
    alphabet='ACDEFGHIKLMNPQRSTVWYX';fixed=body['constraints']['fixed_positions']
    restricted={r['position']:set(r['allowed_residues']) for r in body['constraints']['restricted_positions']}
    for chain in order:
        start=sum(len(conversion['chain_sequences'][c]) for c in order[:order.index(chain)])
        for p in range(1,len(conversion['chain_sequences'][chain])+1):
            i=start+p-1
            assert mask[0,i]==1 and chains[0,i]==int(chain==target)
            if chain==target:
                assert positions[0,i]==int(p not in fixed)
                if p in restricted:assert {a for a,v in zip(alphabet,omits[0,i].tolist()) if v==0}==restricted[p]
    evidence=dict(kind='REAL_NATIVE_MASK_FEATURIZER_NO_GENERATION',network_interfaces=socket.if_nameindex(),
        model_loaded=False,generation_invocations=0,chain_order=order,target_chain=target,target_offset=offset,
        position_mask=positions[0].tolist(),chain_mask=chains[0].tolist(),omit_mask=omits[0].tolist(),
        source_hashes={p.relative_to('/app').as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/app').rglob('*') if p.is_file()},
        input_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/native').iterdir() if p.is_file()},
        parser_stdout=result.stdout.decode(),parser_stderr=result.stderr.decode())
    Path('/out/mask-probe.json').write_text(json.dumps(evidence,sort_keys=True))


if __name__=='__main__':main()
