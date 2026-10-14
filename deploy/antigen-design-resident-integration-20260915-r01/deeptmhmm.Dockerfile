FROM antigen-design-resident-deeptmhmm:assembly-r01
COPY src /opt/t01/src
COPY configuration/deeptmhmm.worker.json /opt/t01/worker.json
LABEL t01.integration="20260915-r01" t01.production_status="NOT_DEPLOYED"
