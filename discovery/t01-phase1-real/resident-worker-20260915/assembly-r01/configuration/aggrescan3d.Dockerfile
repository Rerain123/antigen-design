FROM python:3.11-slim-bookworm AS supervisor
FROM lcbio/a3d_server:latest AS native
FROM t01-freesasa-g0:2.2.1-20260905
COPY --from=native /opt/conda /opt/conda
USER 0
COPY --from=supervisor /usr/local /opt/t01/supervisor
COPY src /opt/t01/src
COPY profile.json /profile.json
COPY setup.py /opt/t01/setup.py
COPY aggrescan3d.worker.json /opt/t01/worker.json
ENV PYTHONHOME=/opt/t01/supervisor LD_LIBRARY_PATH=/opt/t01/supervisor/lib PYTHONPATH=/opt/t01/src PYTHONDONTWRITEBYTECODE=1
RUN /opt/t01/supervisor/bin/python3.11 -B /opt/t01/setup.py aggrescan3d
USER 10001:10001
WORKDIR /
ENTRYPOINT ["/opt/t01/supervisor/bin/python3.11","-B","-m","t01_phase1_real.resident_worker"]
CMD ["--root","/var/lib/t01/resident/aggrescan3d","--config","/opt/t01/worker.json"]
