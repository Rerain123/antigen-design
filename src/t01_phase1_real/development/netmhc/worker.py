"""Run both unchanged DTU binaries and retain their raw channel outputs."""
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import socket
import subprocess
import time
import traceback

OUT=Path('/out')
PAN=Path('/tools/src/netMHCpan-4.2')
IIPAN=Path('/tools/src/netMHCIIpan-4.3')
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def write_json(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,sort_keys=True,allow_nan=False)


def invoke(name,argv,environment):
    started=time.monotonic()
    result=subprocess.run(argv,capture_output=True,env=environment,check=False)
    (OUT/(name+'.txt')).write_bytes(result.stdout)
    (OUT/(name+'.stderr.txt')).write_bytes(result.stderr)
    return dict(argv=argv,exit_code=result.returncode,elapsed_seconds=time.monotonic()-started,
        stdout_sha256=sha(result.stdout),stderr_sha256=sha(result.stderr))


def controlled_channel_failure(name,argv):
    stdout=b'';stderr=b'controlled native channel failure\n'
    (OUT/(name+'.txt')).write_bytes(stdout);(OUT/(name+'.stderr.txt')).write_bytes(stderr)
    return dict(argv=argv,exit_code=64,elapsed_seconds=0.0,stdout_sha256=sha(stdout),stderr_sha256=sha(stderr))


def unavailable_channel(name):
    (OUT/(name+'.txt')).write_bytes(b'')
    (OUT/(name+'.stderr.txt')).write_bytes(b'')
    return dict(argv=[],exit_code=None,elapsed_seconds=0.0,not_executed=True,
                reason='HOST_PANEL_CHANNEL_UNAVAILABLE',stdout_sha256=sha(b''),stderr_sha256=sha(b''))


def main():
    started=time.monotonic();request=json.loads(Path('/input.json').read_text(encoding='utf-8'))
    environment=dict(os.environ,TMPDIR='/tmp',LC_ALL='C',LANG='C',
        NETMHCpan=str(PAN/'Linux_x86_64'),NETMHCIIpan=str(IIPAN/'Linux_x86_64'))
    runtime=dict(python=platform.python_version(),platform=platform.platform(),machine=platform.machine(),
        network_interfaces=socket.if_nameindex(),cpu_affinity=sorted(os.sched_getaffinity(0)),
        input_json_sha256=sha(Path('/input.json').read_bytes()),input_fasta_sha256=sha(Path('/input.fasta').read_bytes()),
        versions=dict(mhc_i=(PAN/'data/version').read_text().strip(),mhc_ii=(IIPAN/'data/version').read_text().strip()),
        package_files={str(path):sha(path.read_bytes()) for path in [PAN/'data/version',PAN/'data/allelenames',
            PAN/'Linux_x86_64/bin/netMHCpan-4.2',IIPAN/'data/version',IIPAN/'data/allele.list',
            IIPAN/'Linux_x86_64/bin/NetMHCIIpan-4.3']},commands={},python_exit_code=None)
    write_json(OUT/'runtime_started.json',runtime)
    try:
        if (OUT/'result').is_dir():raise RuntimeError('controlled whole-tool failure')
        mhc_i_argv=[
            str(PAN/'Linux_x86_64/bin/netMHCpan-4.2'),'-f','/input.fasta','-a',','.join(request['mhc_i_alleles']),
            '-l','8,9,10,11,12,13,14']
        runtime['commands']['mhc_i']=(unavailable_channel('netmhcpan') if not request['mhc_i_alleles'] else controlled_channel_failure('netmhcpan',mhc_i_argv)
            if (OUT/'mhc_i_failure').is_dir() else invoke('netmhcpan',mhc_i_argv,environment))
        mhc_ii_argv=[
            str(IIPAN/'Linux_x86_64/bin/NetMHCIIpan-4.3'),'-f','/input.fasta','-a',','.join(request['mhc_ii_alleles']),
            '-length','15']
        runtime['commands']['mhc_ii']=(unavailable_channel('netmhciipan') if not request['mhc_ii_alleles'] else controlled_channel_failure('netmhciipan',mhc_ii_argv)
            if (OUT/'mhc_ii_failure').is_dir() else invoke('netmhciipan',mhc_ii_argv,environment))
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
