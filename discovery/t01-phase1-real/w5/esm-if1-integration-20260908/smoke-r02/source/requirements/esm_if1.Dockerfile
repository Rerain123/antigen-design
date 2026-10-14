FROM sha256:5b6baa8ebc5660bd3de9cf8b6d1694c7de35fadd23fea6cd7a8352a536e3f3af
RUN python -m pip install --no-cache-dir --report /esm-if1-pip-install.json biotite==0.39.0 scipy==1.15.3 torch-geometric==2.6.1
RUN python -m pip freeze --all > /esm-if1-pip-freeze.txt && dpkg-query -W > /esm-if1-dpkg.txt
ENV PYTHONPATH=/app MPLCONFIGDIR=/tmp/matplotlib
