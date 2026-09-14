from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

PATCH_DIR = Path(__file__).resolve().parent
PACKAGES_DIR = PATCH_DIR.parent / "packages"
for _p in (PATCH_DIR, PACKAGES_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from fontTools.ttLib import TTFont

CORE_TABLES = ("glyf", "loca", "hmtx", "cmap")


def table_hash(path: Path, tag: str) -> str:
    font = TTFont(path, recalcBBoxes=False, recalcTimestamp=False)
    try:
        return hashlib.sha256(font.getTableData(tag)).hexdigest()
    finally:
        font.close()


def route_info(path: Path) -> dict[str, object]:
    font = TTFont(path, recalcBBoxes=False, recalcTimestamp=False)
    try:
        gsub = font["GSUB"].table
        records = gsub.FeatureList.FeatureRecord
        liga = [i for i, r in enumerate(records) if r.FeatureTag == "liga"]
        dflt_record = next(r for r in gsub.ScriptList.ScriptRecord if r.ScriptTag == "DFLT")
        dflt = dflt_record.Script.DefaultLangSys
        linked = [i for i in liga if i in (dflt.FeatureIndex or [])]
        lookups = []
        for i in linked:
            lookups.extend(records[i].Feature.LookupListIndex or [])
        return {
            "dflt_liga_registered": bool(linked),
            "dflt_liga_feature_indices": linked,
            "dflt_liga_lookup_count": len(dict.fromkeys(lookups)),
            "has_hang_script": any(r.ScriptTag == "hang" for r in gsub.ScriptList.ScriptRecord),
        }
    finally:
        font.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", required=True, type=Path)
    ap.add_argument("--patched", required=True, type=Path)
    args = ap.parse_args()

    if not args.original.is_file() or not args.patched.is_file():
        raise SystemExit("missing original or patched font")

    for tag in CORE_TABLES:
        a = table_hash(args.original, tag)
        b = table_hash(args.patched, tag)
        if a != b:
            raise SystemExit(f"[FAIL] {tag} changed: {a} != {b}")
        print(f"[PASS] {tag} unchanged {a}")

    info = route_info(args.patched)
    print("route:", info)
    if not info["dflt_liga_registered"]:
        raise SystemExit("[FAIL] DFLT/liga route missing")
    if info["has_hang_script"]:
        raise SystemExit("[FAIL] unexpected hang ScriptRecord")
    if int(info["dflt_liga_lookup_count"]) <= 0:
        raise SystemExit("[FAIL] liga route has no lookups")
    print("[PASS] structural verification")


if __name__ == "__main__":
    main()
