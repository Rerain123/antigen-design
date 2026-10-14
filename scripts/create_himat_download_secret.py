"""Create the test-only HiMat attachment signing key without persisting or printing it."""
from __future__ import annotations

import base64
import json
import secrets
import subprocess

import prepare_m1_p1_deploy as common


NAME = "antigen-design-himat-download"


def main() -> None:
    exists = subprocess.run(common.K + ["get", "secret", NAME, "-o", "name"],
                            capture_output=True, text=True)
    if exists.returncode == 0:
        print("HIMAT_DOWNLOAD_SECRET_ALREADY_EXISTS", NAME)
        return
    # Hex text avoids newline or encoding ambiguity in the mounted secret file.
    key = secrets.token_hex(32).encode("ascii")
    value = {
        "apiVersion": "v1", "kind": "Secret", "type": "Opaque",
        "metadata": {"name": NAME, "namespace": "him-ws"},
        "data": {"signing-key": base64.b64encode(key).decode("ascii")},
    }
    result = subprocess.run(common.K + ["create", "-f", "-"],
                            input=json.dumps(value).encode("utf-8"),
                            capture_output=True)
    if result.returncode:
        raise RuntimeError("HiMat download secret creation failed")
    print("HIMAT_DOWNLOAD_SECRET_CREATED", NAME)


if __name__ == "__main__":
    main()
