"""Observe the unmodified academic entry point inside an isolated container."""
import json
import os
import resource
import runpy
import socket
import sys
import time
from importlib.metadata import version
from pathlib import Path

import torch

started = time.monotonic()
report = {
    "python": sys.version,
    "packages": {name: version(name) for name in ("torch", "fair-esm", "numpy", "biopython", "matplotlib")},
    "cuda_available": torch.cuda.is_available(),
    "cpu_count": os.cpu_count(),
    "cpu_affinity": sorted(os.sched_getaffinity(0)),
    "network_interfaces": socket.if_nameindex(),
    "scientific_source_modified": False,
    "entrypoint": ["/app/predict.py", "--fasta", "/input.fasta", "--output-dir", "/out/result"],
}
Path('/out/runtime_started.json').write_text(json.dumps(report, indent=2))
sys.path.insert(0, '/app')
sys.argv = report['entrypoint']
try:
    runpy.run_path('/app/predict.py', run_name='__main__')
    report['python_exit_code'] = 0
except SystemExit as exc:
    report['python_exit_code'] = exc.code
    raise
except BaseException as exc:
    report['error_type'] = type(exc).__name__
    report['error'] = str(exc)
    report['python_exit_code'] = 1
    raise
finally:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    report.update(elapsed_seconds=time.monotonic()-started, peak_rss_kib=usage.ru_maxrss,
                  user_cpu_seconds=usage.ru_utime, system_cpu_seconds=usage.ru_stime,
                  torch_intraop_threads=torch.get_num_threads(),
                  torch_interop_threads=torch.get_num_interop_threads())
    Path('/out/runtime.json').write_text(json.dumps(report, indent=2))
