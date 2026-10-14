"""Correct no-generation wording after public status field projection."""
import prepare_host_panel_deploy as deploy

if __name__=='__main__':
    deploy.NAME='antigen-host-panel-r03'
    deploy.OUT=deploy.base.common.ROOT/'deploy/host-panel/r03'
    deploy.FILES+=('development/workflow/m1.py','development/workflow/reporting.py')
    base=deploy.base
    base.NAME,base.OUT,base.EVIDENCE,base.FILES=deploy.NAME,deploy.OUT,deploy.EVIDENCE,deploy.FILES
    base.render=deploy.render
    base.main()
