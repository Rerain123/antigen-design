FROM ncbi/blast:2.17.0 AS blast
FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends mmseqs2=14-7e284+ds-1+b2 mafft=7.505-1 liblmdb0 && rm -rf /var/lib/apt/lists/*
COPY --from=blast /blast/bin/ /opt/blast/bin/
COPY --from=blast /blast/lib/ /blast/lib/
ENV LD_LIBRARY_PATH=/blast/lib
ENV PATH=/opt/blast/bin:$PATH

