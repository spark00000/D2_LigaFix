from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

# Python-only converter: vendor sklearn-free fontTools under ROOT/packages so
# the script runs without `pip install` when the vendored copy is present,
# otherwise falls back to an installed fontTools.
PATCH_DIR = Path(__file__).resolve().parent
ROOT = PATCH_DIR.parent
PACKAGES_DIR = ROOT / "packages"
for _p in (PATCH_DIR, PACKAGES_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from fontTools.ttLib import TTFont
except ModuleNotFoundError:
    raise SystemExit(
        "fontTools is required. Run `pip install fonttools` or restore the "
        "vendored copy at packages/ under the project root."
    )

from d2_ligafix_patch import add_dflt_liga_route, inspect_route

RELEASE_URL = "https://github.com/naver/d2-coding-font/releases/download/VER1.3.3/D2Coding-Ver1.3.3-20260725.zip"
RELEASE_SHA256 = "c2a6e364d4102eb2c4de52ffe3d76317c1f4c045e3737e022e69ee0be47f31e2"
UPSTREAM_COMMIT = "9d6f0559691ebe670a23fbf7b72a8dc42362f1fb"
REGULAR_BLOB = "4e6b159fa85571bdfe648ad5d37af733e185f860"
BOLD_BLOB = "aa514b7b15bf68bfd87d689f808ba923f19264bc"
DERIVATIVE_FAMILY = "D2_LigaFix"
DERIVATIVE_VERSION = "0.3.0"
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "_work"
DEFAULT_OUT = ROOT / "out"
ARCHIVE = WORK / "D2Coding-Ver1.3.3-20260725.zip"

CORE_TABLES = ("glyf", "loca", "hmtx", "cmap")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha1(data: bytes) -> str:
    h = hashlib.sha1()
    h.update(b"blob %d\x00" % len(data))
    h.update(data)
    return h.hexdigest()


def obtain_archive(explicit: Path | None) -> Path:
    WORK.mkdir(exist_ok=True)
    if explicit is not None:
        archive = explicit.resolve()
        if not archive.is_file():
            raise RuntimeError(f"Archive not found: {archive}")
    else:
        archive = ARCHIVE
        if not archive.exists() or sha256_file(archive) != RELEASE_SHA256:
            archive.unlink(missing_ok=True)
            print(f"[DOWNLOAD] {RELEASE_URL}")
            req = urllib.request.Request(RELEASE_URL, headers={"User-Agent": "D2_LigaFix/0.3"})
            with urllib.request.urlopen(req, timeout=120) as response, archive.open("wb") as out:
                shutil.copyfileobj(response, out)

    digest = sha256_file(archive)
    if digest != RELEASE_SHA256:
        raise RuntimeError(
            "Official D2Coding 1.3.3 archive SHA-256 mismatch\n"
            f"Expected: {RELEASE_SHA256}\nActual:   {digest}"
        )
    print(f"[OK] official archive SHA-256: {digest}")
    return archive


def safe_extract(archive: Path) -> Path:
    root = WORK / "official"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    root_resolved = root.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            dest = (root / member.filename).resolve()
            if dest != root_resolved and root_resolved not in dest.parents:
                raise RuntimeError(f"Unsafe archive member: {member.filename}")
        zf.extractall(root)
    return root


def find_ligature_fonts(root: Path) -> dict[str, Path]:
    ttfs = list(root.rglob("*.ttf"))
    candidates = [
        p for p in ttfs
        if "ligature" in p.name.lower() or "ligature" in str(p.parent).lower()
    ]
    regular = [p for p in candidates if "bold" not in p.name.lower()]
    bold = [p for p in candidates if "bold" in p.name.lower()]
    if len(regular) != 1 or len(bold) != 1:
        listing = "\n".join(f"  {p.relative_to(root)}" for p in ttfs)
        raise RuntimeError(f"Could not uniquely locate ligature Regular/Bold TTFs:\n{listing}")
    return {"Regular": regular[0], "Bold": bold[0]}


def set_name(font: TTFont, name_id: int, value: str) -> None:
    for platform_id, encoding_id, lang_id in ((3, 1, 0x0409), (3, 10, 0x0409), (1, 0, 0)):
        try:
            font["name"].setName(value, name_id, platform_id, encoding_id, lang_id)
        except Exception:
            pass


def rename_derivative(font: TTFont, style: str, source_label: str) -> None:
    family = DERIVATIVE_FAMILY
    full = f"{family} {style}"
    ps_style = re.sub(r"[^A-Za-z0-9]", "", style)
    ps_prefix = re.sub(r"[^A-Za-z0-9]", "", family)
    set_name(font, 1, family)
    set_name(font, 2, style)
    set_name(font, 3, f"{ps_prefix}-{DERIVATIVE_VERSION}-{style}")
    set_name(font, 4, full)
    set_name(font, 5, f"Version {DERIVATIVE_VERSION}; derived from {source_label}")
    set_name(font, 6, f"{ps_prefix}-{ps_style}")
    set_name(font, 16, family)
    set_name(font, 17, style)


def table_hash(path: Path, tag: str) -> str:
    font = TTFont(path, recalcBBoxes=False, recalcTimestamp=False)
    try:
        return hashlib.sha256(font.getTableData(tag)).hexdigest()
    finally:
        font.close()


def patch_one(src: Path, dst: Path, style: str, source_label: str) -> None:
    before = {tag: table_hash(src, tag) for tag in CORE_TABLES}
    font = TTFont(src, recalcBBoxes=False, recalcTimestamp=False)
    try:
        info = add_dflt_liga_route(font)
        rename_derivative(font, style, source_label)
        if "DSIG" in font:
            del font["DSIG"]
        font.recalcTimestamp = False
        dst.parent.mkdir(parents=True, exist_ok=True)
        font.save(dst, reorderTables=False)
    finally:
        font.close()

    after = {tag: table_hash(dst, tag) for tag in CORE_TABLES}
    if before != after:
        raise RuntimeError(f"Core outline/metric/cmap table changed for {style}: {before} != {after}")

    check = TTFont(dst)
    try:
        route = inspect_route(check)
    finally:
        check.close()
    if not route["dflt_liga_indices"] or route["has_hang_script"]:
        raise RuntimeError(f"Unexpected patched GSUB route for {style}: {route}")
    print(f"[OK] {style}: {info}; route={route}")
    print(f"[OK] wrote {dst.name} ({dst.stat().st_size:,} bytes)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", type=Path, help="Pre-downloaded official D2Coding 1.3.3 ZIP")
    ap.add_argument("--regular", type=Path, help="Direct upstream ligature Regular TTF")
    ap.add_argument("--bold", type=Path, help="Direct upstream ligature Bold TTF")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    if bool(args.regular) != bool(args.bold):
        raise SystemExit("--regular and --bold must be supplied together")

    if args.regular and args.bold:
        sources = {"Regular": args.regular.resolve(), "Bold": args.bold.resolve()}
        blobs = {"Regular": REGULAR_BLOB, "Bold": BOLD_BLOB}
        for style, p in sources.items():
            if not p.is_file():
                raise SystemExit(f"Source font not found: {p}")
            data = p.read_bytes()
            if git_blob_sha1(data) != blobs[style]:
                raise SystemExit(
                    f"Git blob verification failed for {style}: {p}\n"
                    f"Expected: {blobs[style]}"
                )
            print(f"[OK] {style} Git blob {blobs[style]}")
        source_label = f"D2Coding master {UPSTREAM_COMMIT[:12]}"
    else:
        archive = obtain_archive(args.archive)
        official = safe_extract(archive)
        sources = find_ligature_fonts(official)
        source_label = "D2Coding 1.3.3"

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    for style, src in sources.items():
        print(f"[SOURCE] {style}: {src}")
        patch_one(src, out / f"D2_LigaFix-{style}.ttf", style, source_label)

    print("\n[BUILD PASS] D2_LigaFix Regular/Bold generated and core font tables verified unchanged.")


if __name__ == "__main__":
    main()
