"""Resumable local-to-PVC transfer through a temporary, loopback-only pod exec."""
from __future__ import annotations

import hashlib
import http.client
import json
from pathlib import Path, PurePosixPath
import socket
import subprocess
import time
import sys
import urllib.parse


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".tmp/esmfold2-pvc-environment-20260916-r01"
OUT = ROOT / ".tmp/esmfold2-environment-upload-20260917-r01"
KUBECTL = "C:/Program Files/Docker/Docker/resources/bin/kubectl.exe"
POD = "antigen-esmfold2-assets-upload"
PORT = 18743
DESTINATION = "/models/esmfold2-environment-20260916-r01"
ARGS = [KUBECTL, "--kubeconfig", str(ROOT / ".tmp/himat.kubeconfig"), "-n", "him-ws"]
FORWARD = None


SERVER = r'''
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib,json,os,urllib.parse,threading
from pathlib import Path,PurePosixPath
ROOT=Path("/models/esmfold2-environment-20260916-r01")
ROOT.mkdir(parents=True,exist_ok=True)
def target(value):
 p=PurePosixPath(value)
 if p.is_absolute() or not p.parts or ".." in p.parts: raise ValueError("unsafe path")
 result=ROOT.joinpath(*p.parts)
 if ROOT not in result.parents: raise ValueError("escaped root")
 return result
def digest(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for b in iter(lambda:f.read(8*1024*1024),b""):h.update(b)
 return h.hexdigest()
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,status,value):
  data=json.dumps(value).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
 def do_POST(self):
  if self.path != "/shutdown":self.send(404,{});return
  self.send(200,{"stopping":True})
  threading.Thread(target=self.server.shutdown,daemon=True).start()
 def do_GET(self):
  try:
   p=target(urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)["path"][0]);q=p.with_name(p.name+".partial")
   self.send(200,{"size":p.stat().st_size if p.exists() else q.stat().st_size if q.exists() else 0,"complete":p.exists()})
  except Exception as e:self.send(400,{"error":str(e)})
 def do_PATCH(self):
  try:
   p=target(self.headers["X-Path"]);q=p.with_name(p.name+".partial");p.parent.mkdir(parents=True,exist_ok=True)
   offset=int(self.headers["X-Offset"]);length=int(self.headers["Content-Length"]);total=int(self.headers["X-Size"])
   if p.exists():
    if p.stat().st_size!=total:raise ValueError("completed size differs")
    self.rfile.read(length);self.send(200,{"size":total,"complete":True});return
   current=q.stat().st_size if q.exists() else 0
   if current!=offset:raise ValueError("offset differs")
   remaining=length
   with q.open("ab") as f:
    while remaining:
     chunk=self.rfile.read(min(1024*1024,remaining))
     if not chunk:raise ValueError("short request body")
     f.write(chunk);remaining-=len(chunk)
    f.flush();os.fsync(f.fileno())
   self.send(200,{"size":q.stat().st_size,"complete":False})
  except Exception as e:self.send(409,{"error":str(e)})
 def do_PUT(self):
  try:
   p=target(self.headers["X-Path"]);q=p.with_name(p.name+".partial");expected=self.headers["X-Sha256"]
   if p.exists():q=p
   actual=digest(q)
   if actual!=expected:raise ValueError("sha256 differs")
   if q!=p:q.replace(p)
   self.send(200,{"size":p.stat().st_size,"sha256":actual,"complete":True})
  except Exception as e:self.send(409,{"error":str(e)})
server=ThreadingHTTPServer(("127.0.0.1",18743),Handler)
try:server.serve_forever()
finally:server.server_close()
'''


def wait_port(process: subprocess.Popen) -> None:
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError("port-forward exited")
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=1):
                return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError("port-forward did not become ready")


def reset_forward() -> None:
    global FORWARD
    if FORWARD is not None:
        if FORWARD.poll() is None:
            FORWARD.terminate()
            FORWARD.wait(timeout=15)
        FORWARD = None


def ensure_forward() -> None:
    global FORWARD
    if FORWARD is not None and FORWARD.poll() is None:
        return
    reset_forward()
    FORWARD = subprocess.Popen(
        ARGS + ["port-forward", "--address", "127.0.0.1", "pod/" + POD, f"{PORT}:{PORT}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    wait_port(FORWARD)


def request(method: str, path: str, body=None, headers=None):
    for attempt in range(4):
        ensure_forward()
        connection = http.client.HTTPConnection("127.0.0.1", PORT, timeout=600)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            value = json.loads(response.read())
            if response.status >= 300:
                raise RuntimeError(f"upload HTTP {response.status}: {value}")
            return value
        except (OSError, http.client.HTTPException):
            if attempt == 3:
                raise
            reset_forward()
            time.sleep(2)
        finally:
            connection.close()
    raise RuntimeError("request retries exhausted")


def status(relative: str):
    return request("GET", "/status?" + urllib.parse.urlencode({"path": relative}))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def transfer(relative: str, expected_size: int, expected_sha256: str):
    path = SOURCE / PurePosixPath(relative)
    if path.stat().st_size != expected_size or sha256_file(path) != expected_sha256:
        raise RuntimeError("local integrity failed: " + relative)
    state = status(relative)
    offset = state["size"]
    if state["complete"] and offset == expected_size:
        result = request("PUT", "/complete", headers={"X-Path": relative, "X-Sha256": expected_sha256})
        print("ALREADY_VERIFIED", relative, flush=True)
        return result
    if offset > expected_size:
        raise RuntimeError("remote partial exceeds source: " + relative)
    started = time.monotonic()
    stalled = 0
    with path.open("rb") as stream:
        stream.seek(offset)
        while offset < expected_size:
            chunk = stream.read(min(128 * 1024 * 1024, expected_size - offset))
            try:
                value = request(
                    "PATCH",
                    "/upload",
                    body=chunk,
                    headers={
                        "Content-Type": "application/octet-stream",
                        "X-Path": relative,
                        "X-Offset": str(offset),
                        "X-Size": str(expected_size),
                    },
                )
                offset = value["size"]
                stalled = 0
            except (OSError, http.client.HTTPException, RuntimeError):
                stalled += 1
                if stalled >= 8:
                    raise RuntimeError("Transfer repeatedly failed; partial retained, rerun after checking connection")
                time.sleep(2)
                offset = status(relative)["size"]
                stream.seek(offset)
            if offset == expected_size or offset % (256 * 1024 * 1024) < 128 * 1024 * 1024:
                elapsed = max(time.monotonic() - started, 0.001)
                print("PROGRESS", relative, round(100 * offset / expected_size, 2), "percent", round(offset / 1024**2 / elapsed, 2), "MiB_s", flush=True)
    return request("PUT", "/complete", headers={"X-Path": relative, "X-Sha256": expected_sha256})


def main():
    global FORWARD
    manifest_path = SOURCE / "environment-pvc-manifest.json"
    if sha256_file(manifest_path) != "c719aade5db1dacf747cf1f882061a132558ae359bc5a5dd58fc1f5c955bab39":
        raise RuntimeError("Environment manifest differs from fixed worker profile")
    manifest = json.loads(manifest_path.read_bytes())
    rows = list(manifest["files"])
    rows.append({"path": "environment-pvc-manifest.json", "bytes": manifest_path.stat().st_size, "sha256": sha256_file(manifest_path)})
    for row in rows:
        path = SOURCE / row["path"]
        if path.stat().st_size != row["bytes"] or sha256_file(path) != row["sha256"]:
            raise RuntimeError("Local environment integrity failed: " + row["path"])
    print("LOCAL_ENVIRONMENT_VERIFIED", len(rows), sum(r["bytes"] for r in rows), flush=True)
    if "--check-only" in sys.argv:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    server_log = (OUT / "server.log").open("wb")
    server = subprocess.Popen(ARGS + ["exec", POD, "--", "python", "-u", "-c", SERVER], stdout=server_log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    receipts = []
    try:
        time.sleep(1)
        if server.poll() is not None:
            raise RuntimeError("upload server failed to start")
        ensure_forward()
        for row in rows:
            result = transfer(row["path"], row["bytes"], row["sha256"])
            receipts.append({"path": row["path"], **result})
            (OUT / "receipts.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8")
            print("VERIFIED_REMOTE", row["path"], result["sha256"], flush=True)
        print("ESMFOLD2_ENVIRONMENT_ARCHIVE_UPLOADED", len(receipts), sum(r["size"] for r in receipts), flush=True)
    finally:
        # Stop the helper itself before closing the exec stream.
        if server.poll() is None:
            try:
                request("POST", "/shutdown")
            except Exception:
                print("UPLOAD_HELPER_CLEANUP_UNCONFIRMED", flush=True)
        reset_forward()
        server.terminate()
        server.wait(timeout=15)
        server_log.close()


if __name__ == "__main__":
    main()
