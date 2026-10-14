"""Execute this development campaign in fresh, network-disabled local containers."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

BATCH = Path(__file__).resolve().parent
IMAGE = "t01-freesasa-g0:2.2.1-20260905"


def fingerprint(path):
    data = path.read_bytes()
    return {"path": path.relative_to(BATCH).as_posix(), "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}


def main():
    result_path = BATCH / "campaign_result.json"
    if result_path.exists() or any((BATCH / "runs").iterdir()):
        raise SystemExit("This batch already has evidence; create a new batch for another campaign")
    image_info = json.loads(subprocess.check_output(["docker", "image", "inspect", IMAGE], text=True))[0]
    image_id = image_info["Id"]
    environment = {"image_id": image_id, "image_tag": IMAGE, "architecture": image_info["Architecture"],
                   "os": image_info["Os"], "created": image_info["Created"],
                   "docker_server_version": subprocess.check_output(["docker", "version", "--format", "{{.Server.Version}}"], text=True).strip(),
                   "docker_endpoint": subprocess.check_output(["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], text=True).strip()}
    if environment["docker_endpoint"] != "npipe:////./pipe/dockerDesktopLinuxEngine":
        raise SystemExit("This campaign is only authorized for the inspected local Docker Desktop engine")
    (BATCH / "environment" / "docker.json").write_text(json.dumps(environment, indent=2) + "\n")
    cases = [("native-mmcif", "native", "1UBQ.cif"),
             ("converted-pdb", "cif-to-pdb", "1UBQ.cif"),
             ("converted-pdb-repeat", "cif-to-pdb", "1UBQ.cif"),
             ("biopython-mmcif", "biopython", "1UBQ.cif"),
             ("native-icode", "native", "partial-icode.pdb"),
             ("biopython-icode", "biopython", "partial-icode.pdb"),
             ("invalid-pdb", "native", "invalid.pdb")]
    records = []
    for case_id, mode, input_name in cases:
        case_dir = BATCH / "runs" / case_id
        case_dir.mkdir()
        container_name = "t01-freesasa-probe-" + uuid.uuid4().hex[:12]
        command = ["docker", "run", "--rm", "--name", container_name, "--network", "none", "--read-only",
                   "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--cpus", "2", "--memory", "1g", "--pids-limit", "64",
                   "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
                   "--mount", f"type=bind,source={BATCH / 'inputs'},target=/input,readonly",
                   "--mount", f"type=bind,source={BATCH / 'probe_raw.py'},target=/probe_raw.py,readonly",
                   "--mount", f"type=bind,source={case_dir},target=/out",
                   image_id, "python", "-B", "/probe_raw.py", "--input", "/input/" + input_name,
                   "--mode", mode, "--output-dir", "/out/result"]
        start = datetime.now(timezone.utc).isoformat()
        timer = time.perf_counter()
        timed_out = False
        try:
            process = subprocess.run(command, capture_output=True, timeout=60)
            stdout, stderr, code = process.stdout, process.stderr, process.returncode
        except subprocess.TimeoutExpired as error:
            timed_out = True
            stdout, stderr, code = error.stdout or b"", error.stderr or b"", None
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=20)
        (case_dir / "stdout.txt").write_bytes(stdout)
        (case_dir / "stderr.txt").write_bytes(stderr)
        record = {"case_id": case_id, "command": command, "started_at": start,
                  "finished_at": datetime.now(timezone.utc).isoformat(), "elapsed_seconds": time.perf_counter() - timer,
                  "exit_code": code, "timed_out": timed_out,
                  "artifacts": [fingerprint(p) for p in sorted(case_dir.rglob('*')) if p.is_file()]}
        records.append(record)
        print(json.dumps({"case": case_id, "exit_code": code, "timed_out": timed_out}), flush=True)
    # Preserve the install/source hashes and native package versions from this exact image.
    for source, target in (("/opt/pip-install-report.json", "pip-install-report.json"),
                           ("/opt/python-freeze.txt", "python-freeze.txt"), ("/opt/os-packages.txt", "os-packages.txt")):
        data = subprocess.check_output(["docker", "run", "--rm", "--network", "none", "--read-only", image_id, "cat", source], timeout=30)
        (BATCH / "environment" / target).write_bytes(data)
    result = {"scope": "LOCAL_DOCKER_RAW_FREESASA_G0_PROBE_NOT_TARGET_ACCEPTANCE", "created_at": datetime.now(timezone.utc).isoformat(),
              "image_id": image_id, "case_count": len(records), "cases": records,
              "input_and_program_files": [fingerprint(p) for p in [BATCH/'probe_raw.py', BATCH/'run_local.py',
                    *sorted((BATCH/'inputs').iterdir()), *sorted((BATCH/'environment').iterdir())] if p.is_file()],
              "scientific_acceptance": "NOT_RUN", "g1": "NOT_RUN", "production_status": "NOT_DEPLOYED"}
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
