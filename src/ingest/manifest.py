"""Rebuild data/raw/MANIFEST.csv (file, type, sha256, size, first_seen). Never modifies raw files."""

import csv
import hashlib
from datetime import datetime
from pathlib import Path

RAW = Path("data/raw")
MANIFEST = RAW / "MANIFEST.csv"
FIELDS = ["file", "type", "sha256", "bytes", "downloaded_at"]


def main() -> None:
    old = {}
    if MANIFEST.exists():
        with MANIFEST.open(encoding="utf-8") as f:
            old = {r["file"]: r for r in csv.DictReader(f)}
    rows = []
    for p in sorted(RAW.rglob("*")):
        if not p.is_file() or p == MANIFEST or p.name.startswith("."):
            continue
        rel = str(p.relative_to(RAW))
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        prev = old.get(rel, {})
        if prev.get("sha256") not in (None, sha):
            print(f"WARNING: {rel} changed since it was recorded")
        rows.append({"file": rel, "type": p.parent.name, "sha256": sha,
                     "bytes": p.stat().st_size,
                     "downloaded_at": prev.get("downloaded_at") or datetime.now().astimezone().date().isoformat()})
    with MANIFEST.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} files in manifest")


if __name__ == "__main__":
    main()
