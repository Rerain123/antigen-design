# Development G0 probe only; production environment remains subject to W1 G1/G3.
FROM python@sha256:528257d48c1da0dcecc2e725d1ae34498d60c965f1241e39cd6a85a8859bdf84
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /opt/probe-requirements.txt
RUN python -m pip --isolated --disable-pip-version-check install --no-cache-dir \
    --index-url https://pypi.org/simple --report /opt/pip-install-report.json \
    -r /opt/probe-requirements.txt \
    && python -m pip --disable-pip-version-check freeze --all > /opt/python-freeze.txt \
    && dpkg-query -W > /opt/os-packages.txt
WORKDIR /work
