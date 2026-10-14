"""Create a local reviewable source payload; never contact the cluster."""
import json
from pathlib import Path
from version_bundle import build,encode,sha

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deploy/expert-revision-core/review-r01'
EVIDENCE=ROOT/'reports/expert-revision-core-20260929'


def main():
    archive,manifest=build(ROOT/'src')
    OUT.mkdir(parents=True,exist_ok=True)
    artifacts={'source.tar.gz':archive,'manifest.json':encode(manifest),
        'install.py':(ROOT/'scripts/version_bundle.py').read_bytes()}
    for name,raw in artifacts.items():(OUT/name).write_bytes(raw)
    authority=ROOT/'工作流设计/01-业务依据/计算流程修订_20260929/Agent A 一期计算规则与流程修订方案.md'
    receipt=dict(status='LOCAL_REVIEW_READY_NOT_DEPLOYED',source_sha256=sha(encode(manifest)),source_files=len(manifest),
        artifacts={name:dict(sha256=sha(raw),size_bytes=len(raw)) for name,raw in artifacts.items()},
        destination=dict(kubernetes_namespace='him-ws',deployment='antigen-design',container_count=10),
        content_scope='Project source packages only; no kubeconfig, credentials, model weights or scientific run data',
        authorization_required='Upload this exact source payload, import-check, prepare rollback, deploy and verify existing test service',
        source_authority=dict(path=authority.relative_to(ROOT).as_posix(),sha256=sha(authority.read_bytes())),
        does_not_authorize=['New scientific jobs','Restart cancelled PCV2 run','Scientific policy approval'],
        entrypoint='scripts/deploy_expert_revision_core.py',
        deployment_status='BLOCKED_AUTO_REVIEW_SOURCE_TRANSFER_AUTHORIZATION',
        tests={p.name:sha(p.read_bytes()) for p in EVIDENCE.glob('*.junit.xml')})
    (OUT/'review.json').write_bytes(encode(receipt)+b'\n')
    (EVIDENCE/'tested-source.json').write_bytes(encode(dict(source_hashes=manifest))+b'\n')
    print(json.dumps({k:receipt[k] for k in ('status','source_sha256','source_files')}))


if __name__=='__main__':main()
