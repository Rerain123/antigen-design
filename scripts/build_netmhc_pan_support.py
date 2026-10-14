"""Derive executable names from hash-verified, user-supplied DTU archives."""
import hashlib
import json
import tarfile

from t01_phase1_real.common import encode,sha
from t01_phase1_real.development.netmhc import policy


def build():
    receipt=policy.asset_receipt();channels={}
    for kind,member in [('mhc_i','netMHCpan-4.2/data/MHC_pseudo.dat'),
                        ('mhc_ii','netMHCIIpan-4.3/data/pseudosequence.2023.all.X.dat')]:
        digest=receipt['archive_sha256'][kind]
        archive=next(r for r in receipt['original_archives'] if r['sha256']==digest)
        path=policy.PACKAGE/archive['path'];hasher=hashlib.sha256()
        with path.open('rb') as stream:
            while chunk:=stream.read(8*1024**2):hasher.update(chunk)
        assert hasher.hexdigest()==digest
        with tarfile.open(path) as package:
            raw=package.extractfile(member).read()
        supported={line.split()[0].decode('ascii') for line in raw.splitlines() if line.strip()}
        inventory=policy.allele_inventory(kind)
        excluded=[name for name in inventory if name not in supported]
        channels[kind]=dict(archive_sha256=digest,model_member=member,model_member_sha256=sha(raw),
            declared_count=len(inventory),executable_count=len(inventory)-len(excluded),
            excluded_alleles=excluded,reason='ABSENT_FROM_PACKAGE_NATIVE_PSEUDOSEQUENCE_TABLE',
            inventory_sha256=sha((policy.PACKAGE/receipt['components'][kind]['allele_inventory_path']).read_bytes()))
    return dict(schema_version='1',method='All declared CLI allele names having native package model pseudosequences',
        source_image_id=receipt['image_id'],channels=channels,host_selection_applied=False)


if __name__=='__main__':
    value=build();path=policy.HERE/'pan-support.json'
    with path.open('xb') as stream:stream.write(encode(value))
    print(json.dumps({k:dict(declared=v['declared_count'],executable=v['executable_count'],excluded=v['excluded_alleles'])
                      for k,v in value['channels'].items()}))
