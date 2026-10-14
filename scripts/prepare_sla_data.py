"""Download an immutable official IPD-MHC snapshot and index SLA records locally."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
COMMIT='23598004a4209aca1526a8036bb1ea6d31f718f4'
OUT=ROOT/'var/t01-phase1-real/host-panels/ipdmhc-20260726'
FILES=('MHC_prot.fasta','MHC_nuc.fasta','README.md','LICENCE.md')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    sources=[];records={}
    for name in FILES:
        url=f'https://raw.githubusercontent.com/ANHIG/IPDMHC/{COMMIT}/{name}'
        path=OUT/name
        if not path.exists():
            with urllib.request.urlopen(url,timeout=120) as response:
                raw=response.read(64*1024**2+1)
            if len(raw)>64*1024**2:raise ValueError('Snapshot file too large')
            path.write_bytes(raw)
        raw=path.read_bytes()
        sources.append(dict(name=name,url=url,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        if name.endswith('.fasta'):
            rows=[]
            for block in raw.decode().split('>')[1:]:
                header,*lines=block.splitlines()
                if any(word.startswith('SLA-') for word in header.split()):
                    seq=''.join(lines)
                    rows.append(dict(header=header,length=len(seq),sequence_sha256=hashlib.sha256(seq.encode()).hexdigest()))
            records[name]=rows
    receipt=dict(source='EBI IPD-MHC official linked repository',repository='https://github.com/ANHIG/IPDMHC',
        commit=COMMIT,files=sources,sla_records=records,
        usage='Reference sequence inventory only; not an approved host panel or an executed MHC-II prediction',
        original_files_unmodified=True,external_sequences_submitted=False)
    (OUT/'sla-index.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(commit=COMMIT,sla_counts={k:len(v) for k,v in records.items()},files=sources)))


if __name__=='__main__':main()
