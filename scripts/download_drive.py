"""Download the Polaron hackathon images from the public Google Drive folder.

Usage:
    python scripts/download_drive.py                 # all batches, all channels
    python scripts/download_drive.py --channel BSE   # one channel only (~620 MB)
    python scripts/download_drive.py --batch Batch_1

Writes data/raw/<Batch>/<filename>.tif and data/raw/inventory.csv (name, batch, sample_id,
channel, bytes, sha256). Skips files that already exist with the expected size.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
LISTING = ROOT / "docs" / "Log" / "assets" / "drive_file_listing.json"
RAW = ROOT / "data" / "raw"
URL = "https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t"
NAME_RE = re.compile(r"^img_(?P<sample>[a-z0-9]{8})_(?P<channel>BSE|Inlens|ETD|SE)\.tif$")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(fid: str, dest: Path, expected: int) -> None:
    if dest.exists() and dest.stat().st_size == expected:
        return
    with requests.get(URL.format(fid=fid), stream=True, timeout=120) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(".part")
        with tmp.open("wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        tmp.rename(dest)
    if expected > 0 and dest.stat().st_size != expected:
        raise RuntimeError(f"size mismatch for {dest.name}: {dest.stat().st_size} != {expected}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default=None)
    ap.add_argument("--channel", default=None, choices=["BSE", "Inlens", "ETD", "SE"])
    args = ap.parse_args()

    listing = json.loads(LISTING.read_text())
    rows = []
    for batch, files in listing.items():
        if args.batch and batch != args.batch:
            continue
        (RAW / batch).mkdir(parents=True, exist_ok=True)
        for fid, name, size in files:
            m = NAME_RE.match(name)
            if not m:
                print(f"skip unrecognised name {name}", file=sys.stderr)
                continue
            if args.channel and m["channel"] != args.channel:
                continue
            dest = RAW / batch / name
            print(f"{batch}/{name} ({size/1e6:.1f} MB)")
            download(fid, dest, size)
            rows.append(dict(name=name, batch=batch, sample_id=m["sample"], channel=m["channel"],
                             bytes=dest.stat().st_size, sha256=sha256(dest)))

    inv = RAW / "inventory.csv"
    existing = []
    if inv.exists():
        with inv.open() as f:
            existing = [r for r in csv.DictReader(f) if r["name"] not in {x["name"] for x in rows}]
    with inv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "batch", "sample_id", "channel", "bytes", "sha256"])
        w.writeheader()
        w.writerows(sorted(existing + rows, key=lambda r: (r["batch"], r["name"])))
    print(f"inventory: {inv} ({len(existing) + len(rows)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
