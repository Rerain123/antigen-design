"""Summarize actual validation and deployment evidence for unified items 5–8."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from version_bundle import build,sha,encode

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/remaining-tools-20260928'

def main():
    read=lambda n:json.loads((OUT/n).read_bytes())
    deployed=read('deployment-verification.json')
    assert deployed['status']=='PASS' and deployed['new_jobs']==0
    assert build(ROOT/'src')[1]==read('tested-source.json')['source_hashes']
    latest={}
    for n in ('full.junit.xml','capacity-delivery.junit.xml','final-affected.junit.xml','docker-recheck.junit.xml'):
        for c in ET.parse(OUT/n).iter('testcase'):latest[(c.get('classname'),c.get('name'))]=c
    cases=list(latest.values());assert not any(c.find('failure') is not None or c.find('error') is not None for c in cases)
    evidence=['full.junit.xml','capacity-delivery.junit.xml','final-affected.junit.xml','docker-recheck.junit.xml','tested-source.json','predeploy-imports.json',
        'deployment-verification.json','frozen.json','layout-preview-visual-check.json','camsol-preparation.json',
        'control-report-replay.json','real-skip-replay.json','n17-native-replay.json']
    result=dict(status='ENGINEERING_DELIVERED_WITH_EXPLICIT_SCIENTIFIC_GAPS',items=[5,6,7,8],
        authority=dict(version='v10.5_20260902',sections=['SOP S-30','SOP S-31 R-40','SOP T-01 steps19–22','C44 §2b']),
        deployment={k:deployed[k] for k in ('generation','pod','files_per_snapshot','source_sha256','job_count','new_jobs')},
        regression=dict(total=len(cases),passed=sum(c.find('skipped') is None for c in cases),skipped=sum(c.find('skipped') is not None for c in cases),
            frozen_assets=read('frozen.json')['frozen_asset_count']),
        completed={
            '5':'N13 all current-round S28-validated mutants (up to 64), same-run recursive sources, 4MiB bounded N13/N15 requests and per-pair hashed details; 64 x 999aa summary capacity verified; L1–L3 feed existing N15 ranking; L4 diagnostics not substituted for unspecified Top20 selection.',
            '6':'R40 defined consensus classifications using preserved per-engine ranks/denominators; incomplete coverage and unspecified combinations remain unknown; no cross-engine ddG averaging; responsive report.',
            '7':'Pinned Swiss-Prot 2026_03 AA20 rounded frequencies and public Roseman raw values with source hashes; streaming reproducible calibration machinery; independent moments/Eq1 tests and 100000 x 200 Eq1 preparation run.',
            '8':'Up to 20 N15 engineering candidate DNA children with explicit supported expression host, recursive same-run candidate/sequence/SC10 proof, failure/cancel guards, HTML/Markdown/ZIP and DNA FASTA provenance.'},
        remaining={
            '5':['L4 Top20 pool origin undefined; geometric family definitions and ties incomplete; reliable CamSol/overall absent; no new positive full-pool native scientific run.'],
            '6':['SOP step22 outer non-membrane gate conflicts with inner single-TM ectodomain clause.',
                 'Low-confidence sequence-level ThermoMPNN suggestion lacks a registered sequence-only C43 mode.',
                 'R40 does not classify all rank combinations; current native comparison sets differ (FoldX per-position AA20, ThermoMPNN requested non-self set); disclose for review.',
                 'No new full-scope native scan; model runtime/large-scan batching not validated by these replays.'],
            '7':['OI-025 Roseman sign/transform, alternating-pattern counting, pH correspondence and independent official numerical reference remain unresolved; final mu/sigma/profile/global_score not published.'],
            '8':['HiMat expression-host input remains absent by user decision; first release still only supports registered E.coli profile; candidate-positive full scientific input unavailable, so positive lineage evidence uses explicit engineering fixtures.']},
        new_scientific_jobs=0,scientific_eligible=False,
        evidence={n:sha((OUT/n).read_bytes()) for n in evidence})
    (OUT/'closeout.json').write_bytes(encode(result))
    print(json.dumps({k:result[k] for k in ('status','deployment','regression')}))

if __name__=='__main__':main()
