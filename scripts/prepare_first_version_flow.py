"""Guarded service-only continuation fixes; preserves workers and databases."""
import prepare_phase1_item3 as base

NAME='antigen-first-version-flow-r02'
OUT=base.renderer.common.ROOT/'deploy/first-version-flow/r02'
EVIDENCE=base.renderer.common.ROOT/'discovery/t01-phase1-real/first-version-flow-20260926'
FILES=('development/workflow/service.py','development/workflow/m1.py')

if __name__=='__main__':
    base.NAME=NAME;base.OUT=OUT;base.EVIDENCE=EVIDENCE;base.FILES=FILES
    base.renderer.render=base.render
    base.configure().main()
