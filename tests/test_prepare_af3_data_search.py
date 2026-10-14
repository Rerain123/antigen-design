import hashlib
import importlib.util
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


RUNNER = module("run_af3_data_search", ROOT / "scripts/run_af3_data_search.py")
PREPARE = module("prepare_af3_data_search", ROOT / "scripts/prepare_af3_data_search.py")


def test_fold_input_is_full_pinned_single_chain_and_requests_local_msa():
    value = PREPARE.fold_input()
    assert value["dialect"] == "alphafold3"
    assert value["version"] == 1
    assert value["modelSeeds"] == [1]
    protein = value["sequences"][0]["protein"]
    assert protein == {"id": "A", "sequence": PREPARE.SEQUENCE}
    assert len(protein["sequence"]) == 76
    assert hashlib.sha256(protein["sequence"].encode()).hexdigest() == PREPARE.SEQUENCE_SHA256
    assert "unpairedMsa" not in protein and "pairedMsa" not in protein


def test_runner_uses_fixed_local_assets_and_separates_search_from_inference():
    source = (ROOT / "scripts/run_af3_data_search.py").read_text(encoding="utf-8")
    assert "--run_data_pipeline=true" in source
    assert "--run_inference=false" in source
    assert "--jackhmmer_n_cpu=8" in source
    assert "--nhmmer_n_cpu=8" in source
    assert RUNNER.MODEL_SHA256 == "df8bbf2621f17dd3ee21c2a921e84a50bc2b80cdc0c7971cb915c2826fee1f9b"
    assert set(RUNNER.REQUIRED_DATABASES) == {
        "pdb_seqres_2022_09_28.fasta",
        "rfam_14_9_clust_seq_id_90_cov_80_rep_seq.fasta",
        "rnacentral_active_seq_id_90_cov_80_linclust.fasta",
        "bfd-first_non_consensus_sequences.fasta",
        "nt_rna_2023_02_23_clust_seq_id_90_cov_80_rep_seq.fasta",
        "uniref90_2022_05.fa",
        "uniprot_all_2021_04.fa",
        "mgy_clusters_2022_05.fa",
        "mmcif_files",
    }


def test_data_search_job_is_bounded_read_only_for_assets_and_zero_gpu():
    config, policy, claim, job = PREPARE.documents()
    documents = [config, policy, claim, job]
    assert list(yaml.safe_load_all(yaml.safe_dump_all(documents, sort_keys=False))) == documents
    assert "egress" not in policy["spec"]
    assert claim["spec"]["resources"]["requests"]["storage"] == "50Gi"
    assert claim["spec"]["storageClassName"] == "ceph-rbd"
    pod = job["spec"]["template"]["spec"]
    container = pod["containers"][0]
    assert container["resources"]["requests"]["memory"] == "64Gi"
    assert container["resources"]["limits"]["memory"] == "96Gi"
    assert container["resources"]["limits"]["cpu"] == "16"
    assert "@sha256:" in container["image"]
    assert "nvidia.com/gpu" not in json.dumps(job)
    asset_mounts = {mount["name"]: mount for mount in container["volumeMounts"]}
    assert asset_mounts["databases"]["readOnly"] is True
    assert asset_mounts["weights"]["readOnly"] is True
    assert "readOnly" not in asset_mounts["runtime"]
    volumes = {volume["name"]: volume for volume in pod["volumes"]}
    assert volumes["databases"]["persistentVolumeClaim"]["readOnly"] is True
    assert volumes["weights"]["persistentVolumeClaim"]["readOnly"] is True
