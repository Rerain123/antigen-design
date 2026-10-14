# Jenkins build entry point. The indexed Dockerfile under deploy/ remains an
# immutable release-candidate artifact; this file builds the same application
# layout directly from the repository checkout.
ARG BASE_IMAGE=python:3.11-slim-bookworm@sha256:528257d48c1da0dcecc2e725d1ae34498d60c965f1241e39cd6a85a8859bdf84
FROM ${BASE_IMAGE}

ARG RELEASE_VERSION=0.2.0-rc3
ARG SOURCE_DATE_EPOCH=1788969600
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONHASHSEED=0 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    T01_RELEASE_VERSION=${RELEASE_VERSION} \
    T01_PROCESS_REGISTRY=/tmp/t01-process-control
LABEL org.opencontainers.image.title="Antigen Design control plane" \
      org.opencontainers.image.version="${RELEASE_VERSION}" \
      org.opencontainers.image.created="2026-09-12T00:00:00Z" \
      org.opencontainers.image.source="agent/antigen-design" \
      t01.production_status="NOT_DEPLOYED" \
      t01.scientific_gate="CLOSED"

COPY deploy/t01-phase1-real-target-v0.2/requirements.lock /build/requirements.lock
COPY deploy/t01-phase1-real-target-v0.2/wheelhouse /build/wheelhouse
COPY deploy/codon-linux/wheelhouse /build/codon-wheels
RUN python -m pip install --disable-pip-version-check --no-cache-dir --no-compile \
      --no-index --find-links=/build/wheelhouse -r /build/requirements.lock \
    && python -m pip install --disable-pip-version-check --no-cache-dir --no-compile --no-deps \
      --no-index /build/codon-wheels/colorama-0.4.6-py2.py3-none-any.whl \
    && rm -rf /build

WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
COPY requirements /app/requirements
COPY ["工作流设计", "/app/工作流设计"]
COPY docs /app/docs
COPY discovery/t01-phase1-real/w2/bepipred-integration-20260906/bp3-0.0.12.7-py2.py3-none-any.whl /app/discovery/t01-phase1-real/w2/bepipred-integration-20260906/bp3-0.0.12.7-py2.py3-none-any.whl
COPY discovery/t01-phase1-real/w2/bepipred-integration-20260906/environment/python-freeze.txt discovery/t01-phase1-real/w2/bepipred-integration-20260906/environment/dependency-install-report.json discovery/t01-phase1-real/w2/bepipred-integration-20260906/environment/torch-install-report.json /app/discovery/t01-phase1-real/w2/bepipred-integration-20260906/environment/
COPY scripts/t01_runtime.py /app/scripts/t01_runtime.py
COPY scripts/t01_linux_development_supervisor.py /app/scripts/t01_development_supervisor.py
COPY scripts/t01_linux_w1_supervisor.py /app/scripts/w1_runtime_supervisor.py
COPY scripts/t01_linux_w1_worker.py /app/scripts/w1_runtime_worker.py
COPY scripts/restore_pinned_build_sources.py /build/restore_pinned_build_sources.py
# Git may normalize frozen CRLF documents on Linux checkout. Restore only an
# exact frozen hash match in image copies; fail the build on content changes.
RUN python -B /build/restore_pinned_build_sources.py --build-root /app \
      --profile-manifest requirements/control-profile-inputs.json \
    && rm /build/restore_pinned_build_sources.py

RUN groupadd --gid 10001 t01 \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin t01 \
    && mkdir -p /var/lib/t01/runtime /tmp/t01-process-control \
    && chown -R 10001:10001 /var/lib/t01 /tmp/t01-process-control \
    && chmod 0700 /tmp/t01-process-control

USER 10001:10001
LABEL t01.deployment_attempt="20260915-test-retry-01"
EXPOSE 18083
ENTRYPOINT ["python", "-B", "-m", "t01_phase1_real.linux_service"]
