"""Execute pinned blastp against one read-only registered local database."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import socket
import subprocess
import time
import traceback

OUT=Path('/out')
DATABASE=Path('/database')
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def write_json(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,sort_keys=True,allow_nan=False)


def executable(name):
    return shutil.which(name+'.REAL') or shutil.which(name)


def invoke(name,argv,environment):
    started=time.monotonic();run=subprocess.run(argv,capture_output=True,env=environment,check=False)
    (OUT/(name+'.txt')).write_bytes(run.stdout);(OUT/(name+'.stderr.txt')).write_bytes(run.stderr)
    return dict(argv=argv,exit_code=run.returncode,elapsed_seconds=time.monotonic()-started,
        stdout_sha256=sha(run.stdout),stderr_sha256=sha(run.stderr))


def main():
    started=time.monotonic();request=json.loads(Path('/input.json').read_text(encoding='utf-8'))
    manifest=json.loads((DATABASE/'manifest.json').read_text(encoding='utf-8'))
    blastp=executable('blastp');blastdbcmd=executable('blastdbcmd')
    environment=dict(os.environ,TMPDIR='/tmp',LC_ALL='C',LANG='C',BLASTDB='/database')
    runtime=dict(python=platform.python_version(),platform=platform.platform(),machine=platform.machine(),
        network_interfaces=socket.if_nameindex(),cpu_affinity=sorted(os.sched_getaffinity(0)),
        input_json_sha256=sha(Path('/input.json').read_bytes()),input_fasta_sha256=sha(Path('/input.fasta').read_bytes()),
        database_manifest_sha256=sha((DATABASE/'manifest.json').read_bytes()),versions={},commands={},python_exit_code=None)
    write_json(OUT/'runtime_started.json',runtime)
    try:
        if (OUT/'result').is_dir():raise RuntimeError('controlled whole-tool failure')
        if (OUT/'slow_worker').is_dir():time.sleep(30)
        if not blastp or not blastdbcmd:raise RuntimeError('BLAST+ executable unavailable')
        runtime['versions']['blastp']=subprocess.run([blastp,'-version'],capture_output=True,text=True,env=environment,check=True).stdout.splitlines()[0]
        runtime['versions']['blastdbcmd']=subprocess.run([blastdbcmd,'-version'],capture_output=True,text=True,env=environment,check=True).stdout.splitlines()[0]
        prefix='/database/'+manifest['blast']['db_prefix']
        runtime['commands']['database_info']=invoke('database-info',[blastdbcmd,'-db',prefix,'-info'],environment)
        outfmt='6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore qlen slen qcovhsp qseq sseq stitle'
        argv=[blastp,'-query','/input.fasta','-db',prefix,'-outfmt',outfmt,'-max_target_seqs','500','-max_hsps','10','-num_threads','2']
        runtime['commands']['blastp']=invoke('blast',argv,environment)
        if any(item['exit_code'] for item in runtime['commands'].values()):raise RuntimeError('native BLAST+ command failed')
        if manifest.get('schema_version')=='0.3.0':
            spec=importlib.util.spec_from_file_location('iedb_native',Path(__file__).with_name('iedb.py'))
            helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
            subjects=helper.qualifying_subjects((OUT/'blast.txt').read_text(encoding='utf-8'))
            write_json(OUT/'iedb-evidence.json',helper.read_evidence(DATABASE,subjects,manifest))
        runtime['python_exit_code']=0
    except BaseException as exc:
        runtime.update(python_exit_code=1,error_type=type(exc).__name__,error=str(exc))
        (OUT/'exception.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
    finally:
        usage=resource.getrusage(resource.RUSAGE_SELF)
        runtime.update(elapsed_seconds=time.monotonic()-started,max_rss_kib=usage.ru_maxrss,
            native_output_sha256={p.name:sha(p.read_bytes()) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='runtime.json'})
        write_json(OUT/'runtime.json',runtime)


if __name__=='__main__':main()
