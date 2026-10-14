"""Both sides resolve against their own sequence, bound to one immutable variant origin."""
import copy
from ...common import decode,encode,ensure,sha
from ..design_backend.source import sources as registered
from ..design_backend.geometry import geometry
from . import policy

def same_run_receipts(receipts,run_id):
    """Also fence nested N06 predictors and N09 structural sources."""
    for receipt in receipts.values():
        if receipt.get('verified'):
            ensure(receipt.get('run_id')==run_id,'FORBIDDEN','N13 evidence belongs to another run')
        for key in ('predictors','upstream'):
            if key in receipt:same_run_receipts(receipt[key],run_id)

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
        ensure(all(parsed[k]==value[k] for k in ('epitopes','blast_similarity','blast_input')),
            'OUTPUT_INVALID','N06 maps or IEDB provenance differ from original observation')
        # Recursively verify original predictor artifacts, including native outputs.
        producers={};upstream={}
        for name,tool in (('bepipred','t01.real.bepipred'),('netmhc','t01.real.netmhc'),('blast','t01.real.blast'),('topology','t01.real.deeptmhmm')):
            ref=req.get(name+'_input',{}).get('artifact')
            if ref is not None:producers[name]=tool;upstream[name]=dict(job_id=ref['job_id'],artifact=ref)
        nested,_,nr=registered(rt,db,dict(protein_sequence=body['protein_sequence'],upstream=upstream),producers=producers,enricher=lambda *args:None)
        # N06 persists prediction bytes only for available sources. Failed
        # producers are bound by diagnostic refs and source receipts instead.
        _, replayed=rt._epitope_sources(db,req)
        ensure(replayed==value['execution'].get('source_receipts'),
               'OUTPUT_INVALID','N06 predictor source receipts differ')
        for name in producers:
            path='input/'+name+'-result.json'
            if req[name+'_input']['state']!='available':
                ensure(nr[name]['state']=='failed' and path not in native,
                       'OUTPUT_INVALID','N06 unavailable predictor must retain diagnostics without prediction bytes')
                continue
            ensure(path in native and nested[path]==native[path],'HASH_MISMATCH','N06 predictor snapshot differs')
            if name=='netmhc':
                prediction=decode(nested['input/netmhc-result.json'])
                if prediction.get('scope') in ('N05_NETMHC_PACKAGE_PAN','N05_NETMHC_HOST_PANEL'):
                    from ..netmhc.service import verify_sources
                    verify_sources(rt,rt._job(db,upstream[name]['job_id']),prediction)
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
    from ..structure.normalization import consumable_positions
    ratios=consumable_positions(rsa)
    if ratios is not None:ensure(len(ratios)==len(body['protein_sequence']),'OUTPUT_INVALID','RSA length differs from side sequence')
    ep=(values.get('epitope_map') or {}).get('epitopes') or {};hm=ep.get('b_cell_antigenic_hotspot_map')
    hotspots=hm.get('hotspots') if hm else None
    if hotspots is None:reasons.append('HOTSPOTS_NOT_GENERATED_OI_007_026')
    elif not hotspots:reasons.append('COMPUTED_EMPTY_HOTSPOTS_NO_SCIENTIFIC_PASS')
    domain=(values.get('domains') or {}).get('analysis');regions=None
    if domain and domain.get('lookup',{}).get('status')=='hit':
        from ..expert_feedback import functional_regions
        regions=[r for r in functional_regions(domain['functional_domains']) if r['source']!='structure' and r['type']!='disulfide_bond']
    for name,r in receipts.items():
        reasons.append(name+':'+r['state'])
    reasons+=['STRUCTURE_RSA_AND_PREDICTIONS_UNSIGNED']
    similarity=(values.get('epitope_map') or {}).get('blast_similarity')
    prior=(similarity or {}).get('iedb_evidence')
    contacts=prior.get('contact_residues',[]) if prior else []
    for row in contacts:
        ensure(type(row.get('sequence_position')) is int and 1<=row['sequence_position']<=len(body['protein_sequence'])
            and row.get('residue')==body['protein_sequence'][row['sequence_position']-1]
            and row.get('coordinate_sha256') and row.get('evidence_source')==row.get('source_iedb_id'),
            'OUTPUT_INVALID','Coordinate-backed E4 source identity differs')
    if prior is None:reasons.append('IEDB_PRIOR_UNAVAILABLE')
    elif prior.get('e4_status')=='unavailable':reasons.append('IEDB_E4_COORDINATES_UNAVAILABLE')
    return dict(sequence_sha256=sha(body['protein_sequence'].encode()),source_receipts=receipts,
        structure_artifact=body['upstream']['structure'],mapping=mapping,quality_condition=q,quality=quality,
        rsa=ratios,rsa_state=rsa.get('status'),geometry=geo,hotspots=hotspots,hotspot_map_state=hm,
        prediction_rule_profile=(values.get('epitope_map') or {}).get('binding',{}).get('rule_profile'),
        blast_similarity=similarity,iedb_prior=prior,e4_positions=sorted({r['sequence_position'] for r in contacts}),
        domains=regions,domain_analysis=domain,reasons=reasons)

def enrich(rt,db,body,files,values,receipts):
    ensure('design_audit' in values,'OUTPUT_INVALID','Successful N12 design audit required')
    from ..variant_report.m1 import verified_preselection
    fact=verified_preselection(rt,db,body['protein_sequence'],body['user_sequence_id'],body['upstream']['design_audit'],
                              body['preselection'].get('validation_source'),body['preselection'].get('selection_scope'))
    ensure(fact==body['preselection'],'OUTPUT_INVALID','N12 representative fact differs from verified producers')
    files['input/preselection-fact.json']=encode(fact)
    receipts['design_audit']['preselection_records_sha256']=fact['records_sha256']
    req=decode(files['input/design_audit-request.json'])
    by_id={r['id']:r for r in fact['selected']};pairs=[];side_cache={}
    for item in body['pairs']:
        ensure(item['variant_id'] in by_id,'OUTPUT_INVALID','Variant absent from N12 representative selection')
        record=by_id[item['variant_id']];sides={}
        for side in ('wt','variant'):
            seq=body['protein_sequence'] if side=='wt' else record['sequence']
            side_body=dict(protein_sequence=seq,upstream=item[side])
            key=sha(encode(side_body))
            if key not in side_cache:
                sf,sv,sr=registered(rt,db,side_body,producers=policy.SIDE_PRODUCERS,enricher=side_enrich)
                same_run_receipts(sr,receipts['design_audit']['run_id'])
                side_cache[key]=facts(side_body,sf,sv,sr)
                for name,data in sf.items():files['input/sides/'+key+'/'+name]=data
            sides[side]=side_cache[key]
        # Explicit WT reference must match the original design base, even for same-sequence structures.
        expected=req['upstream']['structure']
        if item['wt']['structure'] is not None:ensure(item['wt']['structure']==expected,'OUTPUT_INVALID','WT structure differs from original variant design base')
        ensure(item['wt']['domains']==req['upstream'].get('domains'),
            'OUTPUT_INVALID','WT domains differ from original N12 source')
        # Both queries must refer to the identical local database snapshot and
        # IEDB metadata. Per-sequence HSPs/regions are retained independently.
        a=sides['wt'].get('blast_similarity');b=sides['variant'].get('blast_similarity')
        if a and b and a.get('state')==b.get('state')=='available':
            ensure(a['database']==b['database'],'OUTPUT_INVALID','Paired BLAST database snapshots differ')
        wm=sides['wt']['mapping'];vm=sides['variant']['mapping']
        if wm and vm and wm.get('target_chain_id') and vm.get('target_chain_id'):
            ensure(wm['target_chain_id']==vm['target_chain_id'],'OUTPUT_INVALID','Target chains differ; no declared chain-renaming mapping')
        pair_id=sha(encode(dict(preselection=fact,variant_id=item['variant_id'],sequence_sha256=sha(record['sequence'].encode()),sources=item)))
        pairs.append(dict(variant_id=item['variant_id'],sequence=record['sequence'],pair_id=pair_id,sides=sides))
    if fact.get('selection_scope')=='ALL_VALIDATED':
        from .compute import compare
        index=[]
        for i,pair in enumerate(pairs,1):
            path=f'input/pairs/{i}.json';details=f'input/pairs/{i}-observation.json'
            files[path]=encode(pair)
            files[details]=encode(compare(body['protein_sequence'],pair['sequence'],pair['sides']))
            index.append(dict(path=path,sha256=sha(files[path]),observation_path=details,observation_sha256=sha(files[details])))
        files['input/paired-facts.json']=encode(dict(format='PER_PAIR_V1',pairs=index))
    else:files['input/paired-facts.json']=encode(dict(pairs=pairs))

def sources(rt,db,body):return registered(rt,db,body,producers=policy.PRODUCERS,enricher=enrich)
