import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "first_chain_auditor", ROOT / "scripts/audit_first_engineering_chain.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def archive(files, *, manifest_mutation=None, extra=None, duplicate=False):
    rows = [
        {"path": name, "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        for name, raw in sorted(files.items())
    ]
    manifest = {"files": rows}
    if manifest_mutation:
        manifest_mutation(manifest)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as value:
        for name, raw in files.items():
            value.writestr(name, raw)
        value.writestr("manifest.json", json.dumps(manifest).encode())
        if extra:
            value.writestr(extra, b"extra")
        if duplicate:
            with pytest.warns(UserWarning):
                value.writestr(next(iter(files)), b"duplicate")
    return output.getvalue()


def test_verified_manifest_zip_accepts_registered_files():
    raw = archive({"workflow.json": b"{}", "workflow-report.md": b"report"})
    files, manifest = AUDIT.verified_manifest_zip(raw)
    assert files == {"workflow.json": b"{}", "workflow-report.md": b"report"}
    assert len(manifest["files"]) == 2


@pytest.mark.parametrize("mutation", ["payload", "extra", "duplicate", "traversal"])
def test_verified_manifest_zip_rejects_tamper_and_unsafe_names(mutation):
    files = {"workflow.json": b"{}"}
    kwargs = {}
    if mutation == "payload":
        def change(manifest):
            manifest["files"][0]["sha256"] = "0" * 64
        kwargs["manifest_mutation"] = change
    elif mutation == "extra":
        kwargs["extra"] = "extra.txt"
    elif mutation == "duplicate":
        kwargs["duplicate"] = True
    else:
        files = {"../escape": b"no"}
    with pytest.raises(AssertionError):
        AUDIT.verified_manifest_zip(archive(files, **kwargs))
