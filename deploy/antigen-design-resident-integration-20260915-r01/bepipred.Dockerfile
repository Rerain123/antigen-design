FROM antigen-design-resident-bepipred:assembly-r01
COPY src /opt/t01/src
COPY configuration/bepipred.worker.json /opt/t01/worker.json
LABEL t01.integration="20260915-r01" t01.production_status="NOT_DEPLOYED"
