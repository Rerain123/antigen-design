"""Call pinned official SSM, reusing one whole-structure embedding across batches.

The official files and model mathematics remain unchanged. This project wrapper
is explicitly recorded; it is not an upstream CLI feature or sequence cropping.
"""
import json
from pathlib import Path

MUTATIONS_PER_BATCH=320
MODE='WT_EMBEDDING_MUTATION_BATCH_V1'


def predict(model,pdb,mutations,*,equal,progress):
    original=model.forward;embedding=model.prot_mpnn.forward
    cached=[];rows=[]
    def shared(*args,**kwargs):
        if not cached:
            value=embedding(*args,**kwargs);cached.append((args,kwargs,value));return value
        previous,keys,value=cached[0]
        if (len(args)!=len(previous) or set(keys)!=set(kwargs)
            or not all(equal(a,b) for a,b in zip(args,previous))
            or not all(equal(keys[k],kwargs[k]) for k in keys)):
            raise ValueError('Whole-structure features changed between mutation batches')
        return value
    model.prot_mpnn.forward=shared
    try:
        for start in range(0,len(mutations),MUTATIONS_PER_BATCH):
            batch=mutations[start:start+MUTATIONS_PER_BATCH]
            output,extra=original(pdb,batch)
            if len(output)!=len(batch) or extra is not None:raise ValueError('Official mutation batch coverage differs')
            # Release per-mutation GPU outputs as soon as a batch is complete;
            # the official writer receives the same values on CPU.
            rows.extend(None if r is None else {k:v.cpu() for k,v in r.items()} for r in output)
            progress(dict(start=start,count=len(batch),completed=len(rows),total=len(mutations)))
    finally:model.prot_mpnn.forward=embedding
    return rows,None


def main():
    import argparse
    import importlib.util
    import sys
    import torch
    from omegaconf import OmegaConf
    parser=argparse.ArgumentParser()
    for key in ('pdb','chain','model_path','out_dir'):parser.add_argument('--'+key,required=True)
    args=parser.parse_args()
    sys.path[:0]=['/app/analysis','/app']
    spec=importlib.util.spec_from_file_location('official_ssm','/app/analysis/custom_inference.py')
    official=importlib.util.module_from_spec(spec);spec.loader.exec_module(official)
    loader=official.get_trained_model;steps=[]
    def progress(row):
        steps.append(row)
        (Path(args.out_dir).parent/'batch-progress.json').write_text(json.dumps(dict(mode=MODE,batches=steps)))
        print('N17 ThermoMPNN mutations',row['completed'],'/',row['total'],flush=True)
    def equal(a,b):
        if isinstance(a,torch.Tensor) or isinstance(b,torch.Tensor):
            return isinstance(a,torch.Tensor) and isinstance(b,torch.Tensor) and torch.equal(a,b)
        return a==b
    def load(*a,**k):
        model=loader(*a,**k);original=model.forward
        def forward(pdb,mutations):
            # Avoid recursion: predict takes the bound original method.
            model.forward=original
            try:return predict(model,pdb,mutations,equal=equal,progress=progress)
            finally:model.forward=forward
        model.forward=forward
        return model
    official.get_trained_model=load
    with torch.no_grad():official.main(OmegaConf.load('/app/local.yaml'),args)


if __name__=='__main__':main()
