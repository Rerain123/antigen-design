from ...common import decode,encode,ensure
from ..design_backend.source import sources as registered
from . import policy

def native(rt,src,value):
    out={}
    for row in value['raw_artifacts']:
        ensure(row['path'] not in out,'OUTPUT_INVALID','Duplicate native source path')
        out[row['path']]=rt.artifact_bytes(src['job_id'],row['artifact']['artifact_id'])
    return out

def enrich(rt,db,body,files,values,receipts):
    structure=body['upstream']['structure']
    for name in ('foldx','thermompnn'):
        if 'input/'+name+'-request.json' not in files:continue
        req=decode(files['input/'+name+'-request.json'])
        ensure(structure is not None and req['structure_artifact']==structure['artifact'],
            'OUTPUT_INVALID','Scan does not bind the exact declared WT structure')
        if name=='foldx':ensure(req['mode']=='positionscan','INVALID_REQUEST','N17 requires WT PositionScan, never BuildModel scores')
        if name not in values:continue
        if name=='foldx':
            from ..foldx.source import sources as prepare
            from ..foldx.result import parse
        else:
            from ..thermompnn.source import sources as prepare
            from ..thermompnn.result import validate_observation as parse
        raw=native(rt,body['upstream'][name],values[name]);prepared,receipt=prepare(rt,db,req)
        ensure(all(raw.get(k)==v for k,v in prepared.items()) and raw['input.json']==files['input/'+name+'-request.json'],
            'HASH_MISMATCH','WT scan original inputs differ')
        parsed=parse(req,raw)
        ensure(parsed['rows']==values[name]['ddg_results'] if name=='foldx' else parsed==values[name]['scan'],
            'OUTPUT_INVALID','WT scan differs from native revalidation')
        ensure(receipt==values[name]['source_receipt'],'OUTPUT_INVALID','WT scan source receipt differs')
        receipts[name]['structure']=receipt
        files['input/'+name+'-verified-scan.json']=encode(parsed)
    if 'design_audit' in values:
        from ..design_backend.source import sources
        from ..design_backend.compute import evaluate
        req=decode(files['input/design_audit-request.json'])
        ensure(req['upstream']['structure']==structure,'OUTPUT_INVALID','Permission audit and WT reference structure differ')
        nf,_,nr=sources(rt,db,req);expected=evaluate(req,nf)
        ensure(values['design_audit']['audit']==expected,'OUTPUT_INVALID','Permission audit differs from original source')
        receipts['design_audit']['upstream']=nr
        protected={r['position'] for r in expected['permissions']['per_residue'] if r['design_permission'] in ('FIXED','RESTRICTED')}
        for name in ('foldx','thermompnn'):
            key='input/'+name+'-request.json'
            if key not in files:continue
            scan=decode(files[key]);excluded=set(scan['fixed_positions'] if name=='foldx' else scan['excluded_positions'])
            ensure(not (set(scan['scan_positions'])-excluded)&protected,
                   'OUTPUT_INVALID','WT scan includes FIXED/RESTRICTED positions from verified audit')

def sources(rt,db,body):return registered(rt,db,body,producers=policy.PRODUCERS,enricher=enrich)
