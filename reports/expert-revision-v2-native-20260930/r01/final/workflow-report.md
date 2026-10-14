# Local workflow engineering report

Scientific Gate: CLOSED; DEVELOPMENT_UNREVIEWED; NOT_DEPLOYED.

| Node | Branch | State | Reason | Origin | Detail |
|---|---|---|---|---|---|
| N04 | bepipred | succeeded |  | SAME_RUN_REUSE |  |
| N03 | blast | succeeded |  | SAME_RUN_REUSE |  |
| N12 | cheap0 | succeeded |  | SAME_RUN_REUSE |  |
| N16 | codon | skipped | EXPRESSION_HOST_NOT_PROVIDED |  |  |
| N11 | design | ready |  |  |  |
| N11 | design_inputs | succeeded |  | SAME_RUN_REUSE |  |
| N10 | developability | succeeded |  | SAME_RUN_REUSE |  |
| N09 | domains | succeeded |  | SAME_RUN_REUSE |  |
| N06 | epitope_map | succeeded |  | SAME_RUN_REUSE |  |
| N11 | formal0 | succeeded |  | SAME_RUN_REUSE |  |
| N07 | glycosylation | succeeded |  | SAME_RUN_REUSE |  |
| N08 | homology | skipped | DATABASE_NOT_PROVIDED |  |  |
| N18 | local_delivery | succeeded |  | NEW_EXECUTION |  |
| N05 | netmhc | succeeded |  | SAME_RUN_REUSE |  |
| N01 | prediction | succeeded |  | SAME_RUN_REUSE |  |
| N11 | proposal0 | succeeded |  | SAME_RUN_REUSE |  |
| N11 | proposal1 | succeeded |  | SAME_RUN_REUSE |  |
| N12 | revision_design | succeeded | S28_ORIGINAL_PASS | INTERNAL_FACT |  |
| N12 | rx0_s2_af3 | succeeded |  | NEW_EXECUTION |  |
| N12 | rx0_s2_esmfold2 | succeeded |  | NEW_EXECUTION |  |
| N12 | rx0_s4_af3 | succeeded |  | NEW_EXECUTION |  |
| N12 | rx0_s4_esmfold2 | succeeded |  | NEW_EXECUTION |  |
| N12 | rx0_s9_af3 | succeeded |  | NEW_EXECUTION |  |
| N12 | rx0_s9_esmfold2 | succeeded |  | NEW_EXECUTION |  |
| N01 | structure | succeeded |  | SAME_RUN_REUSE |  |
| N02 | topology | succeeded |  | SAME_RUN_REUSE |  |
| N18 | wt_draft | succeeded |  | SAME_RUN_REUSE |  |
| N17 | wt_foldx | skipped | NO_COVERED_EXPLICIT_OPEN_SCAN_POSITION |  |  |
| N12 | wt_msa | succeeded |  | NEW_EXECUTION |  |
| N17 | wt_reference | succeeded |  | NEW_EXECUTION |  |
| N17 | wt_thermompnn | skipped | NO_COVERED_EXPLICIT_OPEN_SCAN_POSITION |  |  |
| N13 | z0_s2_bepipred | succeeded |  | NEW_EXECUTION |  |
| N10 | z0_s2_developability | succeeded |  | NEW_EXECUTION |  |
| N13 | z0_s2_epitope_map | succeeded |  | NEW_EXECUTION |  |
| N13 | z0_s2_netmhc | succeeded |  | NEW_EXECUTION |  |
| N13 | z0_s2_structure | succeeded |  | NEW_EXECUTION |  |
| N13 | z0_s4_bepipred | succeeded |  | NEW_EXECUTION |  |
| N10 | z0_s4_developability | succeeded |  | NEW_EXECUTION |  |
| N13 | z0_s4_epitope_map | succeeded |  | NEW_EXECUTION |  |
| N13 | z0_s4_netmhc | succeeded |  | NEW_EXECUTION |  |
| N13 | z0_s4_structure | succeeded |  | NEW_EXECUTION |  |
| N13 | z0_s9_bepipred | succeeded |  | NEW_EXECUTION |  |
| N10 | z0_s9_developability | succeeded |  | NEW_EXECUTION |  |
| N13 | z0_s9_epitope_map | succeeded |  | NEW_EXECUTION |  |
| N13 | z0_s9_netmhc | succeeded |  | NEW_EXECUTION |  |
| N13 | z0_s9_structure | succeeded |  | NEW_EXECUTION |  |

## Expert revision / engineering facts

Contract: t01-core-20260929-v1
Formal acceptance: NOT_ASSESSED
Proposals are nomination-only; full sequences, provenance and task budgets are in workflow.json.

| Candidate | Mutations | Disposition | S28 | FoldX execution / mean / valid repeats | Acceptance |
|---|---|---|---|---|---|
| candidate-fb6599878bc3ce1da413eac3d957643953527f953bc567cdca21f35e51c1e278 | 12 | FORMAL_POOL | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-a781218769c0786d2a9c906949b215850975ba43c1a04c8cd421f65abac95942 | 10 | FORMAL_POOL | PASS | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-137c29d8fb0930411e0c80452eceb45c6b292a23dc48466b218c6438f3ab46df | 11 | FORMAL_POOL | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-655778e3cb86614bec5a1c51cc39d8a37001ca37243b520e5ec22d4ce748fb58 | 11 | FORMAL_POOL | PASS | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-137c29d8fb0930411e0c80452eceb45c6b292a23dc48466b218c6438f3ab46df | 11 | DUPLICATE | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-655778e3cb86614bec5a1c51cc39d8a37001ca37243b520e5ec22d4ce748fb58 | 11 | DUPLICATE | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-a781218769c0786d2a9c906949b215850975ba43c1a04c8cd421f65abac95942 | 10 | DUPLICATE | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-a781218769c0786d2a9c906949b215850975ba43c1a04c8cd421f65abac95942 | 10 | DUPLICATE | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-ee76f1e554e5bd24d4972dfbbe2e1d3d659b3d70fbb84f6aab1462e74f550296 | 10 | FORMAL_POOL | PASS | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-137c29d8fb0930411e0c80452eceb45c6b292a23dc48466b218c6438f3ab46df | 11 | DUPLICATE | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-655778e3cb86614bec5a1c51cc39d8a37001ca37243b520e5ec22d4ce748fb58 | 11 | DUPLICATE | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-137c29d8fb0930411e0c80452eceb45c6b292a23dc48466b218c6438f3ab46df | 11 | DUPLICATE | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-ee76f1e554e5bd24d4972dfbbe2e1d3d659b3d70fbb84f6aab1462e74f550296 | 10 | DUPLICATE | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-655778e3cb86614bec5a1c51cc39d8a37001ca37243b520e5ec22d4ce748fb58 | 11 | DUPLICATE | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-655778e3cb86614bec5a1c51cc39d8a37001ca37243b520e5ec22d4ce748fb58 | 11 | DUPLICATE | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-137c29d8fb0930411e0c80452eceb45c6b292a23dc48466b218c6438f3ab46df | 11 | DUPLICATE | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-a781218769c0786d2a9c906949b215850975ba43c1a04c8cd421f65abac95942 | 10 | DUPLICATE | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-137c29d8fb0930411e0c80452eceb45c6b292a23dc48466b218c6438f3ab46df | 11 | DUPLICATE | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-ee76f1e554e5bd24d4972dfbbe2e1d3d659b3d70fbb84f6aab1462e74f550296 | 10 | DUPLICATE | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-655778e3cb86614bec5a1c51cc39d8a37001ca37243b520e5ec22d4ce748fb58 | 11 | DUPLICATE | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-655778e3cb86614bec5a1c51cc39d8a37001ca37243b520e5ec22d4ce748fb58 | 11 | DUPLICATE | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-655778e3cb86614bec5a1c51cc39d8a37001ca37243b520e5ec22d4ce748fb58 | 11 | DUPLICATE | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-137c29d8fb0930411e0c80452eceb45c6b292a23dc48466b218c6438f3ab46df | 11 | DUPLICATE | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |
| candidate-655778e3cb86614bec5a1c51cc39d8a37001ca37243b520e5ec22d4ce748fb58 | 11 | DUPLICATE | NOT_ASSESSED | NOT_RUN / None / 0 | NOT_ASSESSED |

v2 thresholds: pending_calibration. Provisional task acceptance: NOT_ASSESSED
Scores are comparable only within the same dimension, mode and evidence group; no global rank.

| Candidate | Supplier | N13 / legacy L1 identity | L4 | Comparison before / after penalty | Acceptance score / provisional |
|---|---|---|---|---|---|
| candidate-fb6599878bc3ce1da413eac3d957643953527f953bc567cdca21f35e51c1e278 | None | NOT_ASSESSED / None | NOT_ASSESSED | 0.1428571428571429 / 0.0428571428571429 | None / NOT_ASSESSED |
| candidate-a781218769c0786d2a9c906949b215850975ba43c1a04c8cd421f65abac95942 | primary | NOT_ASSESSED / None | NOT_ASSESSED | 0.35785413500784324 / 0.35785413500784324 | None / NOT_ASSESSED |
| candidate-137c29d8fb0930411e0c80452eceb45c6b292a23dc48466b218c6438f3ab46df | None | NOT_ASSESSED / None | NOT_ASSESSED | 0.2142857142857143 / 0.2142857142857143 | None / NOT_ASSESSED |
| candidate-655778e3cb86614bec5a1c51cc39d8a37001ca37243b520e5ec22d4ce748fb58 | primary | NOT_ASSESSED / None | NOT_ASSESSED | 0.3444879254602145 / 0.3444879254602145 | None / NOT_ASSESSED |
| candidate-137c29d8fb0930411e0c80452eceb45c6b292a23dc48466b218c6438f3ab46df | None | None / None | None | None / None | None / NOT_ASSESSED |
| candidate-655778e3cb86614bec5a1c51cc39d8a37001ca37243b520e5ec22d4ce748fb58 | None | None / None | None | None / None | None / NOT_ASSESSED |
| candidate-a781218769c0786d2a9c906949b215850975ba43c1a04c8cd421f65abac95942 | None | None / None | None | None / None | None / NOT_ASSESSED |
| candidate-a781218769c0786d2a9c906949b215850975ba43c1a04c8cd421f65abac95942 | None | None / None | None | None / None | None / NOT_ASSESSED |
| candidate-ee76f1e554e5bd24d4972dfbbe2e1d3d659b3d70fbb84f6aab1462e74f550296 | primary | NOT_ASSESSED / None | NOT_ASSESSED | 0.3567186135219307 / 0.3567186135219307 | None / NOT_ASSESSED |
| candidate-137c29d8fb0930411e0c80452eceb45c6b292a23dc48466b218c6438f3ab46df | None | None / None | None | None / None | None / NOT_ASSESSED |
| candidate-655778e3cb86614bec5a1c51cc39d8a37001ca37243b520e5ec22d4ce748fb58 | None | None / None | None | None / None | None / NOT_ASSESSED |
| candidate-137c29d8fb0930411e0c80452eceb45c6b292a23dc48466b218c6438f3ab46df | None | None / None | None | None / None | None / NOT_ASSESSED |
| candidate-ee76f1e554e5bd24d4972dfbbe2e1d3d659b3d70fbb84f6aab1462e74f550296 | None | None / None | None | None / None | None / NOT_ASSESSED |
| candidate-655778e3cb86614bec5a1c51cc39d8a37001ca37243b520e5ec22d4ce748fb58 | None | None / None | None | None / None | None / NOT_ASSESSED |
| candidate-655778e3cb86614bec5a1c51cc39d8a37001ca37243b520e5ec22d4ce748fb58 | None | None / None | None | None / None | None / NOT_ASSESSED |
| candidate-137c29d8fb0930411e0c80452eceb45c6b292a23dc48466b218c6438f3ab46df | None | None / None | None | None / None | None / NOT_ASSESSED |
| candidate-a781218769c0786d2a9c906949b215850975ba43c1a04c8cd421f65abac95942 | None | None / None | None | None / None | None / NOT_ASSESSED |
| candidate-137c29d8fb0930411e0c80452eceb45c6b292a23dc48466b218c6438f3ab46df | None | None / None | None | None / None | None / NOT_ASSESSED |
| candidate-ee76f1e554e5bd24d4972dfbbe2e1d3d659b3d70fbb84f6aab1462e74f550296 | None | None / None | None | None / None | None / NOT_ASSESSED |
| candidate-655778e3cb86614bec5a1c51cc39d8a37001ca37243b520e5ec22d4ce748fb58 | None | None / None | None | None / None | None / NOT_ASSESSED |
| candidate-655778e3cb86614bec5a1c51cc39d8a37001ca37243b520e5ec22d4ce748fb58 | None | None / None | None | None / None | None / NOT_ASSESSED |
| candidate-655778e3cb86614bec5a1c51cc39d8a37001ca37243b520e5ec22d4ce748fb58 | None | None / None | None | None / None | None / NOT_ASSESSED |
| candidate-137c29d8fb0930411e0c80452eceb45c6b292a23dc48466b218c6438f3ab46df | None | None / None | None | None / None | None / NOT_ASSESSED |
| candidate-655778e3cb86614bec5a1c51cc39d8a37001ca37243b520e5ec22d4ce748fb58 | None | None / None | None | None / None | None / NOT_ASSESSED |
