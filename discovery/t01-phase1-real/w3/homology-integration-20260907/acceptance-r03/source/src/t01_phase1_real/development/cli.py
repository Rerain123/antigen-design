"""Single trusted-local entry for task admission, lifecycle and immutable results."""
import argparse
from pathlib import Path

from ..common import TOOL as ENGINEERING, RuntimeFault, encode, profile
from ..files import read_locked
from .policy import TOOL, registered_profile
from .runtime import Runtime
from .structure import policy as structure
from .bepipred import policy as bepipred
from .netmhc import policy as netmhc
from .blast import policy as blast
from .epitope_map import policy as epitope_map
from .glycosylation import policy as glycosylation
from .homology import policy as homology


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True)
    p.add_argument('--blast-database-root',help='Trusted local root containing registered N03 database-ID directories')
    p.add_argument('--homology-database-root',help='Trusted registered N08 local data root')
    sub=p.add_subparsers(dest='operation',required=True)
    sub.add_parser('profile')
    c=sub.add_parser('create-run');c.add_argument('--key',required=True)
    c=sub.add_parser('stage');c.add_argument('--run-id',required=True);c.add_argument('--input',required=True)
    c.add_argument('--tool',choices=[ENGINEERING,TOOL,structure.TOOL,bepipred.TOOL,netmhc.TOOL,blast.TOOL,epitope_map.TOOL,glycosylation.TOOL,homology.TOOL],default=ENGINEERING)
    for name in ['submit','control']:
        c=sub.add_parser(name);c.add_argument('--input',required=True)
    for name in ['get','dispatch','cancel','retry','recover','wait','events','execution','result']:
        c=sub.add_parser(name);c.add_argument('--job-id',required=True)
        if name in ['cancel','retry']:c.add_argument('--key',required=True)
        if name=='wait':c.add_argument('--seconds',type=int,default=60)
    c=sub.add_parser('artifact');c.add_argument('--job-id',required=True);c.add_argument('--artifact-id',required=True);c.add_argument('--output',required=True)
    c=sub.add_parser('deeptmhmm',help='Atomically submit a sequence and optionally run/wait')
    group=c.add_mutually_exclusive_group(required=True);group.add_argument('--sequence');group.add_argument('--input',help='Exact JSON request file')
    c.add_argument('--user-id',default='local-input');c.add_argument('--timeout',type=int,default=900)
    c.add_argument('--key',required=True);c.add_argument('--run',action='store_true');c.add_argument('--wait',type=int,default=0)
    c=sub.add_parser('bepipred',help='Submit sequence for offline BepiPred 3.0 raw scores')
    group=c.add_mutually_exclusive_group(required=True);group.add_argument('--sequence');group.add_argument('--input',help='Exact JSON request file')
    c.add_argument('--user-id',default='local-input');c.add_argument('--timeout',type=int,default=900)
    c.add_argument('--key',required=True);c.add_argument('--run',action='store_true');c.add_argument('--wait',type=int,default=0)
    c=sub.add_parser('netmhc',help='Submit N05 with explicit MHC-I and MHC-II alleles; host panel inference remains closed')
    group=c.add_mutually_exclusive_group(required=True);group.add_argument('--sequence');group.add_argument('--input',help='Exact JSON request file')
    c.add_argument('--user-id',default='local-input');c.add_argument('--host')
    c.add_argument('--mhc-i-allele',action='append');c.add_argument('--mhc-ii-allele',action='append')
    c.add_argument('--timeout',type=int,default=900);c.add_argument('--key',required=True)
    c.add_argument('--run',action='store_true');c.add_argument('--wait',type=int,default=0)
    c=sub.add_parser('blast',help='Run N03 blastp against an operator-registered local protein database')
    group=c.add_mutually_exclusive_group(required=True);group.add_argument('--sequence');group.add_argument('--input',help='Exact JSON request file')
    c.add_argument('--user-id',default='local-input');c.add_argument('--database-id');c.add_argument('--database-manifest-sha256')
    c.add_argument('--identity-min',type=float,default=70.0);c.add_argument('--query-coverage-min',type=float,default=80.0)
    c.add_argument('--timeout',type=int,default=900);c.add_argument('--key',required=True)
    c.add_argument('--run',action='store_true');c.add_argument('--wait',type=int,default=0)
    c=sub.add_parser('epitope-map',help='Run N06/S-19 from registered BepiPred and NetMHC result artifacts')
    group=c.add_mutually_exclusive_group(required=True);group.add_argument('--sequence');group.add_argument('--input',help='Exact JSON request file')
    c.add_argument('--user-id',default='local-input');c.add_argument('--bepipred-job-id');c.add_argument('--netmhc-job-id')
    c.add_argument('--timeout',type=int,default=5);c.add_argument('--key',required=True)
    c.add_argument('--run',action='store_true');c.add_argument('--wait',type=int,default=0)
    c=sub.add_parser('glycosylation',help='Run N07/S-12 local sequon scan; hotspot context defaults to explicitly not provided')
    group=c.add_mutually_exclusive_group(required=True);group.add_argument('--sequence');group.add_argument('--input',help='Exact JSON request file')
    c.add_argument('--user-id',default='local-input');c.add_argument('--n06-job-id');c.add_argument('--timeout',type=int,default=5)
    c.add_argument('--key',required=True);c.add_argument('--run',action='store_true');c.add_argument('--wait',type=int,default=0)
    c=sub.add_parser('homology',help='Run N08 offline homolog collection, MSA and conservation')
    c.add_argument('--input',required=True);c.add_argument('--key',required=True)
    c.add_argument('--run',action='store_true');c.add_argument('--wait',type=int,default=0)
    c=sub.add_parser('structure',help='Submit sequence, host and exact local PDB/mmCIF bytes')
    c.add_argument('--structure-file',required=True)
    group=c.add_mutually_exclusive_group(required=True);group.add_argument('--sequence');group.add_argument('--input',help='Exact metadata JSON file')
    c.add_argument('--host');c.add_argument('--format',choices=['PDB','CIF','MMCIF'],default='PDB')
    c.add_argument('--source',choices=['unknown','experimental','predicted'],default='unknown');c.add_argument('--source-note')
    c.add_argument('--model-index',type=int);c.add_argument('--chain',default='AUTO');c.add_argument('--context-chain',action='append')
    c.add_argument('--timeout',type=int,default=60);c.add_argument('--key',required=True)
    c.add_argument('--run',action='store_true');c.add_argument('--wait',type=int,default=0)
    a=p.parse_args(argv)
    try:
        rt=Runtime(a.root,blast_database_root=a.blast_database_root,homology_database_root=a.homology_database_root);op=a.operation
        if op=='profile':value=dict(engineering=profile(),deeptmhmm=registered_profile(),local_structure=structure.registered_profile(),
            bepipred=bepipred.registered_profile(),netmhc=netmhc.registered_profile(),epitope_map=epitope_map.registered_profile(),
            blast=blast.registered_profile(),homology=homology.registered_profile(),homology_rules=homology.registered_rules(),
            epitope_map_rules=epitope_map.registered_rules(),glycosylation=glycosylation.registered_profile(),
            glycosylation_rules=glycosylation.registered_rules(),production_enabled=False)
        elif op=='structure':
            if a.wait:ensure_wait(a.wait)
            raw=read_locked(a.input,32768) if a.input else encode(dict(protein_sequence=a.sequence,host_species=a.host,
                structure_name=Path(a.structure_file).name,declared_format=a.format,source_declaration=dict(kind=a.source,note=a.source_note),
                selection=dict(model_index=a.model_index,chain_selector=a.chain),context_chain_ids=a.context_chain,timeout_seconds=a.timeout))
            structure.metadata(raw)
            value=rt.submit_structure(raw,a.key,read_locked(a.structure_file,structure.MAX_STRUCTURE_BYTES))
            if a.run:value=rt.dispatch(value['job_id'])
            if a.wait:value=rt.wait(value['job_id'],a.wait)
            if any(r['role'] in ('result','diagnostic') for r in value['artifacts']):value=dict(job=value,result=rt.result(value['job_id']))
        elif op in ('deeptmhmm','bepipred','netmhc','blast','epitope-map','glycosylation','homology'):
            if a.wait:ensure_wait(a.wait)
            if a.input:
                if op=='epitope-map' and (a.bepipred_job_id or a.netmhc_job_id):
                    raise RuntimeFault('INVALID_REQUEST','N06 job IDs cannot be combined with an exact input file')
                if op=='glycosylation' and a.n06_job_id:
                    raise RuntimeFault('INVALID_REQUEST','N07 job ID cannot be combined with an exact input file')
                raw=read_locked(a.input,65536)
            elif op=='netmhc':raw=encode(dict(protein_sequence=a.sequence,user_sequence_id=a.user_id,host_species=a.host,
                mhc_i_alleles=a.mhc_i_allele,mhc_ii_alleles=a.mhc_ii_allele,timeout_seconds=a.timeout))
            elif op=='blast':raw=encode(dict(protein_sequence=a.sequence,user_sequence_id=a.user_id,database_id=a.database_id,
                database_manifest_sha256=a.database_manifest_sha256,thresholds=dict(identity_percent_min=a.identity_min,
                    query_coverage_percent_min=a.query_coverage_min),timeout_seconds=a.timeout))
            elif op=='epitope-map':
                bepi=rt.source_input(a.bepipred_job_id,bepipred.TOOL) if a.bepipred_job_id else dict(state='not_provided',artifact=None,reason_code=None)
                mhc=rt.source_input(a.netmhc_job_id,netmhc.TOOL) if a.netmhc_job_id else dict(state='not_provided',artifact=None,reason_code=None)
                raw=encode(dict(protein_sequence=a.sequence,user_sequence_id=a.user_id,bepipred_input=bepi,netmhc_input=mhc,
                    blast_input=dict(state='not_executed',reason_code='OI_028_TARGET_DATABASE_NOT_AVAILABLE'),timeout_seconds=a.timeout))
            elif op=='glycosylation':
                hotspot=rt.n06_hotspot_input(a.n06_job_id,a.sequence) if a.n06_job_id else dict(
                    state='not_provided',hotspots=None,source=None,reason_code=None)
                raw=encode(dict(protein_sequence=a.sequence,user_sequence_id=a.user_id,hotspot_input=hotspot,timeout_seconds=a.timeout))
            else:raw=encode(dict(protein_sequence=a.sequence,user_sequence_id=a.user_id,timeout_seconds=a.timeout))
            worker={ 'deeptmhmm':TOOL,'bepipred':bepipred.TOOL,'netmhc':netmhc.TOOL,'blast':blast.TOOL,
                'epitope-map':epitope_map.TOOL,'glycosylation':glycosylation.TOOL,'homology':homology.TOOL }[op]
            value=rt.submit_sequence(raw,a.key,worker)
            if a.run:value=rt.dispatch(value['job_id'])
            if a.wait:
                ensure_wait(a.wait);value=rt.wait(value['job_id'],a.wait)
            if any(r['role'] in ('result','diagnostic') for r in value['artifacts']):
                value=dict(job=value,result=rt.result(value['job_id']))
        elif op=='create-run':value=rt.create_run(a.key)
        elif op=='stage':value=rt.stage_request(a.run_id,read_locked(a.input,65536),a.tool)
        elif op in ('submit','control'):value=getattr(rt,op)(read_locked(a.input,65536))
        elif op in ('cancel','retry'):value=rt.control(encode(dict(contract_version='0.1.0',operation=op,job_id=a.job_id,idempotency_key=a.key)))
        elif op=='wait':ensure_wait(a.seconds);value=rt.wait(a.job_id,a.seconds)
        elif op=='artifact':
            raw=rt.artifact_bytes(a.job_id,a.artifact_id)
            with Path(a.output).open('xb') as f:f.write(raw)
            value=dict(artifact_id=a.artifact_id,size_bytes=len(raw),output=str(Path(a.output).absolute()))
        else:value=getattr(rt,op)(a.job_id)
        print(encode(value).decode());return 0
    except RuntimeFault as exc:print(encode(exc.envelope()).decode());return 20
    except OSError:print(encode(RuntimeFault('ASSET_MISSING','Local storage/process operation failed').envelope()).decode());return 21


def ensure_wait(seconds):
    if not 1<=seconds<=1000:raise RuntimeFault('INVALID_REQUEST','Wait must be 1..1000 seconds')
