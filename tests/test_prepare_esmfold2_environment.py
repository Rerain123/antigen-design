from pathlib import Path

import pytest

from scripts.prepare_esmfold2_environment import DEPLOY, prepare


def test_environment_inputs_preserve_offline_and_pinned_runtime_contract():
    dockerfile = (DEPLOY / "Dockerfile.environment").read_text(encoding="utf-8")
    environment = (DEPLOY / "environment.json").read_text(encoding="utf-8")
    assert "python:3.12-slim-bookworm@sha256:" in dockerfile
    assert "requirements.resolved.txt" in dockerfile
    assert "gcc libc6-dev" in dockerfile
    assert "HF_HUB_OFFLINE=1" in dockerfile
    assert "TRITON_CACHE_DIR=/tmp/triton" in dockerfile
    assert "b6b0e8815dc3174a9fe9afd36b222aea57d536c5" in environment
    assert "ef32577f55da19a4989cd7b22e004dc43a4998cb" in environment


def test_prepare_refuses_to_replace_existing_context(tmp_path: Path):
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(ValueError, match="already exists"):
        prepare(tmp_path / "assets", output)
