"""Render the independent real-service Dify template and local provider binding."""

from pathlib import Path

from t01_phase1_real.service_api.dify import bound_bytes, template_bytes


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "dify" / "t01-phase1-real-v0.1"


def write_exact(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise RuntimeError(f"generated file differs and will not be overwritten: {path}")
    if not path.exists():
        path.write_bytes(raw)


def main() -> int:
    template = TARGET / "templates" / "T01_Phase1_Real_Service_v0.1.template.dify.yml"
    bound = TARGET / "bound" / "local_dify_1_17" / "T01_Phase1_Real_Service_v0.1.bound.dify.yml"
    write_exact(template, template_bytes())
    write_exact(bound, bound_bytes())
    print(template)
    print(bound)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
