#!/usr/bin/env python3
import argparse
import json
import os
import secrets
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

CHUNK = 4 * 1024 * 1024


def fmt_rate(value):
    mb = value / (1024 * 1024)
    return f"{mb:.2f} MB/s"


def request_json(url, data=None, method=None, headers=None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def create_test_file(path, size_bytes):
    block = bytes((i % 251 for i in range(1024 * 1024)))
    remaining = size_bytes
    with open(path, "wb", buffering=0) as f:
        while remaining:
            chunk = block[: min(len(block), remaining)]
            f.write(chunk)
            remaining -= len(chunk)


def upload(base, path):
    path = Path(path)
    total = path.stat().st_size
    upload_id = secrets.token_hex(16)
    offset = 0
    result = {}
    started = time.perf_counter()
    with path.open("rb", buffering=0) as f:
        first = True
        while first or offset < total:
            first = False
            f.seek(offset)
            body = f.read(min(CHUNK, total - offset)) if total else b""
            checksum = f"{zlib.crc32(body) & 0xffffffff:08x}"
            query = urllib.parse.urlencode({"name": path.name, "offset": offset, "total": total})
            req = urllib.request.Request(
                base.rstrip("/") + "/upload?" + query,
                data=body,
                method="PUT",
                headers={
                    "Content-Type": "application/octet-stream",
                    "X-DeckyShare-CRC32": checksum,
                    "X-DeckyShare-Upload-ID": upload_id,
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    result = json.loads(r.read().decode("utf-8") or "{}")
            except urllib.error.HTTPError as e:
                payload = e.read().decode("utf-8", "replace")
                if e.code == 409:
                    result = json.loads(payload or "{}")
                    offset = int(result.get("received", offset))
                    continue
                raise RuntimeError(f"upload failed HTTP {e.code}: {payload}") from e
            offset = int(result.get("received", offset))
            if result.get("complete"):
                break
    elapsed = max(0.001, time.perf_counter() - started)
    return {
        "seconds": elapsed,
        "bytes": total,
        "rate": total / elapsed,
        "saved_name": result.get("name", path.name),
        "upload_id": upload_id,
    }


def select_uploaded(base, saved_name):
    status = request_json(base.rstrip("/") + "/api/status")
    receive_dir = status.get("receive_dir")
    if not receive_dir:
        raise RuntimeError("receive_dir missing from /api/status")
    payload = json.dumps({"path": str(Path(receive_dir) / saved_name)}).encode()
    return request_json(
        base.rstrip("/") + "/api/select",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )


def download(base, expected_size):
    started = time.perf_counter()
    received = 0
    req = urllib.request.Request(base.rstrip("/") + "/download")
    with urllib.request.urlopen(req, timeout=180) as r:
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            received += len(chunk)
    elapsed = max(0.001, time.perf_counter() - started)
    if received != expected_size:
        raise RuntimeError(f"download size mismatch: expected {expected_size}, got {received}")
    return {"seconds": elapsed, "bytes": received, "rate": received / elapsed}


def main():
    ap = argparse.ArgumentParser(description="DeckyShare real-device upload/download benchmark")
    ap.add_argument("base_url", help="DeckyShare URL, e.g. http://192.168.1.50:8787")
    ap.add_argument("--size-gb", type=float, default=1.0, help="Test file size in GiB (default: 1)")
    ap.add_argument("--file", help="Use an existing file instead of generating one")
    ap.add_argument("--keep", action="store_true", help="Keep generated local test file")
    args = ap.parse_args()

    generated = False
    temp_path = None
    if args.file:
        test_path = Path(args.file).expanduser().resolve()
    else:
        size_bytes = int(args.size_gb * 1024 * 1024 * 1024)
        fd, temp_path = tempfile.mkstemp(prefix="deckyshare-benchmark-", suffix=".bin")
        os.close(fd)
        test_path = Path(temp_path)
        generated = True
        print(f"Generating {args.size_gb:g} GiB test file at {test_path} ...")
        create_test_file(test_path, size_bytes)

    try:
        print(f"Uploading {test_path.name} ({test_path.stat().st_size / (1024**3):.2f} GiB) ...")
        up = upload(args.base_url, test_path)
        print(f"Upload:   {up['seconds']:.2f}s  {fmt_rate(up['rate'])}")

        select_uploaded(args.base_url, up["saved_name"])
        print("Downloading the same file back to memory sink ...")
        down = download(args.base_url, test_path.stat().st_size)
        print(f"Download: {down['seconds']:.2f}s  {fmt_rate(down['rate'])}")
        print("PASS: byte count matched in both directions")
        print("Note: upload chunks are CRC32-verified by DeckyShare; this benchmark does not perform a whole-file cryptographic hash.")
    finally:
        if generated and temp_path and not args.keep:
            try:
                Path(temp_path).unlink()
            except OSError:
                pass


if __name__ == "__main__":
    main()
