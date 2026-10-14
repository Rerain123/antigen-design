ARG BASE_IMAGE=python:3.11-slim-bookworm@sha256:528257d48c1da0dcecc2e725d1ae34498d60c965f1241e39cd6a85a8859bdf84
FROM ${BASE_IMAGE}

ARG RELEASE_VERSION=0.2.0-rc1
ARG SOURCE_DATE_EPOCH=1788969600
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONHASHSEED=0 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    T01_RELEASE_VERSION=${RELEASE_VERSION} \
    T01_PROCESS_REGISTRY=/tmp/t01-process-control
LABEL org.opencontainers.image.title="T-01 Phase 1 real control plane" \
      org.opencontainers.image.version="${RELEASE_VERSION}" \
      org.opencontainers.image.created="2026-09-12T00:00:00Z" \
      org.opencontainers.image.source="local-release-candidate" \
      t01.production_status="NOT_DEPLOYED" \
      t01.scientific_gate="CLOSED"

COPY requirements.lock /build/requirements.lock
COPY wheelhouse /build/wheelhouse
RUN python -m pip install --disable-pip-version-check --no-cache-dir --no-compile \
      --no-index --find-links=/build/wheelhouse -r /build/requirements.lock \
    && rm -rf /build

COPY application /app
RUN groupadd --gid 10001 t01 \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin t01 \
    && mkdir -p /var/lib/t01/runtime /tmp/t01-process-control \
    && chown -R 10001:10001 /var/lib/t01 /tmp/t01-process-control \
    && chmod 0700 /tmp/t01-process-control

WORKDIR /app
USER 10001:10001
EXPOSE 18083
ENTRYPOINT ["python", "-B", "-m", "t01_phase1_real.linux_service"]
