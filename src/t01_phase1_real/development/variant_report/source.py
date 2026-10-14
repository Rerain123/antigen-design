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
    if 'validation_source' in body:
        from ..workflow.validation import verified_fact
        context=body['validation_source'];fact=verified_fact(rt,context['workflow_job_id'],context['node'])
        ensure(fact['source_jobs']['design_audit']==body['upstream']['design_audit'],
               'OUTPUT_INVALID','S28 validation belongs to a different audit')
        files['input/s28-validation.json']=encode(fact)
    if body.get('n13_source'):
        from ..epitope_protection import policy as n13
        def check(rt,db,request,extra,vals,recs):
            req=decode(extra['input/n13-request.json'])
            # N13 recursively verifies N11/N12 and never consumes an N15 report or FoldX.
            from ..epitope_protection.source import sources as n13_sources
            from ..epitope_protection.compute import evaluate
            nf,_,nr=n13_sources(rt,db,req)
            ensure(req['protein_sequence']==body['protein_sequence'] and
                req['upstream']['design_audit']==body['upstream']['design_audit'],
                'OUTPUT_INVALID','N13 belongs to a different N11/N12 variant batch')
            if body['upstream']['foldx'] is not None:
                n13_job=rt._job(db,body['n13_source']['job_id'])
                foldx_job=rt._job(db,body['upstream']['foldx']['job_id'])
                ensure(n13_job['run_id']==foldx_job['run_id'] and n13_job['finished_at'] is not None
                    and foldx_job['started_at'] is not None and n13_job['finished_at']<=foldx_job['started_at'],
                    'OUTPUT_INVALID','N14 must start after the N13 paired result')
            if 'n13' in vals:
                ensure(vals['n13']['protection']==evaluate(req,nf),'OUTPUT_INVALID','N13 observations differ from paired sources')
            recs['n13']['paired_sources']=nr
        extra,vals,recs=registered_sources(rt,db,dict(protein_sequence=body['protein_sequence'],upstream={'n13':body['n13_source']}),
            producers={'n13':n13.TOOL},enricher=check)
        files.update(extra);values.update(vals);receipts.update(recs)
        files['input/source-receipts.json']=encode(receipts)
    if 'm1_test' in body:
        from .m1 import sources as m1_sources
        m1_sources(rt,db,body,files,values,receipts)
    if 'n14_source' in body:
        from ..workflow.stability_pool import verify_report
        files['input/n14-pool.json']=encode(verify_report(rt,db,body))
        from ..workflow.candidate_developability import report_sources
        from .compute import preselection_rows
        complete=report_sources(rt,db,body,preselection_rows(body,files,values))
        if complete is not None:files['input/candidate-developability.json']=encode(complete)
    return files,values,receipts
