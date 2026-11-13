"""Download the pinned third-party runtime into vendor/ (run once; output is committed).

  * Pyodide core (CPython 3.13 compiled to WebAssembly) + its sqlite3 module wheel
  * Space Grotesk + JetBrains Mono fonts (SIL OFL 1.1)

Nothing is ever loaded from a CDN at runtime; the browser and the Android app
use only these local copies.     Usage:  python tools/vendor.py
"""
import hashlib, io, json, pathlib, tarfile, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"
PYODIDE = "0.29.5"
CORE_URL = f"https://github.com/pyodide/pyodide/releases/download/{PYODIDE}/pyodide-core-{PYODIDE}.tar.bz2"
FULL_URL = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE}/full/"
CORE_FILES = ("pyodide.js", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json")
FONTS = {"space-grotesk": ("5.3.0", (400, 500, 700)), "jetbrains-mono": ("5.3.0", (400, 700))}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "queryopsy-vendor"})
    return urllib.request.urlopen(req, timeout=180).read()


def pyodide() -> None:
    out = VENDOR / "pyodide"
    out.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(get(CORE_URL)), mode="r:bz2") as tar:
        for name in CORE_FILES:
            (out / name).write_bytes(tar.extractfile("pyodide/" + name).read())
    lock = json.loads((out / "pyodide-lock.json").read_text())
    pkg = lock["packages"]["sqlite3"]
    whl = get(FULL_URL + pkg["file_name"])
    if hashlib.sha256(whl).hexdigest() != pkg["sha256"]:
        raise SystemExit("sqlite3 wheel checksum mismatch")
    (out / pkg["file_name"]).write_bytes(whl)
    (out / "LICENSE").write_bytes(get(f"https://raw.githubusercontent.com/pyodide/pyodide/{PYODIDE}/LICENSE"))


def fonts() -> None:
    for fam, (ver, weights) in FONTS.items():
        meta = json.loads(get(f"https://registry.npmjs.org/@fontsource/{fam}/{ver}"))
        data = get(meta["dist"]["tarball"])
        if hashlib.sha1(data).hexdigest() != meta["dist"]["shasum"]:
            raise SystemExit("font checksum mismatch " + fam)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            (VENDOR / "fonts").mkdir(parents=True, exist_ok=True)
            for w in weights:
                src = f"package/files/{fam}-latin-{w}-normal.woff2"
                (VENDOR / "fonts" / f"{fam}-{w}.woff2").write_bytes(tar.extractfile(src).read())
            (VENDOR / "fonts" / f"{fam}-OFL.txt").write_bytes(tar.extractfile("package/LICENSE").read())


def main() -> None:
    pyodide()
    fonts()
    (VENDOR / "README.md").write_text(
        "# Vendored runtime (do not edit by hand)\n\n"
        "| Path | What | Licence |\n|---|---|---|\n"
        f"| pyodide/ | Pyodide {PYODIDE} core: CPython 3.13 compiled to WebAssembly, plus its `sqlite3` stdlib module wheel | MPL-2.0 (pyodide/LICENSE); CPython is PSF-licensed; SQLite is public domain |\n"
        "| fonts/space-grotesk-*.woff2 | Space Grotesk (latin subset) via @fontsource | SIL OFL 1.1 (fonts/space-grotesk-OFL.txt) |\n"
        "| fonts/jetbrains-mono-*.woff2 | JetBrains Mono (latin subset) via @fontsource | SIL OFL 1.1 (fonts/jetbrains-mono-OFL.txt) |\n\n"
        "Regenerate with `python tools/vendor.py`.\n", encoding="utf-8")
    print("vendored Pyodide", PYODIDE, "+ fonts")


if __name__ == "__main__":
    main()
