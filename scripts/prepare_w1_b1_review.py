"""One-time B1 review assets and local parsing evidence; no runtime/scientific qualification."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from t01_structure_mapping.probe import parse_local, propose, read_sequence
from probe_structure_mapping import mapping_validator

CONTRACT=ROOT/'工作流设计/02-数据契约/phase1-real-v0.1/b1-review'
EXPERT=ROOT/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902'
FIX=ROOT/'tests/fixtures/structure_mapping'
PRIOR=ROOT/'discovery/t01-phase1-real/w1/r58-freesasa-boundaries-20260905/prepared'


def raw(value): return json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8')+b'\n'
def sha(value): return hashlib.sha256(value).hexdigest()
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as out: out.write(raw(value))
def read(path): return json.loads(path.read_text(encoding='utf-8'))
def fingerprint(path,base=ROOT):
    data=path.read_bytes()
    return dict(path=path.relative_to(base).as_posix(),sha256=sha(data),size_bytes=len(data))
def obj(properties): return dict(type='object',properties=properties,required=list(properties),additionalProperties=False)
def nullable(value): return dict(anyOf=[value,dict(type='null')])


def schemas():
    artifact=read(CONTRACT.parent/'job.schema.json')['properties']['request_artifact']
    text=dict(type='string',minLength=1)
    ident=dict(type='string',pattern='^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')
    digest=dict(type='string',pattern='^[0-9a-f]{64}$')
    request=obj(dict(contract_version=dict(const='0.1.0'),contract_status=dict(const='DRAFT_REVIEW_ONLY'),
        tool_id=dict(enum=['t01.real.ingest_structure','t01.real.map_structure']),run_id=ident,request_id=ident,
        protein_sequence=dict(type='string',pattern='^[A-Z]+$'),protein_sequence_sha256=digest,host_species=text,
        structure_artifact=artifact,declared_format=dict(enum=['PDB','CIF','MMCIF']),
        selection=obj(dict(model_index=nullable(dict(type='integer',minimum=0)),chain_selector=text)),
        source_declaration=obj(dict(kind=dict(enum=['unknown','experimental','predicted']),note=nullable(text))),
        inventory_artifact=nullable(artifact)))
    binding=obj(dict(run_id=ident,request_id=ident,job_id=ident,attempt_id=ident,request_sha256=digest,
                     sequence_sha256=digest,structure_sha256=digest))
    result=obj(dict(contract_version=dict(const='0.1.0'),contract_status=dict(const='DRAFT_REVIEW_ONLY'),
        tool_id=dict(enum=['t01.real.ingest_structure','t01.real.map_structure']),binding=binding,
        outcome=dict(enum=['parsed','candidate','rejected']),output_artifact=nullable(artifact),
        ingestion_observation=nullable(obj(dict(chain_used=nullable(text),auto_selected=dict(type='boolean'),
            model_index=nullable(dict(type='integer',minimum=0)),seq_extracted=nullable(dict(type='string'))))),
        mapping_status=dict(enum=[None,'unverified','unreliable']),
        unresolved_metadata=obj(dict(source=dict(type='null'),missing_atom_fraction=dict(type='null'),plddt=dict(type='null'))),
        issue_codes=dict(type='array',items=text,uniqueItems=True),review_required=dict(const=True),
        scientific_disposition=dict(const='not_evaluated'),usable_for_pipeline=dict(const=False),
        error_code=dict(enum=[None,'INVALID_REQUEST','INPUT_UNSUPPORTED','FORMAT_MISMATCH','PARSE_FAILED','SELECTION_REQUIRED','SELECTION_NOT_FOUND','OUTPUT_INVALID'])))
    for name,schema in [('request',request),('result',result)]:
        schema['$schema']='https://json-schema.org/draft/2020-12/schema'
        schema['$id']='urn:t01:phase1:real:0.1.0:b1-review:'+name
    return dict(request=request,result=result)


def case_plan(batch):
    cases=[]
    def add(name,source,sequence,expected,*,transform=None,model=None,chain=None,kind='synthetic_fixture'):
        data=source.read_bytes()
        if transform: data=transform(data.decode('utf-8')).encode('utf-8')
        path=batch/'inputs'/(name+source.suffix)
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        seq_path=path.with_suffix('.fasta');seq_path.write_text('>B1_REVIEW_ONLY\n'+sequence+'\n',encoding='utf-8')
        cases.append(dict(id=name,source=fingerprint(source),transformed=transform is not None,
            structure=path.relative_to(batch).as_posix(),structure_sha256=sha(data),sequence=sequence,
            sequence_file=seq_path.relative_to(batch).as_posix(),evidence_kind=kind,model_index=model,
            requested_chain=chain,expected=expected,scope='LOCAL_PARSER_AND_CANDIDATE_ONLY'))
    u=read_sequence(FIX/'real/1UBQ.fasta')
    add('B101-real-1ubq',FIX/'real/1UBQ.cif',u,dict(status='unverified',target='A',null_positions=[],atoms=660),kind='local_input')
    add('B102-real-5xzc',FIX/'real/5XZC.cif',read_sequence(FIX/'real/5XZC.fasta'),dict(status='unreliable',target=None),kind='local_input')
    pdb=FIX/'synthetic/partial-icode.pdb';cif=FIX/'synthetic/partial-icode.cif'
    add('B103-pdb-icode',pdb,'ARG',dict(status='unverified',target='A',null_positions=[2],atoms=8,addresses=[[1,'A',42,''],[3,'A',42,'A']]))
    add('B104-cif-author-label',cif,'ARG',dict(status='unverified',target='AUTH',null_positions=[2],atoms=8))
    add('B105-repeated-no-anchor',pdb,'AAG',dict(status='unreliable',target=None))
    add('B106-substitution',pdb,'AC',dict(status='unreliable',target=None))
    def atoms(text): return ''.join(line+'\n' for line in text.splitlines() if line.startswith('ATOM'))
    def add_insert(text):
        a=atoms(text).splitlines();extra=[]
        for line in a[4:]: extra.append(line[:6]+f'{int(line[6:11])+4:5d}'+line[11:22]+f'{44:4d}'+' '+line[27:])
        return '\n'.join(a[:4]+[line.replace('GLY','SER') for line in a[4:]]+extra)+'\nEND\n'
    add('B107-observed-insertion',pdb,'AG',dict(status='unreliable',target=None),transform=add_insert)
    two=lambda t:'MODEL        1\n'+atoms(t)+'ENDMDL\nMODEL        2\n'+atoms(t)+'ENDMDL\nEND\n'
    add('B108-multimodel-unselected',pdb,'ARG',dict(status='unreliable',target=None,issues=['MODEL_SELECTION_REQUIRED'],atoms=16),transform=two)
    add('B109-multimodel-selected',pdb,'ARG',dict(status='unverified',target='A',model_index=1,atoms=16),transform=two,model=1)
    def context(t):
        first=atoms(t).splitlines()[0]
        z=first[:6]+f'{99:5d}'+first[11:17]+'TRP Z'+first[22:]
        return z+'\n'+atoms(t)+'END\n'
    add('B110-auto-not-design',pdb,'ARG',dict(status='unverified',target='A',ingestion='Z',fixed=['Z']),transform=context)
    add('B111-request-not-design',pdb,'ARG',dict(status='unreliable',target=None,issues=['REQUESTED_CHAIN_MISMATCH']),transform=context,chain='Z')
    def altloc(t):
        lines=t.splitlines();line=lines[2]
        lines[2]=line[:16]+'A'+line[17:]
        lines.insert(3,line[:6]+f'{99:5d}'+line[11:16]+'B'+line[17:])
        return '\n'.join(lines)+'\n'
    add('B112-altloc-retained',pdb,'ARG',dict(status='unverified',target='A',atoms=9,issues=['ALTLOC_REVIEW']),transform=altloc)
    add('B113-nonstandard-mse',pdb,'ARG',dict(status='unreliable',target=None,issues=['UNSUPPORTED_RESIDUE_OR_ADDRESS']),transform=lambda t:t.replace('ALA','MSE'))
    add('B114-noninteger-auth',cif,'ARG',dict(status='PARSE_REJECTED',error_contains='Noninteger author'),transform=lambda t:t.replace(' 42 ALA AUTH',' 42A ALA AUTH'))
    add('B115-missing-auth',cif,'ARG',dict(status='PARSE_REJECTED',error_contains='author numbering'),transform=lambda t:t.replace('_atom_site.auth_seq_id','_atom_site.unused'))
    add('B116-corrupt-format',pdb,'ARG',dict(status='PARSE_REJECTED',error_contains='No recognizable'),transform=lambda t:'not a structure\n')
    add('B117-missing-chain',pdb,'ARG',dict(status='unreliable',target=None,issues=['REQUESTED_CHAIN_MISMATCH']),chain='MISSING')
    prior=[('missing-repeat-75','unverified'),('replacement-conflict','unreliable'),('inserted-label-77','unreliable'),
           ('multichain-ambiguous','unreliable'),('multichain-unique','unverified'),('long-author-chain','unverified')]
    for i,(name,state) in enumerate(prior,118):
        source=PRIOR/'inputs'/name/'input.cif'
        expected=dict(status=state)
        if name=='missing-repeat-75': expected['null_positions']=[75]
        add(f'B{i}-{name}',source,u,expected,model=0)
    # These are parser-development inputs; sub-9 aa fixture lengths do not claim valid T-01 pipeline inputs.
    save(batch/'expected_cases.json',dict(declared_before_execution=True,cases=cases,
        oracle='Explicit fixture edits and prior independent sequence/numbering observations; not algorithm gold standards'))
    return cases


def assert_observed(case,inventory,mapping,error):
    expected=case['expected']
    if expected['status']=='PARSE_REJECTED':
        assert error and expected['error_contains'] in error,(case['id'],error)
        return
    assert error is None,(case['id'],error)
    assert mapping['mapping_status']==expected['status'],case['id']
    assert mapping['usable_for_pipeline'] is False and mapping['review'] is None
    assert mapping['sequence']==case['sequence'] and len(mapping['entries'])==len(case['sequence'])
    assert inventory['raw_atom_count']==inventory['parsed_atom_count']
    assert inventory['metadata_assessment']==dict(structure_source='NOT_INFERRED',plddt='NOT_INFERRED_FROM_B_FACTOR',missing_atom_fraction=None)
    keys=dict(target='target_chain_id',model_index='model_index',ingestion='ingestion_chain_id',fixed='fixed_chain_ids')
    for key,field in keys.items():
        if key in expected: assert mapping[field]==expected[key],(case['id'],key)
    if 'atoms' in expected: assert inventory['raw_atom_count']==expected['atoms']
    if 'null_positions' in expected:
        assert [e['sequence_position'] for e in mapping['entries'] if e['structure_residue'] is None]==expected['null_positions']
    for code in expected.get('issues',[]): assert code in [i['code'] for i in mapping['issues']]
    for pos,chain,resseq,icode in expected.get('addresses',[]):
        residue=mapping['entries'][pos-1]['structure_residue']
        assert (residue['chain_id'],residue['res_seq'],residue['insertion_code'])==(chain,resseq,icode)


def execute(batch,cases):
    assert not (batch/'results').exists()
    validator=mapping_validator();results=[]
    for case in cases:
        inventory=mapping=None;error=None
        path=batch/case['structure']
        assert sha(path.read_bytes())==case['structure_sha256']
        try:
            inventory=parse_local(path)
            mapping=propose(case['sequence'],inventory,evidence_kind=case['evidence_kind'],
                            model_index=case['model_index'],requested_chain=case['requested_chain'])
        except (ValueError,KeyError) as exc: error=str(exc)
        assert_observed(case,inventory,mapping,error)
        if mapping:
            assert validator.validate_mapping(mapping)==[]
            save(batch/'results'/case['id']/'inventory.json',inventory)
            save(batch/'results'/case['id']/'mapping.json',mapping)
        else: save(batch/'results'/case['id']/'parse-error.json',dict(error=error))
        assert sha(path.read_bytes())==case['structure_sha256']
        results.append(dict(id=case['id'],status='PASS_EXPECTED_ENGINEERING_BEHAVIOR',
                            observation=mapping['mapping_status'] if mapping else 'PARSE_REJECTED'))
    save(batch/'assessment.json',dict(status='PASS_REVIEW_PREPARATION',cases=results,
        declared_cases_sha256=sha((batch/'expected_cases.json').read_bytes()),
        scientific_mapping_approval='NOT_GRANTED',target_server_execution='NOT_RUN',
        production_adapter_execution='NOT_RUN',production_status='NOT_DEPLOYED'))


def examples(batch):
    dest=CONTRACT/'examples';dest.mkdir(parents=True,exist_ok=True)
    case='B103-pdb-icode'
    run='t01p1r-run-b1-example'
    def artifact(aid,path,role,job=None):
        data=path.read_bytes()
        return dict(artifact_id='t01p1r-artifact-'+aid,run_id=run,job_id=job,
            attempt_id='t01p1r-attempt-'+aid if job else None,role=role,
            media_type='application/json' if path.suffix=='.json' else 'chemical/x-pdb',
            sha256=sha(data),size_bytes=len(data),evidence_kind='ENGINEERING_FIXTURE')
    structure=artifact('b1-structure',batch/'inputs'/(case+'.pdb'),'input')
    invjob='t01p1r-job-b1-ingest-example';mapjob='t01p1r-job-b1-map-example'
    inventory=artifact('b1-inventory',batch/'results'/case/'inventory.json','result',invjob)
    mapping=artifact('b1-mapping',batch/'results'/case/'mapping.json','result',mapjob)
    ingest=dict(contract_version='0.1.0',contract_status='DRAFT_REVIEW_ONLY',tool_id='t01.real.ingest_structure',
        run_id=run,request_id='b1-ingest-example',protein_sequence='ARG',protein_sequence_sha256=sha(b'ARG'),
        host_species='engineering fixture; not a biological host assertion',structure_artifact=structure,
        declared_format='PDB',selection=dict(model_index=0,chain_selector='AUTO'),
        source_declaration=dict(kind='unknown',note=None),inventory_artifact=None)
    mapreq=dict(ingest,tool_id='t01.real.map_structure',request_id='b1-map-example',inventory_artifact=inventory,
                selection=dict(model_index=None,chain_selector='AUTO'))
    for name,request,ref,outcome in [('ingest',ingest,inventory,'parsed'),('map',mapreq,mapping,'candidate')]:
        save(dest/(name+'-request.json'),request)
        result=dict(contract_version='0.1.0',contract_status='DRAFT_REVIEW_ONLY',tool_id=request['tool_id'],
            binding=dict(run_id=run,request_id=request['request_id'],job_id=ref['job_id'],attempt_id=ref['attempt_id'],
                         request_sha256=sha(raw(request)),sequence_sha256=sha(b'ARG'),structure_sha256=structure['sha256']),
            outcome=outcome,output_artifact=ref,
            ingestion_observation=dict(chain_used='A',auto_selected=True,model_index=0,seq_extracted='AG') if name=='ingest' else None,
            mapping_status='unverified' if name=='map' else None,
            unresolved_metadata=dict(source=None,missing_atom_fraction=None,plddt=None),
            issue_codes=['G1_REVIEW_PENDING'],review_required=True,scientific_disposition='not_evaluated',
            usable_for_pipeline=False,error_code=None)
        save(dest/(name+'-result.json'),result)
    save(CONTRACT/'example_artifacts.json',dict(scope='HAND_AUTHORED_BINDINGS_TO_RECORDED_ENGINEERING_FIXTURES_NOT_RUNTIME_ISSUED',
        artifacts=[dict(ref=ref,path=path.relative_to(ROOT).as_posix()) for ref,path in [
            (structure,batch/'inputs'/(case+'.pdb')),(inventory,batch/'results'/case/'inventory.json'),
            (mapping,batch/'results'/case/'mapping.json')]]))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();batch=args.output_dir.resolve()
    assert batch.is_relative_to(ROOT/'discovery/t01-phase1-real/w1') and not batch.exists()
    batch.mkdir(parents=True)
    for name,schema in schemas().items(): save(CONTRACT/(name+'.schema.json'),schema)
    cases=case_plan(batch)
    execute(batch,cases)
    examples(batch)
    sources=[]
    for path in sorted(EXPERT.iterdir()):
        if path.is_file(): sources.append(dict(fingerprint(path),kind='EXPERT_ORIGINAL'))
    others=[ROOT/'docs/project/sources/PHASE1_NODE01_OFFLINE_SOURCE_20260903.json',
        ROOT/'docs/project/sources/PHASE1_W1_SERVER_CAPACITY_20260905.json',
        ROOT/'docs/project/sources/PHASE1_W1_MODULAR_DEVELOPMENT_20260905.json',
        CONTRACT.parent/'job.schema.json',ROOT/'工作流设计/02-数据契约/tool-interface-v0.1/structure_mapping/mapping.schema.json',
        ROOT/'工作流设计/02-数据契约/tool-interface-v0.1/structure_mapping/validate_mapping.py',
        ROOT/'src/t01_structure_mapping/probe.py',ROOT/'src/t01_structure_mapping/__init__.py',
        ROOT/'scripts/probe_structure_mapping.py',ROOT/'scripts/check_structure_mapping.py',
        FIX/'real/SOURCE_MANIFEST.json',PRIOR/'case_spec.json',
        ROOT/'discovery/t01-phase1-real/w1/w1-preparation-20260905/facts/sample_audit.json']
    for path in others: sources.append(dict(fingerprint(path),kind='CURRENT_SOURCE_OR_PRIOR_EVIDENCE'))
    save(CONTRACT/'source_manifest.json',dict(sources=sources,retrieval=dict(
        scope='All 22 expert package originals plus later user decisions and local evidence',
        searched_terms=['R-58','S-07c','S-07b','T-01 0a','insertion code','auth_seq_id','altloc','原子缺失','比对','宿主'],
        not_found_in_applicable_rules=['R-58 general substitution/gap scoring and acceptance profile',
             'Complete missing-atom denominator/template policy','General alternate-conformer choice policy']),
        external_format_references=[
            dict(url='https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/_atom_site.auth_seq_id.html',
                 section='Item Description / Data Type',checked_date='2026-09-05',finding='Author identifier need not be numeric; no automatic text split authorized'),
            dict(url='https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/_atom_site.pdbx_PDB_ins_code.html',
                 section='Item Description',checked_date='2026-09-05',finding='Insertion code has a separate data item')]))
    import Bio
    save(batch/'environment.json',dict(os=platform.platform(),python=sys.version,biopython=Bio.__version__,
        recorded_at=datetime.now(timezone.utc).isoformat(),execution='LOCAL_PARSE_AND_UNVERIFIED_CANDIDATES',
        network_during_case_execution='NO_NETWORK_CODE_IN_CASE_RUNNER'))
    print(json.dumps(dict(status='PASS_REVIEW_PREPARATION',case_count=len(cases),batch=str(batch)),ensure_ascii=False))


if __name__=='__main__': main()
