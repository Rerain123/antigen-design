"""Archive compact receipts from completed nr preparation and validation Jobs."""
import argparse
import json
import subprocess
from pathlib import Path
import prepare_m1_p1_deploy as common

OUT = common.ROOT / 'discovery/t01-phase1-real/m1-p4-20260922'
JOBS = {
    'inspect': 'antigen-nr-accept-inspect-r01',
    'info': 'antigen-nr-blastdb-info-r01',
    'sizes': 'antigen-nr-size-breakdown-r01',
    'manifest': 'antigen-nr-stage-manifest-r01',
    'hash': 'antigen-nr-full-hash-r01',
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('kind', choices=JOBS)
    args = ap.parse_args()
    name = JOBS[args.kind]
    job = json.loads(subprocess.check_output(common.K + ['get', 'job', name, '-o', 'json']))
    assert job['status'].get('succeeded') == 1 and job['status'].get('failed', 0) == 0
    log = subprocess.check_output(common.K + ['logs', 'job/' + name], timeout=90).decode()
    container = job['spec']['template']['spec']['containers'][0]
    mount = next((m for m in container.get('volumeMounts', []) if m['name'] == 'database'), None)
    value = dict(job=name, uid=job['metadata']['uid'],
                 completion_time=job['status']['completionTime'],
                 image=container['image'], pvc=next((v['persistentVolumeClaim']['claimName']
                    for v in job['spec']['template']['spec'].get('volumes', [])
                    if 'persistentVolumeClaim' in v), None),
                 read_only_mount=mount.get('readOnly', False) if mount else None,
                 log=log)
    if args.kind in ('inspect', 'sizes', 'manifest', 'hash'):
        value['result'] = json.loads(log.strip().splitlines()[-1])
    if args.kind == 'info':
        assert '935,749,080 sequences; 354,907,547,446 total residues' in log
        assert 'BLASTDB Version: 5' in log
        assert log.count('/data/nr-20250624/raw/nr.') == 123
    if args.kind == 'hash':
        assert value['result']['status'] == 'VERIFIED_FULL_SHA256'
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / ('nr-' + args.kind + '-r01.json')
    assert not path.exists()
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    print(path, value.get('result', {}).get('status', 'PASS'))


if __name__ == '__main__':
    main()
