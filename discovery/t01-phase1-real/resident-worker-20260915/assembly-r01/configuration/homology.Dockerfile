FROM python:3.11-slim-bookworm AS supervisor
FROM t01-homology-development:20260907
USER 0
COPY --from=supervisor /usr/local /opt/t01/supervisor
COPY src /opt/t01/src
COPY profile.json /profile.json
COPY setup.py /opt/t01/setup.py
COPY homology.worker.json /opt/t01/worker.json
ENV PYTHONHOME=/opt/t01/supervisor LD_LIBRARY_PATH=/opt/t01/supervisor/lib PYTHONPATH=/opt/t01/src PYTHONDONTWRITEBYTECODE=1
RUN /opt/t01/supervisor/bin/python3.11 -B /opt/t01/setup.py homology
USER 10001:10001
WORKDIR /
ENTRYPOINT ["/opt/t01/supervisor/bin/python3.11","-B","-m","t01_phase1_real.resident_worker"]
CMD ["--root","/var/lib/t01/resident/homology","--config","/opt/t01/worker.json"]
