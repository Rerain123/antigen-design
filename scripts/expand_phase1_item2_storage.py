"""Expand the existing evidence PVC without moving or deleting run data."""
import json
import subprocess
import argparse

import prepare_m1_p1_deploy as c
from prepare_phase1_item2 import EVIDENCE


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--maximum-input-capacity',action='store_true');args=ap.parse_args()
    expected,target,suffix=('128Gi','160Gi','-r02') if args.maximum_input_capacity else ('20Gi','128Gi','')
    before=json.loads(subprocess.check_output(c.K+['get','pvc','antigen-design-runtime','-o','json']))
    assert before['status']['phase']=='Bound'
    assert before['spec']['resources']['requests']['storage']==expected
    storage=json.loads(subprocess.check_output(c.K+['get','storageclass',before['spec']['storageClassName'],'-o','json']))
    assert storage.get('allowVolumeExpansion') is True
    patch=[dict(op='test',path='/metadata/uid',value=before['metadata']['uid']),
           dict(op='test',path='/spec/resources/requests/storage',value=expected),
           dict(op='replace',path='/spec/resources/requests/storage',value=target)]
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    path=EVIDENCE/('runtime-pvc-expansion'+suffix+'.patch.json')
    with path.open('x',encoding='utf8') as stream:json.dump(patch,stream,indent=2)
    command=c.K+['patch','pvc','antigen-design-runtime','--type=json','--patch-file',str(path)]
    subprocess.run(command+['--dry-run=server','-o','name'],check=True)
    subprocess.run(command,check=True)
    evidence=dict(before_request=expected,requested=target,uid=before['metadata']['uid'],
        storage_class=before['spec']['storageClassName'],online_expansion_supported=True,
        reason='Retain the complete package pan allele native evidence for accepted inputs up to 999 residues; no smaller allele subset',
        data_deleted=False,rollback='PVC expansion cannot be shrunk in place')
    if args.maximum_input_capacity:
        from t01_phase1_real.development.netmhc import pan,policy
        panel=pan.manifest()
        rows=sum(panel['channels'][k]['count']*sum(999-n+1 for n in lengths)
            for k,lengths in [('mhc_i',policy.MHC_I_LENGTHS),('mhc_ii',policy.MHC_II_LENGTHS)])
        evidence.update(maximum_input_residues=999,native_rows=rows,guard_required_bytes=rows*1400+256*1024**2,
            correction='All seven native MHC I peptide lengths (8 through 14) require 138148608656 bytes plus existing evidence; 128 GiB is insufficient')
    with (EVIDENCE/('runtime-pvc-expansion'+suffix+'.json')).open('x',encoding='utf8') as stream:json.dump(evidence,stream,indent=2)


if __name__=='__main__':main()
