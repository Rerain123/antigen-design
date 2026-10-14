"""Read-only check of the deployed nr metadata, alias, and provenance contract."""
import json
import prepare_m1_p1_deploy as common

OUT = common.ROOT / 'discovery/t01-phase1-real/m1-p4-20260922/nr-contract-r01.json'
PROGRAM = r'''
import hashlib,json
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development.blast.prebuilt import validate
folder=Path('/var/lib/t01/m1-p1-test-data/blast/nr-20250624')
raw=(folder/'manifest.json').read_bytes()
manifest=json.loads(raw)
result=validate(folder,manifest)
print(json.dumps(dict(status='REAL_TARGET_PREBUILT_CONTRACT_PASS',
    manifest_sha256=hashlib.sha256(raw).hexdigest(),
    volume_count=result['volume_count'],
    file_count=len(manifest['files']),
    integrity=result['integrity'],
    upstream_checksum_verified=result['upstream_checksum_verified'],
    database_qualification=manifest['qualification'])))
'''


def main():
    value = common.remote(PROGRAM)
    assert value['status'] == 'REAL_TARGET_PREBUILT_CONTRACT_PASS'
    assert value['volume_count'] == 123 and value['file_count'] == 2227
    assert value['database_qualification'] == 'TARGET_DATABASE_UNREVIEWED'
    assert not OUT.exists()
    OUT.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    print(value['status'])


if __name__ == '__main__':
    main()
