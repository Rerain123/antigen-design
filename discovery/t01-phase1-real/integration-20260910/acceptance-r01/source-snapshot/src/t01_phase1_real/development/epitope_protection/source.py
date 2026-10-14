"""Both sides resolve against their own sequence, bound to one immutable variant origin."""
import copy
from ...common import decode,encode,ensure,sha
from ..design_backend.source import sources as registered
from ..design_backend.geometry import geometry
from . import policy

def raw_files(rt,job,value):
    native={}
    for item in value['raw_artifacts']:
        ensure(item['path'] not in native,'OUTPUT_INVALID','Duplicate raw artifact path')
        native[item['path']]=rt.artifact_bytes(job['job_id'],item['artifact']['artifact_id'])
    return native

def side_enrich(rt,db,body,files,values,receipts):
    # Full structure result validation also recomputes RSA from native absolute areas.
    if 'structure' in values:
        from ..structure.result import result as validate
        value=values['structure'];job=rt._job(db,body['upstream']['structure']['job_id'])
        native=raw_files(rt,job,value);req=decode(files['input/structure-request.json'])
        checked=validate(job,req,native,copy.deepcopy(value['execution']))
        ensure(checked['analysis'] is not None and checked['analysis']==value['analysis'],'OUTPUT_INVALID','Paired structure/RSA facts differ from original outputs')
        for name,data in native.items():files['input/structure-native/'+name]=data
        files['input/structure-original.bin']=native['input.structure']
        for name in ('preflight','raw_metadata','raw_addresses','mapping'):
            if 'output/result/'+name+'.json' in native:files['input/'+name+'.json']=native['output/result/'+name+'.json']
    if 'epitope_map' in values:
        value=values['epitope_map'];job=rt._job(db,body['upstream']['epitope_map']['job_id'])
        req=decode(files['input/epitope_map-request.json']);native=raw_files(rt,job,value)
        from ..epitope_map.result import _parse
        parsed=_parse(native,req)
        ensure(parsed['epitopes']==value['epitopes'],'OUTPUT_INVALID','N06 prediction maps differ from original observation')
        # Recursively verify original predictor artifacts, including native outputs.
        producers={};upstream={}
        for name,tool in (('bepipred','t01.real.bepipred'),('netmhc','t01.real.netmhc'),('blast','t01.real.blast')):
            ref=req[name+'_input']['artifact']
            if ref is not None:producers[name]=tool;upstream[name]=dict(job_id=ref['job_id'],artifact=ref)
        nested,_,nr=registered(rt,db,dict(protein_sequence=body['protein_sequence'],upstream=upstream),producers=producers,enricher=lambda *args:None)
        for name in producers:
            ensure(nested['input/'+name+'-result.json']==native['input/'+name+'-result.json'],'HASH_MISMATCH','N06 predictor snapshot differs')
        receipts['epitope_map']['predictors']=nr
        for name,data in native.items():files['input/map-native/'+name]=data
    if 'domains' in values:
        value=values['domains'];job=rt._job(db,body['upstream']['domains']['job_id']);native=raw_files(rt,job,value)
        observed=decode(native['output/observation.json'])
        ensure(observed['result']==value['analysis'],'OUTPUT_INVALID','N09 original analysis differs')
        from ..domains.service import evaluate as evaluate_domains
        req=decode(files['input/domains-request.json'])
        ensure(evaluate_domains(req,native)==value['analysis'],'OUTPUT_INVALID','N09 domains differ from registered annotation snapshots')
        ensure(observed['input_hashes']=={k:sha(v) for k,v in native.items() if k.startswith('input/')},'HASH_MISMATCH','N09 input hashes differ')
        producers={};upstream={}
        for name,tool in (('structure','t01.real.ingest_structure'),('topology','t01.real.deeptmhmm')):
            ref=req[name+'_input']['artifact']
            if ref is not None:producers[name]=tool;upstream[name]=dict(job_id=ref['job_id'],artifact=ref)
        nested,_,nr=registered(rt,db,dict(protein_sequence=body['protein_sequence'],upstream=upstream),producers=producers,enricher=lambda *args:None)
        for name in producers:ensure(nested['input/'+name+'-result.json']==native['input/'+name+'-result.json'],'HASH_MISMATCH','N09 upstream snapshot differs')
        receipts['domains']['upstream']=nr
        for name,data in native.items():files['input/domain-native/'+name]=data

def facts(body,files,values,receipts):
    s=values.get('structure');analysis=(s or {}).get('analysis') or {}
    mapping=analysis.get('mapping');quality=analysis.get('quality') or {};rsa=analysis.get('rsa') or {}
    q=quality.get('s11_quality_condition');geo=None;reasons=[]
    if mapping and mapping.get('target_chain_id'):
        geo=geometry(body,files)['residues']
    ratios=(rsa.get('development_result') or {}).get('per_residue')
    if ratios is not None:ensure(len(ratios)==len(body['protein_sequence']),'OUTPUT_INVALID','RSA length differs from side sequence')
    ep=(values.get('epitope_map') or {}).get('epitopes') or {};hm=ep.get('b_cell_antigenic_hotspot_map')
    hotspots=hm.get('hotspots') if hm else None
    if hotspots is None:reasons.append('HOTSPOTS_NOT_GENERATED_OI_007_026')
    elif not hotspots:reasons.append('COMPUTED_EMPTY_HOTSPOTS_NO_SCIENTIFIC_PASS')
    domain=(values.get('domains') or {}).get('analysis');regions=None
    if domain and domain.get('lookup',{}).get('status')=='hit':
        regions=[r for r in domain['functional_domains'] if r['source']!='structure' and r['type']!='disulfide_bond']
    for name,r in receipts.items():
        reasons.append(name+':'+r['state'])
    reasons+=['STRUCTURE_RSA_AND_PREDICTIONS_UNSIGNED']
    return dict(sequence_sha256=sha(body['protein_sequence'].encode()),source_receipts=receipts,
        structure_artifact=body['upstream']['structure'],mapping=mapping,quality_condition=q,quality=quality,
        rsa=ratios,rsa_state=rsa.get('status'),geometry=geo,hotspots=hotspots,hotspot_map_state=hm,
        prediction_rule_profile=(values.get('epitope_map') or {}).get('binding',{}).get('rule_profile'),domains=regions,reasons=reasons)

def enrich(rt,db,body,files,values,receipts):
    ensure('base_report' in values,'OUTPUT_INVALID','Successful base report required')
    base=values['base_report'];req=decode(files['input/base_report-request.json'])
    ensure(not req.get('n13_source'),'INVALID_REQUEST','N13 base must precede N13; report cycles forbidden')
    from ..variant_report.source import sources as report_sources
    from ..variant_report.compute import variants
    prior,pv,pr=report_sources(rt,db,req)
    actual=variants(req,prior,pv);reported=base['report']['records']
    ensure([(r['id'],r['sequence'],r['mutations']) for r in actual]==[(r['id'],r['sequence'],r['mutations']) for r in reported],
        'OUTPUT_INVALID','Base report variant identities differ from verified producers')
    job=rt._job(db,body['upstream']['base_report']['job_id']);native=raw_files(rt,job,base)
    ensure(decode(native['output/variant-report.json'])==base['report'],'OUTPUT_INVALID','Original report differs')
    receipts['base_report']['producers']=pr
    by_id={r['id']:r for r in actual};pairs=[];side_cache={}
    for item in body['pairs']:
        ensure(item['variant_id'] in by_id,'OUTPUT_INVALID','Variant absent from the named report batch')
        record=by_id[item['variant_id']];sides={}
        for side in ('wt','variant'):
            seq=body['protein_sequence'] if side=='wt' else record['sequence']
            side_body=dict(protein_sequence=seq,upstream=item[side])
            key=sha(encode(side_body))
            if key not in side_cache:
                sf,sv,sr=registered(rt,db,side_body,producers=policy.SIDE_PRODUCERS,enricher=side_enrich)
                side_cache[key]=facts(side_body,sf,sv,sr)
                for name,data in sf.items():files['input/sides/'+key+'/'+name]=data
            sides[side]=side_cache[key]
        # Explicit WT reference must match the original design base, even for same-sequence structures.
        expected=None
        if req['variant_source']=='N11_DESIGN_AUDIT' and 'input/design_audit-request.json' in prior:
            expected=decode(prior['input/design_audit-request.json'])['upstream']['structure']
        elif 'input/foldx-request.json' in prior:
            ref=decode(prior['input/foldx-request.json'])['structure_artifact'];expected=dict(job_id=ref['job_id'],artifact=ref)
        if item['wt']['structure'] is not None:ensure(item['wt']['structure']==expected,'OUTPUT_INVALID','WT structure differs from original variant design base')
        wm=sides['wt']['mapping'];vm=sides['variant']['mapping']
        if wm and vm and wm.get('target_chain_id') and vm.get('target_chain_id'):
            ensure(wm['target_chain_id']==vm['target_chain_id'],'OUTPUT_INVALID','Target chains differ; no declared chain-renaming mapping')
        pair_id=sha(encode(dict(base_report=body['upstream']['base_report'],variant_id=item['variant_id'],sequence_sha256=sha(record['sequence'].encode()),sources=item)))
        pairs.append(dict(variant_id=item['variant_id'],sequence=record['sequence'],pair_id=pair_id,sides=sides))
    files['input/paired-facts.json']=encode(dict(pairs=pairs))

def sources(rt,db,body):return registered(rt,db,body,producers=policy.PRODUCERS,enricher=enrich)
