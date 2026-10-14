"""Read-only archive/publication/ZIP hashes and terminal engineering assertions."""
import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path

def sha(raw):return hashlib.sha256(raw).hexdigest()
def package(raw,expected):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=z.namelist();assert len(names)==len(set(names))
        assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in names)
        manifest=json.loads(z.read('manifest.json'))
        assert set(names)=={r['path'] for r in manifest['files']}|{'manifest.json'}
        for r in manifest['files']:
            data=z.read(r['path']);assert len(data)==r['size_bytes'] and sha(data)==r['sha256']
        assert json.loads(z.read('data.json'))==expected
        assert b'data.json' in z.read('report.md') and b'manifest.json' in z.read('report.md')
        return len(names)

def audit(root):
    index=json.loads((root/'index.json').read_bytes());count=0;published=0;packages=[];scans={}
    for row in index['files']:
        path=(root/row['path']).resolve();assert path.is_relative_to(root.resolve())
        raw=path.read_bytes();assert len(raw)==row['bytes'] and sha(raw)==row['sha256'];count+=1
    assert {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}=={r['path'] for r in index['files']}|{'index.json'}
    for c in index['cases']:
        folder=root/'cases'/c['case'];job=json.loads((folder/'job.json').read_bytes());raws={}
        assert (job['job_id'],job['state'],job['error_code'])==(c['job_id'],c['state'],c['error_code'])
        for ref in job['artifacts']:
            raw=(folder/'artifacts'/ref['artifact_id']).read_bytes()
            assert sha(raw)==ref['sha256'] and len(raw)==ref['size_bytes'];published+=1;raws[ref['artifact_id']]=raw
        if not job['artifacts']:continue
        value=json.loads((folder/'result.json').read_bytes());ref=next(r for r in job['artifacts'] if r['role'] in ('result','diagnostic'))
        assert json.loads(raws[ref['artifact_id']])==value
        assert value['usable_for_pipeline'] is False and value['automatic_handoff'] is False and value['scientific_signoff'] is None
        assert value['binding']['sequence_sha256']==sha(json.loads((folder/'request.json').read_bytes())['protein_sequence'].encode())
        if value.get('reference'):
            reference=value['reference'];assert reference['scan_invocations']==0 and reference['consensus_ranking'] is None and reference['combined_ddg'] is None
            for engine,e in reference['engines'].items():
                seq=json.loads((folder/'request.json').read_bytes())['protein_sequence']
                assert all(r['wt']==seq[r['position']-1] and r['position'] not in e['excluded_positions'] for r in e['records'])
                if e['records']:scans[c['case']+':'+engine]=len(e['records'])
        d=value.get('delivery')
        if d:
            assert d['best_candidate'] is None and d['formal_candidate_id'] is None and d['agent_c_payload'] is None
            assert not d['formal_wt_delivery'] and not d['candidate_record_complete']
            entry=next(r for r in value['raw_artifacts'] if r['path']=='output/package.zip')
            n=package(raws[entry['artifact']['artifact_id']],d);packages.append(dict(case=c['case'],files=n))
            if c['case']=='real24-all-excluded-delivery':
                report=d['variant_report'];assert d['outcome']=='ALL_EXCLUDED' and report['summary']==dict(total=24,excluded=24,retained=0,undetermined=0)
                assert all(r['disposition']=='EXCLUDED' and any(e['code']=='R35_DETERIORATION_EXCEEDED' for e in r['exclusion_reasons']) for r in report['records'])
    return dict(passed=True,verified_files=count,published_artifacts=published,cases=len(index['cases']),guards=len(index['guards']),
        verified_packages=packages,reference_record_counts=scans,index_sha256=sha((root/'index.json').read_bytes()),
        original_24_exclusions_preserved=True,scientific_handoff=False)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('archive',type=Path);a=ap.parse_args()
    print(json.dumps(audit(a.archive),ensure_ascii=False,indent=2))
