"""Small multi-volume manifest contracts; native BLAST is checked separately."""
import copy
import pytest
from t01_phase1_real.common import encode,decode,sha,RuntimeFault
from t01_phase1_real.development.blast import policy


def fixture(root):
    folder=root/'engineering-multivol';folder.mkdir(parents=True)
    files={f'part.{i:02d}.{s}':(str(i)+s).encode() for i in range(2) for s in ('phr','pin','psq')}
    files['part.pal']=b'TITLE engineering fixture\nDBLIST part.00 part.01\n'
    meta=dict(dbname='part',dbtype='Protein',**{'number-of-volumes':2,'number-of-sequences':2,
        'last-updated':'2026-09-22T00:00:00','bytes-total':sum(len(b) for b in files.values()),'files':sorted(files)})
    files['metadata.json']=encode(meta)
    m=dict(schema_version='0.2.0',database_id=folder.name,qualification='ENGINEERING_FIXTURE',
        purpose='N03 prebuilt manifest contract fixture',created_at='2026-09-22',
        source=dict(name='engineering multivol',version='test1',release_date='2026-09-22',license='project fixture',reference='https://example.invalid/test1/'),
        blast=dict(db_prefix='part',dbtype='prot',blastdb_version=5,title='engineering fixture',sequence_count=2,
            makeblastdb_version='makeblastdb: 2.17.0+',builder_identity=policy.IMAGE),
        prebuilt=dict(metadata_path='metadata.json',alias_path='part.pal',volume_prefixes=['part.00','part.01'],integrity='LOCAL_SHA256_NO_UPSTREAM_CHECKSUM'),
        files=[])
    for name,raw in files.items():
        (folder/name).write_bytes(raw)
        m['files'].append(dict(path=name,role='metadata' if name=='metadata.json' else 'alias' if name.endswith('.pal') else 'index',bytes=len(raw),sha256=sha(raw)))
    return folder,m


def verify(folder,m):
    raw=encode(m);(folder/'manifest.json').write_bytes(raw)
    return policy.verify_database(folder.parent,dict(database_id=folder.name,database_manifest_sha256=sha(raw)))


def replace(folder,m,name,raw):
    (folder/name).write_bytes(raw)
    next(e for e in m['files'] if e['path']==name).update(bytes=len(raw),sha256=sha(raw))


def test_prebuilt_preserves_engineering_identity_and_full_hashing(tmp_path):
    folder,m=fixture(tmp_path);receipt=verify(folder,m)
    assert receipt['qualification']=='ENGINEERING_FIXTURE' and len(receipt['files'])==8
    (folder/'part.01.psq').write_bytes(b'corrupt')
    with pytest.raises(RuntimeFault,match='changed'):verify(folder,m)


@pytest.mark.parametrize('damage',['missing_volume','unlisted_volume','escape','backslash','alias_escape','alias_mixed',
    'sequence_identity','wrong_snapshot','wrong_name','wrong_bytes','source_fasta_mix','alias_subset'])
def test_prebuilt_rejects_missing_corrupt_or_mixed_identity(tmp_path,damage):
    folder,m=fixture(tmp_path)
    if damage=='missing_volume':(folder/'part.01.pin').unlink()
    elif damage=='unlisted_volume':(folder/'part.02.psq').write_bytes(b'extra')
    elif damage in ('escape','backslash'):m['files'][0]['path']='../outside' if damage=='escape' else '..\\outside'
    elif damage=='alias_escape':replace(folder,m,'part.pal',b'DBLIST part.00 ../other/part.01\n')
    elif damage=='alias_mixed':replace(folder,m,'part.pal',b'DBLIST part.00 nr.01\n')
    elif damage=='alias_subset':replace(folder,m,'part.pal',b'DBLIST part.00 part.01\nOIDLIST subset\n')
    elif damage=='source_fasta_mix':m['files'][0]['role']='source_fasta'
    else:
        meta=decode((folder/'metadata.json').read_bytes())
        if damage=='sequence_identity':meta['number-of-sequences']=3
        elif damage=='wrong_name':meta['dbname']='nr'
        elif damage=='wrong_bytes':meta['bytes-total']+=1
        else:meta['files'][0]='https://example.invalid/other/'+meta['files'][0]
        replace(folder,m,'metadata.json',encode(meta))
    with pytest.raises(RuntimeFault):verify(folder,m)


def test_nr_sized_inventory_and_canonical_gs_snapshot(tmp_path):
    # Tiny bytes, 123 volumes and 1113 native file entries: contract scaling only.
    folder,m=fixture(tmp_path)
    for p in folder.iterdir():p.unlink()
    m['blast'].update(db_prefix='nr',sequence_count=935749080)
    m['source'].update(name='CONTRACT_FIXTURE_NR_LAYOUT',reference='gs://blast-db/2025-06-24-01-05-02/',release_date='2025-06-22')
    m['prebuilt'].update(alias_path='nr.pal',volume_prefixes=[f'nr.{i:03}' for i in range(123)])
    names=[f'nr.{i:03}.{s}' for i in range(123) for s in ('phr','pin','psq','phd','phi','pog','ppd','ppi','pxm')]
    names+=['nr.'+s for s in ('pal','pdb','pos','pot','ptf','pto')]
    rawfiles={n:b'CONTRACT_FIXTURE_INDEX' for n in names}
    rawfiles['nr.pal']=('DBLIST '+' '.join(m['prebuilt']['volume_prefixes'])+'\n').encode()
    meta=dict(dbname='nr',dbtype='Protein',**{'number-of-volumes':123,'number-of-sequences':935749080,
        'last-updated':'2025-06-22T00:00:00',
        'bytes-total':sum(len(raw) for name,raw in rawfiles.items()
                          if name!='nr.pal' and name.rsplit('.',1)[-1] not in ('pdb','pos','pot','ptf','pto','pxm')),
        'files':[m['source']['reference']+n for n in names]})
    rawfiles['metadata.json']=encode(meta);m['files']=[]
    for name,raw in rawfiles.items():
        (folder/name).write_bytes(raw)
        m['files'].append(dict(path=name,role='metadata' if name=='metadata.json' else 'alias' if name=='nr.pal' else 'index',bytes=len(raw),sha256=sha(raw)))
    receipt=verify(folder,m)
    assert len(receipt['files'])==1114 and receipt['qualification']=='ENGINEERING_FIXTURE'
    replace(folder,m,'nr.pal',b'DBLIST nr.000\n')
    with pytest.raises(RuntimeFault):verify(folder,m)


def test_target_prebuilt_requires_consistent_mirror_sidecars(tmp_path):
    folder,m=fixture(tmp_path)
    m['qualification']='TARGET_DATABASE_UNREVIEWED'
    with pytest.raises(RuntimeFault,match='source records'):verify(folder,m)
    for row in list(m['files']):
        if row['role'] not in ('index','alias'):continue
        name=row['path']+'.source.json'
        raw=encode(dict(url='https://mirror.example.invalid/snapshot/'+row['path'],
                        bytes=row['bytes'],validator='fixed-test-validator'))
        (folder/name).write_bytes(raw)
        m['files'].append(dict(path=name,role='provenance',bytes=len(raw),sha256=sha(raw)))
    verify(folder,m)
    sidecar=folder/'part.00.phr.source.json'
    bad=encode(dict(url='https://other.example.invalid/snapshot/part.00.phr',
                    bytes=2,validator='fixed-test-validator'))
    replace(folder,m,sidecar.name,bad)
    with pytest.raises(RuntimeFault):verify(folder,m)
