"""Immutable item 4 service overlay; no design job is started by deployment."""
import prepare_phase1_item3 as base

NAME='antigen-phase1-item4-r02'
OUT=base.renderer.common.ROOT/'deploy/phase1-item4/r02'
EVIDENCE=base.renderer.common.ROOT/'discovery/t01-phase1-real/phase1-item4-20260925'
FILES=('development/design_backend/permissions.py','development/design_backend/policy.py',
       'development/proteinmpnn/policy.py','development/esm_if1/policy.py','development/esm_if1/source.py',
       'development/workflow/design_rounds.py','development/workflow/policy.py','development/workflow/service.py',
       'development/workflow/engineering.py','development/workflow/m1.py',
       'development/variant_report/policy.py','development/variant_report/m1.py',
       'development/n12_prediction_evidence.py')


if __name__=='__main__':
    base.NAME=NAME;base.OUT=OUT;base.EVIDENCE=EVIDENCE;base.FILES=FILES
    base.renderer.render=base.render
    base.configure().main()
