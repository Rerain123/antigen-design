"""Publish the verified ESMFold2 backend control image through the established cluster relay."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import time
import urllib.parse


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper_path = ROOT / '.tmp/publish_resident_images.py'
if hashlib.sha256(helper_path.read_bytes()).hexdigest() != '1c3c5f007d58be0c2b04750f2c2733cb5a934fc0b5296de86705abd1cbc761de':
    raise ValueError('Established registry publisher changed; review before upload')
publisher = load("publisher", helper_path)
bundle = load("bundle", ROOT / "scripts/resident_bundle.py")
OUT = ROOT / ".tmp/esmfold2-backend-publish-20260917-r03"

publisher.OUT = OUT
publisher.STATE = OUT / "upload-state.json"
publisher.POD = "antigen-esmfold2-backend-relay-r03"


class Registry(publisher.Registry):
    def token_for(self, repo):
        if repo != "qcyz/antigen-design":
            raise RuntimeError("Unexpected repository")
        query = urllib.parse.urlencode(
            [("service", "harbor-registry"), ("scope", "repository:" + repo + ":pull,push")]
        )
        status, _, data = self.raw(
            "GET", "/service/token?" + query, headers={"Authorization": "Basic " + self.auth}
        )
        if status != 200:
            raise RuntimeError("Token HTTP " + str(status))
        value = json.loads(data)
        self.token = value.get("token") or value["access_token"]
        self.repo = repo
        self.issued = time.monotonic()


EXPECTED_INDEX = "sha256:3b3f4b19285467d841b627cb6e17bdd763e17e602f2b0aafdc17180488cc748b"
EXPECTED_PLATFORM = "sha256:0e572b386fd2ad45d3d9b844910b3ff6fb01ce0ad5d42a1be27e183fb76bdb2b"


def validate_image(native, platform):
    if native["Id"] != EXPECTED_INDEX or platform["Descriptor"]["digest"] != EXPECTED_PLATFORM:
        raise ValueError("Image tag changed from the user-built verified image")
    if platform.get("Os") != "linux" or platform.get("Architecture") != "amd64":
        raise ValueError("Expected linux/amd64 image")


def main():
    tag = "antigen-design:esmfold2-backend-r03"
    archive = OUT / "control-linux-amd64.tar"
    native = json.loads(subprocess.check_output(["docker", "image", "inspect", tag]))[0]
    platform = json.loads(
        subprocess.check_output(["docker", "image", "inspect", "--platform", "linux/amd64", tag])
    )[0]
    validate_image(native, platform)
    OUT.mkdir(parents=True, exist_ok=True)
    rows = {
        "control": {
            "tag": tag,
            "image_id": native["Id"],
            "export_manifest_digest": platform["Descriptor"]["digest"],
            "repository": "qcyz/antigen-design",
            "publish_tag": "esmfold2-backend-r03",
        }
    }
    (OUT / "images.json").write_text(json.dumps(rows, indent=2) + "\n")
    if not archive.exists():
        subprocess.run(
            ["docker", "save", "--platform", "linux/amd64", "-o", str(archive), tag],
            check=True,
        )
    verified = bundle.verify_images_archive(archive, rows)
    (OUT / "export-verification.json").write_text(json.dumps(verified, indent=2) + "\n")
    print("EXPORT_VERIFIED", platform["Descriptor"]["digest"], archive.stat().st_size, flush=True)

    secret = json.loads(publisher.kc("get", "secret", "harbor", "-o", "json", "--request-timeout=20s"))
    config = json.loads(base64.b64decode(secret["data"][".dockerconfigjson"]))
    entry = config["auths"][publisher.HOST]
    auth = entry.get("auth") or base64.b64encode(
        (entry["username"] + ":" + entry["password"]).encode()
    ).decode()
    pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": publisher.POD, "namespace": "him-ws", "labels": {"app": publisher.POD}},
        "spec": {
            "restartPolicy": "Never",
            "automountServiceAccountToken": False,
            "imagePullSecrets": [{"name": "harbor"}],
            "securityContext": {"runAsNonRoot": True, "runAsUser": 10001, "runAsGroup": 10001},
            "containers": [
                {
                    "name": "relay",
                    "image": "harbor-core.base.svc.cluster.local/qcyz/antigen-design@sha256:fba5a32c0550e56a5310160e2fc49d647fcd27d76851073a2d82cc935fb4c2fc",
                    "command": ["python", "-u", "-c", publisher.RELAY],
                    "resources": {
                        "requests": {"cpu": "100m", "memory": "64Mi"},
                        "limits": {"cpu": "1", "memory": "256Mi"},
                    },
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "readOnlyRootFilesystem": True,
                        "capabilities": {"drop": ["ALL"]},
                    },
                }
            ],
        },
    }
    existing = json.loads(
        publisher.kc("get", "pod", publisher.POD, "--ignore-not-found", "-o", "json") or b"null"
    )
    if existing:
        raise RuntimeError("Refusing to reuse an existing relay pod")
    publisher.kc("create", "-f", "-", data=json.dumps(pod).encode())
    forward = None
    try:
        publisher.kc("wait", "--for=condition=Ready", "pod/" + publisher.POD, "--timeout=120s")
        forward = subprocess.Popen(
            publisher.ARGS
            + [
                "port-forward",
                "--address",
                "127.0.0.1",
                "pod/" + publisher.POD,
                f"{publisher.PORT}:{publisher.PORT}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        for _ in range(120):
            if forward.poll() is not None:
                raise RuntimeError("Port forward exited")
            try:
                with socket.create_connection(("127.0.0.1", publisher.PORT), timeout=1):
                    break
            except OSError:
                time.sleep(0.5)
        else:
            raise RuntimeError("Port forward not ready")
        publisher.publish(Registry(auth), archive, rows)
    finally:
        if forward is not None:
            forward.terminate()
            forward.wait(timeout=15)
        publisher.kc("delete", "pod", publisher.POD, "--wait=true", "--timeout=60s")
        print("TEMP_RELAY_REMOVED", flush=True)


if __name__ == "__main__":
    main()
