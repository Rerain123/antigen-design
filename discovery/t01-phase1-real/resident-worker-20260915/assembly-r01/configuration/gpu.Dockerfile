FROM python:3.11-slim-bookworm AS supervisor
FROM t01-esm-if1-development:2b369911-cu128-20260908 AS esm-if1
FROM t01-thermompnn-development:2b04fd37-cu128-20260908 AS thermompnn
FROM t01-proteinmpnn-development:8907e667-cu128-20260908
COPY --from=esm-if1 /usr/local /opt/t01/env/esm-if1
COPY --from=thermompnn /usr/local /opt/t01/env/thermompnn
USER 0
COPY --from=supervisor /usr/local /opt/t01/supervisor
COPY src /opt/t01/src
COPY profile.json /profile.json
COPY setup.py /opt/t01/setup.py
COPY gpu.worker.json /opt/t01/worker.json
ENV PYTHONHOME=/opt/t01/supervisor LD_LIBRARY_PATH=/opt/t01/supervisor/lib PYTHONPATH=/opt/t01/src PYTHONDONTWRITEBYTECODE=1
RUN /opt/t01/supervisor/bin/python3.11 -B /opt/t01/setup.py gpu
USER 10001:10001
WORKDIR /
ENTRYPOINT ["/opt/t01/supervisor/bin/python3.11","-B","-m","t01_phase1_real.resident_worker"]
CMD ["--root","/var/lib/t01/resident/gpu","--config","/opt/t01/worker.json"]
