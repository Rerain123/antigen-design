"""Pin numeric tables from preserved authoritative source bytes; never fetch at runtime."""
from pathlib import Path
import re
import sys
from Bio.Align import substitution_matrices
import Bio
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import encode,sha


def main():
    folder=REPO/'discovery/t01-phase1-real/w5/design-backend-assets-20260908'
    output=REPO/'src/t01_phase1_real/development/design_backend/scales.json'
    aa='ACDEFGHIKLMNPQRSTVWY';raw=(folder/'aaindex1.txt').read_bytes()
    section=next(s for s in raw.decode().split('//') if re.search(r'^H KYTJ820101$',s,re.M))
    tail=section.split('\nI ')[1].splitlines()
    ordered=''.join(p.split('/')[0] for p in tail[0].split())+''.join(p.split('/')[1] for p in tail[0].split())
    kd=dict(zip(ordered,map(float,' '.join(tail[1:]).split())))
    assert len(kd)==20 and kd['I']==4.5 and kd['R']==-4.5
    html=(folder/'imgt-classes.html').read_bytes()
    text=re.sub('<[^>]+>',' ',html.decode())
    text=' '.join(text.split())
    volume_numbers=[60.1,88.6,89.,108.5,111.1,112.7,114.1,116.1,138.4,140.,143.8,153.2,162.9,166.7,166.7,168.6,173.4,189.9,193.6,227.8]
    # Verify the exact published row, not isolated numbers appearing elsewhere.
    actual=re.search(r'G A S C D P N T E V Q H M I L K R F Y W (.*?) VERY SMALL',text).group(1)
    assert list(map(float,actual.split()))==volume_numbers
    volume=dict(zip('GASCDPNTEVQHMILKRFYW',volume_numbers))
    matrix=substitution_matrices.load('BLOSUM62')
    original=Path(substitution_matrices.__file__).parent/'data/BLOSUM62'
    copy=folder/'BLOSUM62.txt'
    if not copy.exists():copy.write_bytes(original.read_bytes())
    assert copy.read_bytes()==original.read_bytes()
    value=dict(version='0.1.0',scientific_signoff=None,scope='C15/C18/S27/S28_ENGINEERING_DEFAULTS',
        hydrophobicity=kd,volume=volume,charge={a:1 if a in 'KR' else -1 if a in 'DE' else .1 if a=='H' else 0 for a in aa},
        polar='RKDENQHSTY',blosum62={a:{b:int(matrix[a,b]) for b in aa} for a in aa},
        source_receipts={p.name:dict(path=p.relative_to(REPO).as_posix(),sha256=sha(p.read_bytes()),bytes=p.stat().st_size)
            for p in (folder/'aaindex1.txt',folder/'imgt-classes.html',copy)},
        sources=dict(hydrophobicity='https://www.genome.jp/ftp/db/community/aaindex/aaindex1 (KYTJ820101)',
            volume='https://www.imgt.org/IMGTeducation/Aide-memoire/_UK/aminoacids/IMGTclasses.html (Volume row)',
            charge_and_polarity='SOP v10.5 S-28; H=0.1 pH7 approximation',blosum62='Biopython '+Bio.__version__+' original data/BLOSUM62'),
        thresholds=dict(chemical=dict(hydrophobicity=4.5,volume=100.,charge=1.),spatial_distance=10.,epistasis_distance=5.,
            proximity_distance=5.,general=dict(count=12,spatial_clustering=.5,functional_proximity=.3,epitope_proximity=.3),
            solubility=dict(count=15,spatial_clustering=.5,functional_proximity=.3,epitope_proximity=.3),
            thermostability=dict(count=12,spatial_clustering=.5,functional_proximity=.5,epitope_proximity=.3)))
    with output.open('xb') as stream:stream.write(encode(value))
    print('Pinned scales',sha(output.read_bytes()))


if __name__=='__main__':main()
