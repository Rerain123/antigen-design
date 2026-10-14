FROM python:3.8.20-slim-bookworm@sha256:1d52838af602b4b5a831beb13a0e4d073280665ea7be7f69ce2382f29c5a613f
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
RUN python -m pip install pip==24.3.1 setuptools==75.3.2 wheel==0.45.1 Cython==0.29.37 pkgconfig==1.5.5
RUN python -m pip install --report /torch-install-report.json "https://download.pytorch.org/whl/cu92/torch-1.5.0%2Bcu92-cp38-cp38-linux_x86_64.whl#sha256=77586f5deca99bf854dce2bce9e533a90dd97694d190b15bd17c170ef493e2b1"
COPY requirements.txt /requirements.txt
RUN python -m pip install --report /dependency-install-report.json -r /requirements.txt && python -m pip check
RUN python -m pip freeze --all > /python-freeze.txt && dpkg-query -W > /system-packages.txt
ENV MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib PYTHONDONTWRITEBYTECODE=1 HOME=/tmp
WORKDIR /app
