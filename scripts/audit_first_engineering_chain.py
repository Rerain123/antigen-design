"""Audit one downloaded ESMFold2-first N01-N18 engineering-chain report.

The audit is read-only unless --output is supplied.  It verifies retained local
receipts, both ZIP manifests, exact workflow branch outcomes, same-run artifact
bindings, the ESMFold2-to-N01 evidence carried into N17/N18, and closed release
guards.  Anonymous HTTP observations are accepted as explicit inputs because
the archive itself cannot prove whether an object-store URL is public.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import zipfile


SEQUENCE = "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG"
SEQUENCE_SHA256 = "233b4b0b8c4616095bc3249f9375fc345d32af7deaef07117d0383c51d6f19aa"
SUCCEEDED = {
    "prediction", "structure", "topology", "bepipred", "netmhc",
    "epitope_map", "glycosylation", "developability", "wt_draft",
    "variant_report", "wt_reference", "local_delivery",
}
SKIPPED = {
    "blast": "DATABASE_NOT_PROVIDED",
    "homology": "DATABASE_NOT_PROVIDED",
    "domains": "DATABASE_NOT_PROVIDED",
    "design": "SCIENTIFIC_GATE_CLOSED",
    "rescore": "SCIENTIFIC_GATE_CLOSED",
    "protection": "SCIENTIFIC_GATE_CLOSED",
    "stability": "SCIENTIFIC_GATE_CLOSED",
    "codon": "NO_ELIGIBLE_SEQUENCE",
}


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_bytes())


def verified_manifest_zip(raw: bytes) -> tuple[dict[str, bytes], dict]:
    """Return registered files and manifest after safety, CRC, size and hash checks."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert len(names) == len(set(names))
        assert "manifest.json" in names
        for name in names:
            path = PurePosixPath(name)
            assert not path.is_absolute() and ".." not in path.parts and "\\" not in name
        manifest = json.loads(archive.read("manifest.json"))
        rows = manifest["files"]
        assert len(rows) == len({row["path"] for row in rows})
        assert set(names) == {row["path"] for row in rows} | {"manifest.json"}
        files = {name: archive.read(name) for name in names if name != "manifest.json"}
        for row in rows:
            value = files[row["path"]]
            assert len(value) == row["size_bytes"]
            assert sha256(value) == row["sha256"]
        return files, manifest


def audit(batch_dir: Path, anonymous_zip_status: int | None = None,
          anonymous_markdown_status: int | None = None) -> dict:
    batch_dir = batch_dir.resolve()
    batch = load_json(batch_dir / "batch.json")
    submit = load_json(batch_dir / "submit.json")
    status = load_json(batch_dir / "status.json")
    receipt = load_json(batch_dir / "report-receipt.json")
    verification = load_json(batch_dir / "verification.json")
    report_raw = (batch_dir / "report.zip").read_bytes()

    request = batch["request"]
    assert batch["input_mode"] == "esmfold2"
    assert request["protein_sequence"] == SEQUENCE
    assert batch["sequence_sha256"] == sha256(SEQUENCE.encode()) == SEQUENCE_SHA256
    assert request["structure"] is None and request["reuse_jobs"] == {}
    assert request["prediction"] == {"engine": "esmfold2", "seed": 1, "timeout_seconds": 600}
    assert "upload_id" not in batch

    job_id, run_id = submit["job_id"], submit["run_id"]
    assert status["job_id"] == receipt["job_id"] == verification["job_id"] == job_id
    assert status["run_id"] == run_id
    assert status["state"] == "succeeded" and status["terminal"] is True
    assert status["report_ready"] is True and status["error_code"] is None
    assert receipt["publication_status"] == "verified"
    assert verification["status"] == "DOWNLOAD_VERIFIED"
    assert verification["scope"] == "FIRST_N01_N18_ENGINEERING_CHAIN_WITH_ESMFOLD2"
    assert len(report_raw) == receipt["size_bytes"] == verification["bytes"]
    assert sha256(report_raw) == receipt["sha256"] == verification["sha256"]

    outer, _ = verified_manifest_zip(report_raw)
    assert set(outer) == {"local-delivery.zip", "workflow-report.md", "workflow.json"}
    assert outer["workflow-report.md"].decode() == receipt["report_markdown"]
    attachments = {row["fileName"]: row for row in receipt["attachments"]}
    assert set(attachments) == {"report.zip", "report.md"}
    assert attachments["report.zip"]["sha256"] == sha256(report_raw)
    assert attachments["report.zip"]["sizeBytes"] == len(report_raw)
    assert attachments["report.md"]["sha256"] == sha256(outer["workflow-report.md"])
    assert attachments["report.md"]["sizeBytes"] == len(outer["workflow-report.md"])

    workflow = json.loads(outer["workflow.json"])
    nodes = workflow["nodes"]
    assert set(nodes) == SUCCEEDED | set(SKIPPED)
    assert workflow["sequence_sha256"] == SEQUENCE_SHA256
    assert workflow["parent_at_assembly"]["job_id"] == job_id
    assert workflow["parent_at_assembly"]["run_id"] == run_id
    assert workflow["configuration"] == {
        "blast_database_root": None,
        "domains_database_root": None,
        "homology_database_root": None,
    }
    assert workflow["scientific_gate"] == "CLOSED"
    assert workflow["usable_for_pipeline"] is False
    assert workflow["automatic_handoff"] is False
    assert workflow["production_status"] == "NOT_DEPLOYED"
    assert workflow["scientific_signoff"] is None and workflow["md"] == "EXCLUDED"

    status_nodes = status["nodes"]
    assert set(status_nodes) == set(nodes)
    artifact_ids: list[str] = []
    for name, row in nodes.items():
        compact = status_nodes[name]
        assert (compact["job_id"], compact["state"], compact["reason_code"], compact["origin"]) == (
            row.get("job_id"), row["state"], row.get("reason_code") or row.get("error_code"), row.get("origin"))
        if name in SUCCEEDED:
            assert row["state"] == "succeeded" and row["origin"] == "NEW_EXECUTION"
            assert row["job_id"] and row["request_artifact"]["run_id"] == run_id
            assert row["qualification"] == "DEVELOPMENT_UNREVIEWED"
            assert row["usable_for_pipeline"] is False and row["scientific_signoff"] is None
            for artifact in row["artifacts"]:
                assert artifact["run_id"] == run_id
                assert artifact["job_id"] == row["job_id"]
                artifact_ids.append(artifact["artifact_id"])
        else:
            assert row["state"] == "skipped" and row["reason_code"] == SKIPPED[name]
            assert row.get("job_id") is None and not row.get("artifacts")
    assert len(artifact_ids) == len(set(artifact_ids))
    assert nodes["prediction"]["execution_profile"]["id"] == "esmfold2-standard-resident-r01"

    inner, _ = verified_manifest_zip(outer["local-delivery.zip"])
    assert {"data.json", "request.json", "report.md"}.issubset(inner)
    delivery = json.loads(inner["data.json"])
    delivery_request = json.loads(inner["request.json"])
    assert delivery_request["protein_sequence"] == SEQUENCE
    assert delivery["subject"]["sequence_sha256"] == SEQUENCE_SHA256
    assert delivery["outcome"] == "DESIGN_INPUTS_UNAVAILABLE"
    assert delivery["best_candidate"] is None and delivery["formal_candidate_id"] is None
    assert delivery["scientific_pass"] is None and delivery["automatic_handoff"] is False
    assert delivery["production_status"] == "NOT_DEPLOYED"
    assert delivery["candidate_record_complete"] is False and delivery["formal_wt_delivery"] is False

    evidence = delivery["wt_reference"]["structure_quality"]["prediction_evidence"]
    structure = evidence["quality"]["structure"]
    assert evidence["prediction_job_id"] == nodes["prediction"]["job_id"]
    assert evidence["binding"]["job_id"] == nodes["structure"]["job_id"]
    assert evidence["binding"]["run_id"] == run_id
    assert evidence["binding"]["sequence_sha256"] == SEQUENCE_SHA256
    assert evidence["structure_artifact"]["job_id"] == nodes["prediction"]["job_id"]
    assert evidence["structure_artifact"]["run_id"] == run_id
    assert evidence["structure_artifact"]["sha256"] == evidence["binding"]["structure_sha256"]
    assert structure["source"] == "esmfold2_predicted"
    assert len(structure["plddt_per_residue"]) == len(SEQUENCE) == 76
    assert all(math.isfinite(value) and 0 <= value <= 1 for value in structure["plddt_per_residue"])
    assert math.isfinite(structure["mean_plddt"]) and math.isfinite(structure["ptm"])
    assert evidence["quality"]["scientific_gate"] == "CLOSED"
    assert evidence["quality"]["usable_for_pipeline"] is False

    public_observation = {
        "authorization": "NOT_GRANTED_FOR_R03",
        "report_zip_http_status": anonymous_zip_status,
        "report_markdown_http_status": anonymous_markdown_status,
        "anonymous_access_confirmed": anonymous_zip_status == 200 and anonymous_markdown_status == 200,
    }
    return {
        "passed": True,
        "scope": "FIRST_N01_N18_ENGINEERING_CHAIN_WITH_ESMFOLD2",
        "job_id": job_id,
        "run_id": run_id,
        "sequence_sha256": SEQUENCE_SHA256,
        "branch_counts": {"succeeded": len(SUCCEEDED), "skipped": len(SKIPPED), "failed": 0},
        "succeeded": sorted(SUCCEEDED),
        "skipped": {name: SKIPPED[name] for name in sorted(SKIPPED)},
        "artifact_refs": {"total": len(artifact_ids), "unique": len(set(artifact_ids)), "same_run": True},
        "report": {"sha256": sha256(report_raw), "size_bytes": len(report_raw),
                   "outer_members": len(outer) + 1, "inner_members": len(inner) + 1},
        "prediction_to_n01": {
            "profile": nodes["prediction"]["execution_profile"]["id"],
            "prediction_job_id": nodes["prediction"]["job_id"],
            "structure_job_id": nodes["structure"]["job_id"],
            "structure_sha256": evidence["binding"]["structure_sha256"],
            "residues": len(structure["plddt_per_residue"]),
            "mean_plddt": structure["mean_plddt"],
            "ptm": structure["ptm"],
        },
        "delivery_outcome": delivery["outcome"],
        "release_guards": {"scientific_gate": "CLOSED", "usable_for_pipeline": False,
                           "automatic_handoff": False, "production_status": "NOT_DEPLOYED"},
        "public_object_observation": public_observation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch_dir", type=Path)
    parser.add_argument("--anonymous-zip-status", type=int)
    parser.add_argument("--anonymous-markdown-status", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.batch_dir, args.anonymous_zip_status, args.anonymous_markdown_status)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
