"""Offline FoldX worker: RepairPDB is mandatory before PositionScan/BuildModel."""
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import time
import traceback

try:
    from .scan_batches import plan as scan_plan, seal, seal_models
    from .parallel import execute as parallel_buildmodel
except ImportError:
    from scan_batches import plan as scan_plan, seal, seal_models
    from parallel import execute as parallel_buildmodel

OUT = Path("/out")


def filehash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


def write(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, allow_nan=False)


def run(argv, cwd, stdout_name):
    # Keep native diagnostics even if the supervisor cancels the process tree.
    # Neither the command nor its process-group ownership changes.
    stderr_name = stdout_name.rsplit(".", 1)[0] + ".stderr.txt"
    with (OUT / stdout_name).open("xb") as stdout, (OUT / stderr_name).open("xb") as stderr:
        return subprocess.run(argv, cwd=cwd, stdout=stdout, stderr=stderr)


def main():
    started = time.monotonic()
    payload = json.loads(Path("/native/payload.json").read_bytes())
    runtime = dict(
        python=platform.python_version(), network_interfaces=socket.if_nameindex(), cpu_affinity=sorted(os.sched_getaffinity(0)),
        input_sha256=filehash(Path("/input.json")), input_fasta_sha256=filehash(Path("/input.fasta")),
        native_input_sha256={p.name: filehash(p) for p in Path("/native").iterdir() if p.is_file()},
        executable_sha256=filehash(Path("/app/foldx_20270131")), mode=payload["mode"], repair_required=True,
        tool_invoked=False, commands={}, python_exit_code=None,
    )
    write("runtime_started.json", runtime)
    try:
        executable = "/app/foldx_20270131"
        if (OUT / "result").is_dir():
            raise RuntimeError("Controlled FoldX tool failure")
        if (OUT / "slow_worker").is_dir():
            time.sleep(60)
        repair_dir = OUT / "repair"; repair_dir.mkdir()
        repair_command = [executable, "--command=RepairPDB", "--pdb=target.pdb", "--pdb-dir=/native", "--output-dir=/out/repair"]
        repair = run(repair_command, "/out/repair", "repair.stdout.txt")
        runtime["commands"]["repair"] = dict(argv=repair_command, exit_code=repair.returncode)
        if repair.returncode:
            raise RuntimeError("FoldX RepairPDB failed with exit code " + str(repair.returncode))
        repaired = sorted(repair_dir.glob("*_Repair.pdb"))
        if len(repaired) != 1:
            raise RuntimeError("FoldX RepairPDB did not produce exactly one repaired PDB")
        runtime["repaired_pdb"] = repaired[0].relative_to(OUT).as_posix()
        if payload["mapping_failures"] and not (payload["mode"] == "buildmodel" and payload["variant_lines"]):
            runtime["mapping_failed"] = True
            runtime["mapping_failure_count"] = len(payload["mapping_failures"])
        else:
            runtime["mapping_failed"] = bool(payload["mapping_failures"])
            if payload["mode"] == "positionscan":
                batches=scan_plan(payload);runtime['scan_batches']=[]
                (OUT/'batches').mkdir()
                write('scan-plan.json',dict(positions_per_batch=16,batches=batches,repair_reused=True))
                for batch in batches:
                    name=f"batches/{batch['index']:04d}"
                    directory=OUT/name;directory.mkdir()
                    command=[executable,'--command=PositionScan','--pdb='+repaired[0].name,
                        '--pdb-dir=/out/repair','--positions='+','.join(batch['scan_tokens']),
                        '--output-dir=/out/'+name]
                    result=run(command,str(directory),name+'/stdout.txt')
                    record=dict(batch,argv=command,exit_code=result.returncode,archive=name+'.zip')
                    runtime['tool_invoked']=True
                    record.update(seal(directory,OUT/(name+'.zip')))
                    runtime['scan_batches'].append(record)
                    (OUT/'scan-progress.json').write_text(json.dumps(dict(completed=runtime['scan_batches'],total=len(batches))))
                    if result.returncode:
                        raise RuntimeError('FoldX batch failed: '+str(batch['index']))
                    print('N17 FoldX batch',batch['index']+1,'/',len(batches),'completed',flush=True)
            elif len(payload['variant_lines']) > 1:
                runtime['tool_invoked'] = True
                runtime['buildmodel_parallel'] = parallel_buildmodel(OUT, payload, run)
                result = subprocess.CompletedProcess([], 0)
            else:
                Path("/out/buildmodel").mkdir()
                Path("/out/buildmodel/individual_list.txt").write_text("\n".join(payload["variant_lines"]) + "\n", encoding="utf-8")
                command = [executable, "--command=BuildModel", "--pdb=" + repaired[0].name, "--pdb-dir=/out/repair", "--mutant-file=individual_list.txt", "--numberOfRuns=5", "--output-dir=/out/buildmodel"]
                result = run(command, "/out/buildmodel", "buildmodel.stdout.txt")
                runtime["commands"]["buildmodel"] = dict(argv=command, exit_code=result.returncode)
                if result.returncode==0:
                    runtime['buildmodel_archives']=seal_models(OUT/'buildmodel',len(payload['variant_lines']))
            runtime["tool_invoked"] = True
            if result.returncode:
                raise RuntimeError("FoldX " + payload["mode"] + " failed with exit code " + str(result.returncode))
        runtime["python_exit_code"] = 0
        write("observation.json", dict(status="completed" if not payload["mapping_failures"] else
            "completed_partial_mapping" if runtime["tool_invoked"] else "mapping_failed", mode=payload["mode"], repaired_pdb=runtime["repaired_pdb"], mapping_failures=payload["mapping_failures"], tool_invoked=runtime["tool_invoked"]))
    except BaseException as exc:
        runtime.update(python_exit_code=1, error=str(exc), error_type=type(exc).__name__)
        (OUT / "exception.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        runtime["elapsed_seconds"] = time.monotonic() - started
        runtime["native_output_sha256"] = {p.relative_to(OUT).as_posix(): filehash(p) for p in sorted(OUT.rglob("*")) if p.is_file()}
        write("runtime.json", runtime)


if __name__ == "__main__":
    main()
