# W6 offline CPU worker image. FoldX and the worker are immutable read-only
# mounts at execution time; this image contributes only the pinned Python host.
FROM python:3.10-slim-bookworm
LABEL t01.component="foldx-development" \
      t01.foldx.version="5" \
      t01.foldx.executable-sha256="5309d81c3f08b8405d172153aaf9792a244c06f98387c9d57a104302a9cef2cf" \
      t01.base-image-id="sha256:68d914ec641a0b69267ce65184d000a2bc3a9ee2590ab702b82250ab2385735a" \
      t01.network-policy="offline"
ENTRYPOINT ["timeout"]
