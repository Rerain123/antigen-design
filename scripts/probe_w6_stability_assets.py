"""Record a non-secret W6 local asset probe without substituting engine versions."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from t01_phase1_real.common import encode, now, sha
from t01_phase1_real.development.thermompnn import policy as thermompnn


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).absolute()
    assert output.is_relative_to(REPO / "discovery/t01-phase1-real/w6")
    assert not output.exists()
    commands = {name: shutil.which(name) for name in ("foldx", "FoldX", "foldx_5", "foldx5")}
    environment = {name: bool(os.environ.get(name)) for name in sorted(os.environ) if "FOLDX" in name.upper()}
    asset_root = REPO / "var/t01-phase1-real/tool-assets"
    registered_matches = [path.relative_to(REPO).as_posix() for path in sorted(asset_root.glob("*foldx*"))]
    image_process = subprocess.run(
        ["docker", "image", "ls", "--format", "{{.Repository}}:{{.Tag}} {{.ID}}"],
        capture_output=True,
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    image_lines = image_process.stdout.decode(errors="replace").splitlines() if image_process.returncode == 0 else []
    docker_matches = [line for line in image_lines if "foldx" in line.lower()]
    authority = {
        path.relative_to(REPO).as_posix(): sha(path.read_bytes())
        for path in thermompnn.AUTHORITY
        if "FoldX" in path.name or "SOP" in path.name
    }
    value = dict(
        schema_version="0.1.0",
        checked_at=now(),
        engine="FoldX",
        required_version="5.0",
        status="BLOCKED_ASSET_MISSING",
        legal_package_present=False,
        license_receipt_present=False,
        companion_files_verified=False,
        executable_candidates=commands,
        foldx_environment_variable_presence=environment,
        registered_asset_matches=registered_matches,
        docker_image_matches=docker_matches,
        docker_inventory_exit_code=image_process.returncode,
        authority=authority,
        official_license_information="https://foldxsuite.crg.eu/node/737",
        required_to_close=[
            "legally obtained FoldX 5.0 package",
            "local license/authorization receipt suitable for this use",
            "executable and required companion files with immutable hashes",
        ],
        blocked_capabilities=["RepairPDB", "BuildModel explicit single/multi mutation scoring", "PositionScan explicit position scanning"],
        unaffected_capabilities=["ThermoMPNN monomer full-SSM engineering integration"],
        substitution_performed=False,
        scientific_effect="No FoldX result exists; no N14/N17 scientific release or candidate recovery is implied.",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(encode(value))
    print(encode(dict(output=str(output), status=value["status"], docker_image_matches=docker_matches)).decode())


if __name__ == "__main__":
    main()
