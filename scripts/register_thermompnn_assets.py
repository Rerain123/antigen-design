"""One-time registration of the pinned official ThermoMPNN tree and image."""
from pathlib import Path
import hashlib
import json
import subprocess


REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / ".tmp/thermompnn-official-2b04fd"
PACKAGE = REPO / "var/t01-phase1-real/tool-assets/thermompnn-2b04fd370e39"
EVIDENCE = REPO / "discovery/t01-phase1-real/w6/stability-assets-20260908"
REGISTRY = REPO / "src/t01_phase1_real/development/thermompnn/assets.json"
COMMIT = "2b04fd370e399911b1fa5848112cc9013f084110"
IMAGE = "sha256:3cbd3c12b792a8b344347e6e9171d03deb7c5a115a6c4b8af27b84847dfdd847"
FILES = (
    "LICENSE",
    "README.md",
    "cache.py",
    "datasets.py",
    "local.yaml",
    "model_utils.py",
    "protein_mpnn_utils.py",
    "train_thermompnn.py",
    "transfer_model.py",
    "analysis/SSM.py",
    "analysis/custom_inference.py",
    "analysis/thermompnn_benchmarking.py",
    "images/SVG/thermoMPNN_scheme.svg",
    "models/thermoMPNN_default.pt",
    "vanilla_model_weights/v_48_020.pt",
)


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            value.update(block)
    return value.hexdigest()


def git(*args):
    result = subprocess.run(
        ["git", "-c", f"safe.directory={SOURCE.as_posix()}", "-C", str(SOURCE), *args],
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def git_blob(sha1):
    return subprocess.run(
        ["git", "-c", f"safe.directory={SOURCE.as_posix()}", "-C", str(SOURCE), "cat-file", "blob", sha1],
        capture_output=True,
        check=True,
    ).stdout


def main():
    assert git("rev-parse", "HEAD").strip() == COMMIT
    tree = {}
    for line in git("ls-tree", "-r", "-l", "HEAD").splitlines():
        metadata, name = line.split("\t", 1)
        _, kind, blob, size = metadata.split()
        tree[name] = {"kind": kind, "blob": blob, "bytes": int(size)}
    assert not PACKAGE.exists() and not REGISTRY.exists()
    for name in FILES:
        item = tree[name]
        raw = git_blob(item["blob"])
        assert item["kind"] == "blob" and len(raw) == item["bytes"]
        raw_sha1 = hashlib.sha1(b"blob " + str(item["bytes"]).encode() + b"\0" + raw).hexdigest()
        assert raw_sha1 == item["blob"]
        target = PACKAGE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    runtime_config = b'{"data_loc":{},"platform":{"accel":"gpu","cache_dir":"/tmp/thermompnn-cache","thermompnn_dir":"/app"}}'
    (PACKAGE / "runtime-local.yaml").write_bytes(runtime_config)

    image = json.loads(subprocess.run(
        ["docker", "image", "inspect", IMAGE], capture_output=True, check=True
    ).stdout)[0]
    assert image["Id"] == IMAGE and image["Architecture"] == "amd64" and image["Os"] == "linux"
    environment_raw = subprocess.run(
        [
            "docker", "run", "--rm", "--network", "none", "--gpus", "device=0",
            "--entrypoint", "python", IMAGE, "-c",
            "import json,platform,socket,torch,pandas,Bio,omegaconf,pytorch_lightning,torchmetrics,sklearn,scipy;"
            "print(json.dumps(dict(python=platform.python_version(),torch=torch.__version__,cuda=torch.version.cuda,"
            "gpu_available=torch.cuda.is_available(),gpu_name=torch.cuda.get_device_name(0),"
            "gpu_capability=list(torch.cuda.get_device_capability(0)),pandas=pandas.__version__,"
            "biopython=Bio.__version__,omegaconf=omegaconf.__version__,pytorch_lightning=pytorch_lightning.__version__,"
            "torchmetrics=torchmetrics.__version__,scikit_learn=sklearn.__version__,scipy=scipy.__version__,"
            "network_interfaces=socket.if_nameindex()),sort_keys=True))",
        ],
        capture_output=True,
        check=True,
    ).stdout
    environment = json.loads(environment_raw)
    assert environment["gpu_available"] is True and environment["network_interfaces"] == [[1, "lo"]]

    registered = []
    for name in FILES:
        path = PACKAGE / name
        registered.append({
            "path": path.relative_to(REPO).as_posix(),
            "package_path": name,
            "upstream_path": name,
            "bytes": path.stat().st_size,
            "sha256": digest(path),
            "git_blob_sha1": tree[name]["blob"],
        })
    registered.append({
        "path": (PACKAGE / "runtime-local.yaml").relative_to(REPO).as_posix(),
        "package_path": "runtime-local.yaml",
        "upstream_path": None,
        "bytes": len(runtime_config),
        "sha256": hashlib.sha256(runtime_config).hexdigest(),
        "git_blob_sha1": None,
    })
    manifest_raw = json.dumps(registered, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    registry = {
        "schema_version": "0.1.0",
        "engine": "ThermoMPNN",
        "commit": COMMIT,
        "model": "thermoMPNN_default.pt",
        "image": IMAGE,
        "image_reference": "t01-thermompnn-development@" + IMAGE,
        "base_image": "sha256:5b6baa8ebc5660bd3de9cf8b6d1694c7de35fadd23fea6cd7a8352a536e3f3af",
        "license": "MIT",
        "source": "https://github.com/Kuhlman-Lab/ThermoMPNN/tree/" + COMMIT,
        "files": registered,
        "source_manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "archive_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "environment": environment,
        "official_cli": {
            "path": "analysis/custom_inference.py",
            "threshold_parameter": False,
            "complete_output_strategy": "unfiltered 20-AA SSM emitted by the pinned official custom inference entrypoint",
        },
        "scientific_signoff": None,
        "production_status": "NOT_DEPLOYED",
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(registry, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    REGISTRY.write_bytes(raw)
    (EVIDENCE / "source-verification.json").write_bytes(raw)
    (EVIDENCE / "image-inspect.json").write_bytes(json.dumps([image], sort_keys=True, ensure_ascii=False).encode())
    (EVIDENCE / "environment.json").write_bytes(json.dumps(environment, sort_keys=True, ensure_ascii=False).encode())
    print(json.dumps({"commit": COMMIT, "image": IMAGE, "registered_files": len(registered)}, sort_keys=True))


if __name__ == "__main__":
    main()
