FROM python@sha256:68d914ec641a0b69267ce65184d000a2bc3a9ee2590ab702b82250ab2385735a
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir pip==25.1.1 typing-extensions==4.14.1
RUN python -m pip install --no-cache-dir --report /proteinmpnn-pip-install.json numpy==1.26.4 torch==2.7.1+cu128 --index-url https://download.pytorch.org/whl/cu128
RUN python -m pip freeze --all > /proteinmpnn-pip-freeze.txt && dpkg-query -W > /proteinmpnn-dpkg.txt
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
