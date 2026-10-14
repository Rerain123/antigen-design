"""Publish the retained real r02 report through authenticated MCP and verify URLs."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from t01_phase1_real.service_api.object_storage import RustFSPublisher

spec = importlib.util.spec_from_file_location('probe', ROOT / 'scripts/run_cluster_workflow_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
OUT = ROOT / 'discovery/t01-phase1-real/rustfs-report-20260917/r01'

def main():
    batch = json.loads((ROOT / '.tmp/cluster-workflow-probe-r02/batch.json').read_text())
    assert batch['job_id'] == 't01p1r-job-b5c8b65e06914192b4de20f2290598bd'
    current = probe.tool(batch, 'workflow.get', {'job_id': batch['job_id']})
    assert current['state'] == 'succeeded'
    report = probe.tool(batch, 'workflow.report', {'job_id': batch['job_id']})
    assert report['publication_status'] == 'verified'
    assert report['scientific_gate'] == 'CLOSED' and report['usable_for_pipeline'] is False
    assert 'content_base64' not in report
    assert {r['fileName'] for r in report['attachments']} == {'report.zip', 'report.md'}
    artifacts = {}
    for row in report['attachments']:
        u = urlsplit(row['fileUrl'])
        assert u.scheme == 'https' and u.netloc == 'rustfs.ne.scqcyz.cn'
        assert not u.query and not u.fragment
        assert u.path.startswith('/antigen-design/data/') and '/' + batch['job_id'] + '/' in u.path
        assert 0 <= row['sizeBytes'] <= 32 * 1024**2
        status, headers, raw = RustFSPublisher._exchange('https://rustfs.ne.scqcyz.cn', 'GET', u.path, b'', {}, row['sizeBytes'])
        assert status == 200 and len(raw) == row['sizeBytes']
        assert hashlib.sha256(raw).hexdigest() == row['sha256']
        artifacts[row['fileName']] = raw
    package = artifacts['report.zip']
    assert hashlib.sha256(package).hexdigest() == report['sha256']
    assert len(package) == report['size_bytes']
    original = (ROOT / '.tmp/cluster-workflow-probe-r02/report.zip').read_bytes()
    assert package == original, 'Published package differs from retained real report'
    assert artifacts['report.md'] == report['report_markdown'].encode('utf-8')
    with zipfile.ZipFile(io.BytesIO(package)) as z:
        assert z.testzip() is None
        members = len(z.infolist())
    repeated = probe.tool(batch, 'workflow.report', {'job_id': batch['job_id']})
    assert repeated['attachments'] == report['attachments']
    summary = {'status': 'REAL_REPORT_PUBLICATION_VERIFIED', 'job_id': batch['job_id'],
               'publication_status': report['publication_status'], 'attachments': report['attachments'],
               'zip_crc_verified': True, 'zip_members': members, 'matches_retained_report': True,
               'repeat_publication_same_objects': True, 'scientific_computation_rerun': False,
               'scientific_gate': 'CLOSED', 'actual_himat': False,
               'control_image': 'harbor-core.base.svc.cluster.local/qcyz/antigen-design@sha256:fba5a32c0550e56a5310160e2fc49d647fcd27d76851073a2d82cc935fb4c2fc'}
    OUT.mkdir(parents=True, exist_ok=False)
    for name, raw in artifacts.items(): (OUT / name).write_bytes(raw)
    (OUT / 'receipt.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    index = [{'path': p.name, 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in OUT.iterdir() if p.is_file()]
    (OUT / 'index.json').write_text(json.dumps({'files': index, 'scientific_gate': 'CLOSED'}, indent=2)+'\n')
    print(json.dumps(summary, indent=2))

if __name__ == '__main__': main()
