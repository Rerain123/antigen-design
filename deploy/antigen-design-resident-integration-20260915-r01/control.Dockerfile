FROM antigen-design-control:ci-root-smoke
COPY src /app/src
COPY configuration/controller.json /opt/t01/resident-controller.json
ENV T01_RESIDENT_CONFIG_FILE=/opt/t01/resident-controller.json
LABEL t01.integration="20260915-r01" t01.production_status="NOT_DEPLOYED"
