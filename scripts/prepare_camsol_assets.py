"""Download only public parameter sources; never send protein inputs."""
import hashlib
import json
import re
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'src/t01_phase1_real/development/developability/assets/camsol-preparation-v1'
URLS=dict(swissprot='https://web.expasy.org/docs/relnotes/relstat.html',
    roseman='https://web.expasy.org/protscale/pscale/Hphob.Roseman.html')
AA='ACDEFGHIKLMNPQRSTVWY'
NAMES=dict(zip(('Ala','Cys','Asp','Glu','Phe','Gly','His','Ile','Lys','Leu','Met','Asn','Pro','Gln','Arg','Ser','Thr','Val','Trp','Tyr'),AA))

def main():
    OUT.mkdir(parents=True,exist_ok=True);sources={};pages={}
    for key,url in URLS.items():
        raw=urllib.request.urlopen(url,timeout=60).read()
        (OUT/(key+'.html')).write_bytes(raw);pages[key]=raw.decode('utf8')
        sources[key]=dict(url=url,file=key+'.html',sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
    assert 'Release 2026_03' in pages['swissprot']
    section=pages['swissprot'].split('6.1')[1].split('6.2')[0]
    frequencies={aa:float(x) for aa,x in re.findall(r'\(([A-Z])\)\s+(\d+\.\d+)',section) if aa in AA}
    scale={NAMES[n]:float(x) for n,x in re.findall(r'([A-Z][a-z]{2}):\s*([-+]?\d+(?:\.\d+)?)',pages['roseman']) if n in NAMES}
    assert set(frequencies)==set(scale)==set(AA),(frequencies,scale)
    data=dict(kind='CAMSOL_PREPARATION_NOT_APPROVED_PARAMETERS',release='Swiss-Prot 2026_03',sources=sources,
        amino_acid_order=AA,published_percent=frequencies,frequencies={a:frequencies[a]/sum(frequencies.values()) for a in AA},
        frequency_method='NORMALIZED_PUBLISHED_ROUNDED_AA20_PERCENTAGES_NOT_EXACT_COUNTS',
        roseman_public_values=scale,roseman_transform=None,pattern_count=None,mu_random=None,sigma_random=None,
        scientific_consumption=False,blocked=['OI_025_ROSEMAN_SIGN','OI_025_PATTERN_COUNT','OI_025_PH_MAPPING'])
    raw=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode()
    (OUT/'manifest.json').write_bytes(raw)
    (OUT/'manifest.sha256').write_text(hashlib.sha256(raw).hexdigest()+'\n',encoding='ascii')
    print(json.dumps(dict(output=str(OUT),manifest_sha256=hashlib.sha256(raw).hexdigest(),aa_count=len(scale))))

if __name__=='__main__':main()
