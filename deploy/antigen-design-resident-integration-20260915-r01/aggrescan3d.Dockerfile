FROM antigen-design-resident-aggrescan3d:assembly-r01
COPY src /opt/t01/src
COPY configuration/aggrescan3d.worker.json /opt/t01/worker.json
LABEL t01.integration="20260915-r01" t01.production_status="NOT_DEPLOYED"
