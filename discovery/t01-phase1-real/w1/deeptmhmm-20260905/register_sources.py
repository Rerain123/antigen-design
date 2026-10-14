"""Record provenance of already downloaded public assets; no downloads, predictions or submissions."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

BATCH = Path(__file__).resolve().parent
SOURCES = BATCH/'public_sources'
metadata = json.loads((SOURCES/'pybiolib-pypi.json').read_text())
wheel = next(row for row in metadata['urls'] if row['filename'].endswith('.whl'))
known = [
    ('pybiolib-pypi.json','https://pypi.org/pypi/pybiolib/json','urllib response bytes'),
    (wheel['filename'],wheel['url'],'urllib response bytes; verified against PyPI SHA-256'),
    ('deeptmhmm-app.html','https://dtu.biolib.com/DeepTMHMM/','urllib response bytes; JavaScript shell'),
    ('app-metadata.json','https://biolib.com/api/app/?uri=DTU%2FDeepTMHMM','PowerShell response Content re-encoded as UTF-8; not wire bytes'),
    ('dtu-fasta-example.html','https://services.healthtech.dtu.dk/services/DeepTMHMM-1.0/fasta_example.html','Invoke-WebRequest OutFile'),
    ('dtu-service.html','https://services.healthtech.dtu.dk/services/DeepTMHMM-1.0/','Invoke-WebRequest OutFile'),
    ('DeepTMHMM.3line','https://biolib-public-assets.s3.eu-west-1.amazonaws.com/deeptmhmm/DeepTMHMM.3line','Invoke-WebRequest OutFile; direct link in official app description'),
    ('DeepTMHMM.crossval.top','https://biolib-public-assets.s3.eu-west-1.amazonaws.com/deeptmhmm/DeepTMHMM.crossval.top','Invoke-WebRequest OutFile; direct link in official app description'),
]
records = []
for name,url,capture in known:
    path = SOURCES/name
    data = path.read_bytes()
    records.append({'file':name,'source_url':url,'capture':capture,'bytes':len(data),
                    'sha256':hashlib.sha256(data).hexdigest(),
                    'local_file_mtime_utc':datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat()})
receipt = {
    'registered_at':datetime.now(timezone.utc).isoformat(), 'scope':'PUBLIC_SOFTWARE_DOCUMENTATION_AND_DATA_ONLY',
    'downloads':records, 'prediction_submissions':0, 'external_application_submissions':0,
    'initial_download_issue':{
        'script':'fetch_public_sources.py',
        'failed_url':'https://services.healthtech.dtu.dk/services/DeepTMHMM-1.0/fasta_example.html',
        'error':'urllib.error.URLError: SSL: CERTIFICATE_VERIFY_FAILED; unable to get local issuer certificate',
        'result':'PARTIAL_DOWNLOAD; initial script did not write retrieval.json',
        'resolution':'Retried with Windows Invoke-WebRequest default TLS verification; download succeeded. TLS verification was not disabled.'},
    'sdk_extraction':'sdk_sources contains selected .py/METADATA/LICENSE/entry_points.txt copied from the verified wheel; verifier compares each copy to the archive',
    'metadata_route_source':'sdk_sources/biolib/biolib_api_client/biolib_app_api.py get_by_uri; anonymous GET /api/app/?uri=DTU%2FDeepTMHMM',
    'clock_note':'File mtime is a local file fact; not asserted as server publication time or request start time',
}
target = SOURCES/'retrieval.json'
if target.exists():
    raise SystemExit('Refusing to overwrite retrieval receipt')
target.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'registered_public_files':len(records),'prediction_submissions':0}))
