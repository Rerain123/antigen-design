FROM t01-proteinmpnn-development:8907e667-cu128-20260908

# ThermoMPNN's published checkpoint was written by PyTorch Lightning 2.0.2.
# Keep the original CUDA-enabled torch from the immutable ProteinMPNN base and
# pin only the additional runtime libraries used by the official inference path.
RUN python -m pip install --no-cache-dir --report /thermompnn-pip-install.json \
    biopython==1.85 \
    joblib==1.4.2 \
    omegaconf==2.3.0 \
    pandas==2.2.3 \
    pytorch-lightning==2.0.2 \
    scikit-learn==1.6.1 \
    scipy==1.15.2 \
    torchmetrics==0.11.4 \
    tqdm==4.67.1 \
    wandb==0.19.10
RUN python -m pip freeze --all > /thermompnn-pip-freeze.txt && dpkg-query -W > /thermompnn-dpkg.txt

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1
