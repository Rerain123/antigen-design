"""Recursively verify original producers and replay native FoldX identity/aggregation."""
from ...common import decode,encode,ensure,sha
from ..design_backend.source import sources as registered_sources
from ..design_backend.compute import evaluate as design_evaluate
from ..design_backend.policy import request as design_request
from ..foldx import policy as foldx
from ..foldx.source import sources as prepare_foldx
from ..foldx.result import parse as parse_foldx
from . import policy

def enrich(rt,db,body,files,values,receipts):
    def originals(name):
        native={}
        for item in values[name]['raw_artifacts']:
            ensure(item['path'] not in native,'OUTPUT_INVALID','Duplicate native path')
            native[item['path']]=rt.artifact_bytes(body['upstream'][name]['job_id'],item['artifact']['artifact_id'])
        return native
    if 'design_audit' in values:
        req=design_request(files['input/design_audit-request.json'])
        upstream,_,nested=registered_sources(rt,db,req)
        expected=design_evaluate(req,upstream)
        ensure(expected==values['design_audit']['audit'],'OUTPUT_INVALID','Historical design audit differs from source recomputation')
        receipts['design_audit']['upstream']=nested
        native=originals('design_audit')
        ensure(decode(native['output/design-audit.json'])==expected,'OUTPUT_INVALID','Native design audit differs')
        for name,data in upstream.items():files['input/design/'+name]=data
        files['input/verified-design.json']=encode(expected)
    if 'input/foldx-request.json' in files:
        req=foldx.request(files['input/foldx-request.json'])
        ensure(req['mode']=='buildmodel','INVALID_REQUEST','N14 variant scores require BuildModel; single-point scans cannot be summed')
        if 'design_audit' in values:
            design_req=decode(files['input/design_audit-request.json'])
            ensure(req['structure_artifact']==design_req['upstream']['structure']['artifact'],
                'OUTPUT_INVALID','FoldX and N11 must bind the exact same WT structure artifact')
    if 'foldx' in values:
        native=originals('foldx');prepared,receipt=prepare_foldx(rt,db,req)
        ensure(all(native.get(n)==data for n,data in prepared.items()),'HASH_MISMATCH','FoldX original structure/mapping/payload no longer matches source')
        ensure(native['input.json']==files['input/foldx-request.json'],'HASH_MISMATCH','FoldX executed request differs')
        parsed=parse_foldx(req,native)
        ensure(parsed['rows']==values['foldx']['variant_ddg'] and parsed['status']==values['foldx']['status']
            and values['foldx']['source_receipt']==receipt,'OUTPUT_INVALID','FoldX source/aggregates differ from native outputs')
        receipts['foldx']['structure']=receipt
        from .structures import validate as validate_structures
        receipts['foldx']['pdb_validation']=validate_structures(req,native)
        # Preserve repair, mapping and all five mutant/WT PDBs in the report evidence.
        for name,data in native.items():files['input/foldx-native/'+name]=data
        if 'design_audit' in values:
            ensure(native['input/structure-original.bin']==files['input/design/input/structure-original.bin'],
                'HASH_MISMATCH','FoldX and N11 WT structure bytes differ')
    # Validate explicit joins at admission as well as calculation/publication.
    from .compute import variants
    variants(body,files,values)

def sources(rt,db,body):
    files,values,receipts=registered_sources(rt,db,body,producers=policy.PRODUCERS,enricher=enrich)
    if body.get('n13_source'):
        from ..epitope_protection import policy as n13
        def check(rt,db,request,extra,vals,recs):
            req=decode(extra['input/n13-request.json'])
            # No recursion: N13 only consumes reports without N13 sources.
            from ..epitope_protection.source import sources as n13_sources
            from ..epitope_protection.compute import evaluate
            nf,_,nr=n13_sources(rt,db,req)
            base_req=decode(nf['input/base_report-request.json'])
            ensure(all(base_req[k]==body[k] for k in ('protein_sequence','upstream','variant_source','foldx_bindings')),
                'OUTPUT_INVALID','N13 belongs to a different report variant batch')
            if 'n13' in vals:
                ensure(vals['n13']['protection']==evaluate(req,nf),'OUTPUT_INVALID','N13 observations differ from paired sources')
            recs['n13']['paired_sources']=nr
        extra,vals,recs=registered_sources(rt,db,dict(protein_sequence=body['protein_sequence'],upstream={'n13':body['n13_source']}),
            producers={'n13':n13.TOOL},enricher=check)
        files.update(extra);values.update(vals);receipts.update(recs)
        files['input/source-receipts.json']=encode(receipts)
    return files,values,receipts
