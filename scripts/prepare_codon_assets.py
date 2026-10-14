"""One-time capture of installed dependencies and the bundled Kazusa table; no overwrite."""
import hashlib
import importlib.metadata as md
import json
from pathlib import Path
import sysconfig

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'src/t01_phase1_real/development/codon/assets'

def digest(raw):return hashlib.sha256(raw).hexdigest()
def write(name,raw):
    DEST.mkdir(parents=True,exist_ok=True)
    with (DEST/name).open('xb') as f:f.write(raw)

def main():
    site=Path(sysconfig.get_paths()['purelib'])
    packages={}
    for name in ('dnachisel','biopython','numpy','python-codon-tables','docopt','flametree','proglog','tqdm','colorama'):
        dist=md.distribution(name);files=[]
        for entry in dist.files:
            path=Path(dist.locate_file(entry)).resolve()
            if not path.is_relative_to(site.resolve()) or path.suffix=='.pyc' or path.name=='RECORD':continue
            raw=path.read_bytes();files.append(dict(path=path.relative_to(site).as_posix(),size_bytes=len(raw),sha256=digest(raw)))
        packages[name]=dict(version=dist.version,files=files)
    raw=(site/'python_codon_tables/codon_usage_data/tables/e_coli_316407.csv').read_bytes()
    write('e_coli_316407.csv',raw)
    manifest=dict(table=dict(file='e_coli_316407.csv',size_bytes=len(raw),sha256=digest(raw),
        taxonomy_id=316407,host='E.coli',profile='ecoli-k12-w3110-kazusa-316407-v1',
        source='https://www.kazusa.or.jp/codon/cgi-bin/showcodon.cgi?aa=1&style=N&species=316407',
        distribution='python-codon-tables==0.1.18',
        distribution_source='https://github.com/Edinburgh-Genome-Foundry/python_codon_tables',
        provenance='Bundled Kazusa-derived relative frequencies, original rounded values retained; not a fresh Kazusa download'),
        python='3.11',packages=packages)
    write('manifest.json',(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
    write('requirements.txt',('\n'.join(k+'=='+v['version'] for k,v in packages.items())+'\n').encode())

if __name__=='__main__':main()
