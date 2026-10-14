"""Offline official ThermoMPNN SSM through a recorded project batch adapter."""
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time
import traceback


OUT = Path("/out")


def filehash(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            value.update(block)
    return value.hexdigest()


def write(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)


def main():
    started = time.monotonic()
    payload = json.loads(Path("/native/payload.json").read_bytes())
    runtime = dict(
        python=platform.python_version(),
        network_interfaces=socket.if_nameindex(),
        cpu_affinity=sorted(os.sched_getaffinity(0)),
        input_sha256=filehash(Path("/input.json")),
        input_fasta_sha256=filehash(Path("/input.fasta")),
        native_input_sha256={path.name: filehash(path) for path in Path("/native").iterdir() if path.is_file()},
        source_sha256={path.relative_to("/upstream").as_posix(): filehash(path) for path in sorted(Path("/upstream").rglob("*")) if path.is_file()},
        official_source_modified=False,
        official_entrypoint="analysis/custom_inference.py",
        threshold_parameter=None,
        complete_output_strategy="official custom_inference unfiltered 20-AA SSM plus parser coverage check",
        tool_invoked=False,
        model_loaded_by_official_cli=False,
        python_exit_code=None,
        commands={},
    )
    write("runtime_started.json", runtime)
    try:
        import Bio
        import numpy as np
        import omegaconf
        import pandas
        import pytorch_lightning
        import sklearn
        import scipy
        import torch
        import torchmetrics

        runtime.update(
            torch=torch.__version__,
            numpy=np.__version__,
            cuda=torch.version.cuda,
            pandas=pandas.__version__,
            biopython=Bio.__version__,
            omegaconf=omegaconf.__version__,
            pytorch_lightning=pytorch_lightning.__version__,
            torchmetrics=torchmetrics.__version__,
            scikit_learn=sklearn.__version__,
            scipy=scipy.__version__,
            gpu_available=torch.cuda.is_available(),
        )
        if not torch.cuda.is_available():
            raise RuntimeError("Registered CUDA device unavailable; no CPU fallback")
        runtime.update(
            gpu_name=torch.cuda.get_device_name(0),
            gpu_allocation_policy="scheduler-assigned-exclusive-v1",
            gpu_count=torch.cuda.device_count(),
            gpu_capability=list(torch.cuda.get_device_capability(0)),
        )
        if (OUT / "result").is_dir():
            raise RuntimeError("Controlled ThermoMPNN tool failure")
        if (OUT / "slow_worker").is_dir():
            time.sleep(60)
        if len(payload["chain_sequences"]) > 1:
            write(
                "observation.json",
                dict(
                    status="skipped_multichain",
                    reason_code="R39_THERMOMPNN_MONOMER_ONLY",
                    protein_chain_count=len(payload["chain_sequences"]),
                    target_chain=payload["target_chain"],
                    tool_invoked=False,
                ),
            )
        else:
            help_argv = [sys.executable, "-B", "/app/analysis/custom_inference.py", "--help"]
            helped = subprocess.run(help_argv, cwd="/app", capture_output=True, check=True)
            (OUT / "native-help.txt").write_bytes(helped.stdout)
            (OUT / "native-help.stderr.txt").write_bytes(helped.stderr)
            runtime["threshold_parameter"] = b"--threshold" in helped.stdout
            runtime["commands"]["help"] = dict(argv=help_argv, exit_code=helped.returncode)
            native_out = OUT / "native"
            native_out.mkdir()
            adapter=Path(__file__).with_name('batch_adapter.py')
            runtime['batch_adapter']=dict(mode='WT_EMBEDDING_MUTATION_BATCH_V1',sha256=filehash(adapter),
                mutations_per_batch=320,official_files_modified=False)
            argv = [
                sys.executable,
                "-B",
                str(adapter),
                "--pdb",
                "/native/target.pdb",
                "--chain",
                payload["target_chain"],
                "--model_path",
                "/app/models/thermoMPNN_default.pt",
                "--out_dir",
                "/out/native",
            ]
            runtime["commands"]["scan"] = dict(argv=argv, execution="official_cli_with_project_batch_adapter")
            completed = subprocess.run(argv, cwd="/app", capture_output=True)
            (OUT / "official.stdout.txt").write_bytes(completed.stdout)
            (OUT / "official.stderr.txt").write_bytes(completed.stderr)
            runtime["commands"]["scan"]["exit_code"] = completed.returncode
            runtime["tool_invoked"] = True
            runtime["model_loaded_by_official_cli"] = completed.returncode == 0
            if completed.returncode:
                raise RuntimeError("Official ThermoMPNN CLI failed with exit code " + str(completed.returncode))
            expected = native_out / "ThermoMPNN_inference_target.csv"
            if not expected.is_file():
                raise RuntimeError("Official ThermoMPNN CSV is missing")
            write(
                "observation.json",
                dict(
                    status="predicted",
                    target_chain=payload["target_chain"],
                    protein_chain_count=1,
                    native_csv="native/ThermoMPNN_inference_target.csv",
                    native_csv_sha256=filehash(expected),
                    tool_invoked=True,
                ),
            )
        runtime["python_exit_code"] = 0
    except BaseException as exc:
        runtime.update(python_exit_code=1, error=str(exc), error_type=type(exc).__name__)
        (OUT / "exception.txt").write_text(traceback.format_exc())
        raise
    finally:
        runtime["elapsed_seconds"] = time.monotonic() - started
        runtime["native_output_sha256"] = {
            path.relative_to(OUT).as_posix(): filehash(path)
            for path in sorted(OUT.rglob("*"))
            if path.is_file()
        }
        write("runtime.json", runtime)


if __name__ == "__main__":
    main()

