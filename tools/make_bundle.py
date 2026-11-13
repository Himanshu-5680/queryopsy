"""Package the repository + release assets into dist/queryopsy-github.zip (single folder queryopsy/).

    python tools/make_bundle.py
Excludes git metadata, build output, virtualenvs, caches and raw data. Signing material never lives in the repo.
"""
import json
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
SKIP_DIRS = {".git", "build", "dist", ".venv", "venv", "__pycache__", ".pytest_cache", "test-results", "node_modules", "release-assets"}
SKIP_SUFFIX = {".pyc", ".keystore", ".jks"}
SKIP_NAMES = {"keystore.properties", ".DS_Store"}


def files():
    for p in sorted(ROOT.rglob("*")):
        rel = p.relative_to(ROOT)
        if not p.is_file() or set(rel.parts[:-1]) & SKIP_DIRS or p.suffix in SKIP_SUFFIX or p.name in SKIP_NAMES:
            continue
        if rel.parts[:2] == ("data", "raw") and p.name != "README.md":
            continue
        yield p, rel


def main():
    ver = json.loads((ROOT / "version.json").read_text())["versionName"]
    assets = [DIST / f"Queryopsy-v{ver}.apk", DIST / f"queryopsy-web-v{ver}.zip"]
    for a in assets:
        if not a.exists():
            raise SystemExit(f"missing {a}: run tools/build_web.py and tools/build_apk.py first")
    out = DIST / "queryopsy-github.zip"
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p, rel in files():
            info = zipfile.ZipInfo.from_file(p, f"queryopsy/{rel.as_posix()}")
            if p.name == "publish.sh":
                info.external_attr = 0o100755 << 16
            z.writestr(info, p.read_bytes(), zipfile.ZIP_DEFLATED)
            n += 1
        for a in assets:
            z.write(a, f"queryopsy/release-assets/{a.name}")
    print(f"bundle: {out} ({out.stat().st_size / 1e6:.1f} MB, {n} repo files + {len(assets)} release assets)")


if __name__ == "__main__":
    main()
