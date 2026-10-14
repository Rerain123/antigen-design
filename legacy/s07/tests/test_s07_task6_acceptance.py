from __future__ import annotations

from t01_s07_acceptance.backend import (
    rcsb_strict_matches,
    select_experimental_candidate,
    strict_candidate_passes,
)


def candidate(
    entry: str,
    chain: str,
    method_group: str,
    resolution: float | None,
) -> dict:
    return {
        "entry_id": entry,
        "chain_id": chain,
        "method": method_group,
        "method_group": method_group,
        "resolution_angstrom": resolution,
    }


def test_strict_gate_rejects_equal_boundaries() -> None:
    assert not strict_candidate_passes({"fident": 0.95, "qcov": 0.91})
    assert not strict_candidate_passes({"fident": 0.96, "qcov": 0.90})
    assert strict_candidate_passes({"fident": 0.950001, "qcov": 0.900001})


def test_resolution_selection_uses_provisional_cross_method_order() -> None:
    result = select_experimental_candidate(
        [
            candidate("XRAY", "A", "X_RAY", 2.0),
            candidate("EM01", "B", "CRYO_EM", 3.5),
            candidate("NMR1", "C", "NMR", None),
            candidate("INT1", "D", "OTHER", None),
        ]
    )
    assert result["status"] == "SELECTED_PROVISIONAL"
    assert result["selected_entry_id"] == "XRAY"
    assert "S07-EQ-02" in result["expert_confirmation_ids"]
    assert "NMR_CANDIDATES_RETAINED_AS_PROVISIONAL_BACKUP" in result["reason_codes"]
    assert (
        "INCOMPARABLE_METHOD_CANDIDATES_RETAINED_AS_PROVISIONAL_BACKUP"
        in result["reason_codes"]
    )


def test_resolution_tie_does_not_use_array_order() -> None:
    result = select_experimental_candidate(
        [
            candidate("BBBB", "A", "X_RAY", 2.0),
            candidate("AAAA", "A", "CRYO_EM", 2.0),
        ]
    )
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["selected_entry_id"] is None
    assert result["tied_entry_ids"] == ["AAAA", "BBBB"]


def test_r58_multiple_chains_block_handoff() -> None:
    result = select_experimental_candidate(
        [
            candidate("9R2Q", "K", "CRYO_EM", 3.2),
            candidate("9R2Q", "L", "CRYO_EM", 3.2),
        ]
    )
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["matching_chain_ids"] == ["K", "L"]
    assert "R58_AMBIGUOUS_MATCHING_CHAINS_BLOCK_AUTO_HANDOFF" in result["reason_codes"]


def test_verbose_rcsb_context_is_postfiltered_with_query_coverage() -> None:
    payload = {
        "result_set": [
            {
                "identifier": "PASS_1",
                "services": [
                    {
                        "service_type": "sequence",
                        "nodes": [
                            {
                                "match_context": [
                                    {
                                        "sequence_identity": 0.96,
                                        "query_beg": 2,
                                        "query_end": 96,
                                        "query_length": 100,
                                        "subject_beg": 1,
                                        "subject_end": 95,
                                        "subject_length": 110,
                                        "evalue": 1e-20,
                                        "bitscore": 80,
                                    }
                                ]
                            }
                        ],
                    }
                ],
            },
            {
                "identifier": "BOUNDARY_1",
                "services": [
                    {
                        "service_type": "sequence",
                        "nodes": [
                            {
                                "match_context": [
                                    {
                                        "sequence_identity": 0.95,
                                        "query_beg": 1,
                                        "query_end": 100,
                                        "query_length": 100,
                                        "subject_beg": 1,
                                        "subject_end": 100,
                                        "subject_length": 100,
                                    }
                                ]
                            }
                        ],
                    }
                ],
            },
        ]
    }
    matches = rcsb_strict_matches([payload])
    assert [item["identifier"] for item in matches] == ["PASS_1"]
    assert matches[0]["query_coverage"] == 0.95
