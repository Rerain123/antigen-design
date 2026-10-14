FROM python:3.10-slim-bookworm@sha256:68d914ec641a0b69267ce65184d000a2bc3a9ee2590ab702b82250ab2385735a
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN python -m pip install pip==25.2 setuptools==80.9.0 wheel==0.45.1
RUN python -m pip install --report /torch-install-report.json torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt /requirements.txt
COPY bp3-0.0.12.7-py2.py3-none-any.whl /bp3-0.0.12.7-py2.py3-none-any.whl
RUN python -m pip install --report /dependency-install-report.json /bp3-0.0.12.7-py2.py3-none-any.whl -r /requirements.txt && python -m pip check
RUN python -m pip freeze --all > /python-freeze.txt && dpkg-query -W > /system-packages.txt
ENV MPLCONFIGDIR=/tmp/matplotlib PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp CUDA_VISIBLE_DEVICES=-1 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8
WORKDIR /app
