"""Stage the pinned nr mirror snapshot; no scientific query or service mutation."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

BASE = "http://ncbichina.iict.ac.cn:8008/blastdb/20250624/2025-06-24-01-05-02/"
ROOT = Path("/data/nr-20250624")
EXPECTED_BYTES = 613736552406
CHUNK = 8 * 1024 * 1024

def small(name):
    with urlopen(BASE + name, timeout=120) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise RuntimeError("Metadata too large: " + name)
    return raw

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()

def atomic(path, raw):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(raw)
    tmp.replace(path)

def download(name, rawdir):
    target = rawdir / name
    part = rawdir / (name + ".part")
    for attempt in range(6):
        try:
            with urlopen(Request(BASE + name, method="HEAD"), timeout=120) as response:
                length = int(response.headers["Content-Length"])
                validator = response.headers.get("ETag") or response.headers.get("Last-Modified")
            if length <= 0:
                raise RuntimeError("Invalid source size: " + name)
            identity = json.dumps({"url": BASE + name, "bytes": length, "validator": validator}, sort_keys=True).encode()
            identity_path = rawdir / (name + ".source.json")
            if identity_path.exists() and identity_path.read_bytes() != identity:
                raise RuntimeError("Source identity changed; manual inspection required: " + name)
            if not identity_path.exists():
                if target.exists() or part.exists():
                    raise RuntimeError("Untracked existing file: " + name)
                atomic(identity_path, identity)
            if target.exists():
                if target.stat().st_size != length:
                    raise RuntimeError("Completed file size mismatch: " + name)
                return {"path": name, "bytes": length, "sha256": sha256(target), "source_validator": validator}
            offset = part.stat().st_size if part.exists() else 0
            if offset > length:
                raise RuntimeError("Partial file exceeds source size: " + name)
            if offset < length:
                headers = {"Accept-Encoding": "identity"}
                if offset:
                    headers["Range"] = "bytes=" + str(offset) + "-"
                    if validator:
                        headers["If-Range"] = validator
                with urlopen(Request(BASE + name, headers=headers), timeout=120) as response:
                    if response.status == 206:
                        cr = response.headers.get("Content-Range", "")
                        if cr != "bytes " + str(offset) + "-" + str(length - 1) + "/" + str(length):
                            raise RuntimeError("Unexpected Content-Range: " + cr)
                        mode = "ab" if offset else "wb"
                    elif response.status == 200:
                        mode = "wb"
                        if offset:
                            print("RANGE_IGNORED restarting", name, flush=True)
                    else:
                        raise RuntimeError("Unexpected HTTP status")
                    with part.open(mode) as stream:
                        while True:
                            block = response.read(CHUNK)
                            if not block:
                                break
                            stream.write(block)
                            if stream.tell() > length:
                                raise RuntimeError("Response exceeds expected file size")
                if part.stat().st_size != length:
                    raise RuntimeError("Incomplete transfer: " + name)
            part.replace(target)
            return {"path": name, "bytes": length, "sha256": sha256(target), "source_validator": validator}
        except Exception as exc:
            print("RETRY", name, attempt + 1, type(exc).__name__, str(exc), flush=True)
            if attempt == 5:
                raise
            time.sleep(min(60, 2 ** (attempt + 1)))

def main():
    import fcntl
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / "download.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run()

def run():
    rawdir = ROOT / "raw"
    rawdir.mkdir(exist_ok=True)
    metadata_raw = small("nr-prot-metadata.json")
    meta = json.loads(metadata_raw)
    expected = {"dbname": "nr", "dbtype": "Protein", "number-of-volumes": 123,
                "number-of-sequences": 935749080, "number-of-letters": 354907547446,
                "last-updated": "2025-06-22T00:00:00", "bytes-total": EXPECTED_BYTES}
    for key, value in expected.items():
        if meta.get(key) != value:
            raise RuntimeError("Snapshot mismatch: " + key)
    names = []
    for item in meta["files"]:
        name = urlsplit(item).path.rsplit("/", 1)[-1]
        if not re.fullmatch(r"nr\.(?:[0-9]{3}\.)?[a-z]+", name):
            raise RuntimeError("Unexpected database filename: " + name)
        names.append(name)
    if len(names) != 1113 or len(set(names)) != 1113:
        raise RuntimeError("Unexpected file count")
    if set(n for n in names if n.endswith(".psq")) != {f"nr.{i:03d}.psq" for i in range(123)}:
        raise RuntimeError("Missing sequence volume")
    # Some NCBI manifests omit the alias; always include it explicitly.
    names = sorted(set(names) | {"nr.pal"})
    pal = small("nr.pal")
    dbline = next(line for line in pal.decode().splitlines() if line.startswith("DBLIST "))
    if dbline.split()[1:] != [f"nr.{i:03d}" for i in range(123)]:
        raise RuntimeError("Alias volume mismatch")
    metadata_path = ROOT / "nr-prot-metadata.json"
    if metadata_path.exists() and metadata_path.read_bytes() != metadata_raw:
        raise RuntimeError("Previously staged metadata differs")
    atomic(metadata_path, metadata_raw)
    occupied = sum(p.stat().st_size for p in rawdir.iterdir() if p.is_file())
    free = shutil.disk_usage(ROOT).free
    required = max(0, EXPECTED_BYTES - occupied) + 50 * 1024 ** 3
    print("PREFLIGHT", json.dumps({"free_bytes": free, "required_bytes": required, "files": len(names)}), flush=True)
    if free < required:
        raise RuntimeError("Insufficient free space including 50 GiB reserve")
    records = []
    for index, name in enumerate(names, 1):
        print("DOWNLOADING", index, "/", len(names), name, flush=True)
        record = download(name, rawdir)
        records.append(record)
        print("VERIFIED_LOCAL", name, record["bytes"], record["sha256"], flush=True)
    if (rawdir / "nr.pal").read_bytes() != pal or small("nr-prot-metadata.json") != metadata_raw or small("nr.pal") != pal:
        raise RuntimeError("Source metadata/alias changed during download")
    receipt = {"source": BASE, "metadata": expected, "files": records,
               "downloaded_bytes": sum(r["bytes"] for r in records),
               "integrity": "HTTP size checks and locally computed SHA-256; no upstream checksum comparison",
               "status": "STAGED_NOT_N03_ACCEPTED"}
    atomic(ROOT / "download-receipt.json", (json.dumps(receipt, indent=2) + "\n").encode())
    atomic(ROOT / "SHA256SUMS", "".join(r["sha256"] + "  raw/" + r["path"] + "\n" for r in records).encode())
    print("DOWNLOAD_COMPLETE", receipt["downloaded_bytes"], "STAGED_NOT_N03_ACCEPTED", flush=True)

if __name__ == "__main__":
    main()

