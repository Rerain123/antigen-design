"""Download official complete Swiss-Prot originals; no import or workflow change."""
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

BASE='https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/'
NAMES=('uniprot_sprot.dat.gz','uniprot_sprot.fasta.gz')

def run(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    with (root/'started.json').open('x') as f:json.dump(dict(pid=os.getpid()),f)
    status=dict(state='starting',files=[],imported=False,indexed=False,deployed=False)
    def publish(**kw):
        status.update(kw,updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        p=root/'status.pending';p.write_text(json.dumps(status,indent=2));p.replace(root/'status.json')
    try:
        metadata={}
        for name in ('RELEASE.metalink','reldate.txt','LICENSE','README'):
            with urllib.request.urlopen(BASE+name,timeout=60) as r:data=r.read(1024**2+1)
            assert len(data)<=1024**2
            (root/name).write_bytes(data);metadata[name]=data
        tree=ET.fromstring(metadata['RELEASE.metalink']);ns={'m':'http://www.metalinker.org/'}
        version=tree.findtext('m:version',namespaces=ns);assert version=='2026_03',version
        entries={e.attrib['name']:e for e in tree.findall('m:files/m:file',ns)}
        total=sum(int(entries[n].findtext('m:size',namespaces=ns)) for n in NAMES)
        assert shutil.disk_usage(root).free>total+2*1024**3
        publish(release=version,expected_bytes=total)
        for name in ('reldate.txt','LICENSE','README')+NAMES:
            e=entries[name];size=int(e.findtext('m:size',namespaces=ns))
            expected=e.findtext('m:verification/m:hash',namespaces=ns)
            part=root/(name+'.part');md5=hashlib.md5();sha=hashlib.sha256();count=0
            if name in metadata:
                data=metadata[name];md5.update(data);sha.update(data);count=len(data)
            else:
                publish(state='downloading',current_file=name,bytes_received=0)
                last=time.monotonic()
                with urllib.request.urlopen(BASE+name,timeout=90) as r,part.open('xb') as f:
                    assert r.status==200
                    while chunk:=r.read(1024**2):
                        count+=len(chunk);assert count<=size
                        assert shutil.disk_usage(root).free>2*1024**3
                        f.write(chunk);md5.update(chunk);sha.update(chunk)
                        if time.monotonic()-last>3:
                            publish(bytes_received=count);last=time.monotonic()
                assert count==size and md5.hexdigest()==expected,'Official checksum mismatch'
                publish(state='verifying_gzip',bytes_received=count)
                expanded=records=0
                with gzip.open(part,'rb') as f:
                    for line in f:
                        expanded+=len(line);assert expanded<30*1024**3
                        records+=int(line.startswith(b'ID   ') if name.endswith('.dat.gz') else line.startswith(b'>'))
                assert records>500000
                part.rename(root/name)
            assert count==size and md5.hexdigest()==expected,'Official checksum mismatch'
            row=dict(name=name,bytes=count,md5=md5.hexdigest(),sha256=sha.hexdigest(),upstream_checksum_verified=True,url=BASE+name)
            if name in NAMES:row.update(gzip_integrity=True,uncompressed_bytes=expanded,records=records)
            status['files'].append(row);publish()
        counts=[r['records'] for r in status['files'] if 'records' in r];assert counts[0]==counts[1]
        (root/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in status['files']))
        publish(state='downloaded_verified',record_count=counts[0],server_directory=str(root))
    except BaseException as e:
        publish(state='failed',error=repr(e));raise

if __name__=='__main__':run(sys.argv[1])
