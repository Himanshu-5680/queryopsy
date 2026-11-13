"""Build the signed Android APK (plain WebView shell, no Gradle needed).

    python tools/build_apk.py

Needs: JDK 17 (JAVA_HOME) and the Android SDK (ANDROID_HOME) with build-tools + a platform.
Signing: keystore.properties (storeFile, keyAlias, storePassword) found via QUERYOPSY_SIGNING
(default: ../signing/ next to the repo - never commit the keystore). Output: dist/Queryopsy-v<ver>.apk
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_web  # noqa: E402

AND, BUILD, DIST = ROOT / "android", ROOT / "build" / "apk", ROOT / "dist"
MIN_SDK = 24


def sdk_paths():
    sdk = pathlib.Path(os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or "")
    java = pathlib.Path(os.environ.get("JAVA_HOME", ""))
    if not (sdk / "build-tools").is_dir():
        raise SystemExit("Set ANDROID_HOME to an Android SDK with build-tools and a platform installed.")
    bt = sorted((sdk / "build-tools").iterdir(), key=lambda p: [int(x) if x.isdigit() else 0 for x in p.name.split(".")])[-1]
    plat = sorted((sdk / "platforms").iterdir(), key=lambda p: int(p.name.split("-")[-1]))[-1]
    return bt, plat / "android.jar", int(plat.name.split("-")[-1]), java


def run(*cmd, **kw):
    print("+", " ".join(str(c) for c in cmd)[:160])
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def signing():
    d = pathlib.Path(os.environ.get("QUERYOPSY_SIGNING", ROOT.parent / "signing"))
    props = dict(l.strip().split("=", 1) for l in (d / "keystore.properties").read_text().splitlines() if "=" in l and not l.startswith("#"))
    return d / props["storeFile"], props["keyAlias"], props["storePassword"]


def main():
    bt, android_jar, target, java = sdk_paths()
    if java.name:
        os.environ["PATH"] = f"{java / 'bin'}{os.pathsep}{os.environ['PATH']}"
    ver = json.loads((ROOT / "version.json").read_text())
    site = build_web.build()
    shutil.rmtree(BUILD, ignore_errors=True)
    for d in ("gen", "classes", "dex", "assets"):
        (BUILD / d).mkdir(parents=True)
    shutil.copytree(site, BUILD / "assets" / "www", ignore=shutil.ignore_patterns("sw.js", "precache.json", ".nojekyll", "*.sql"))
    tool = lambda n: bt / n  # noqa: E731
    run(tool("aapt2"), "compile", "--dir", AND / "res", "-o", BUILD / "res.zip")
    unsigned = BUILD / "unsigned.apk"
    run(tool("aapt2"), "link", "-o", unsigned, "-I", android_jar, "--manifest", AND / "AndroidManifest.xml",
        "--min-sdk-version", MIN_SDK, "--target-sdk-version", target, "--version-code", ver["versionCode"],
        "--version-name", ver["versionName"], "--java", BUILD / "gen", "-A", BUILD / "assets",
        BUILD / "res.zip")
    srcs = [p for base in (AND / "java", BUILD / "gen") for p in base.rglob("*.java")]
    javac = java / "bin" / "javac" if java.name else "javac"
    run(javac, "-nowarn", "-Xlint:-options", "-source", "8", "-target", "8", "-encoding", "UTF-8",
        "-bootclasspath", f"{android_jar}{os.pathsep}{tool('core-lambda-stubs.jar')}", "-d", BUILD / "classes", *srcs)
    classes = list((BUILD / "classes").rglob("*.class"))
    run(tool("d8"), "--release", "--min-api", MIN_SDK, "--lib", android_jar, "--output", BUILD / "dex", *classes)
    with zipfile.ZipFile(unsigned, "a", zipfile.ZIP_DEFLATED) as z:
        z.write(BUILD / "dex" / "classes.dex", "classes.dex")
    aligned = BUILD / "aligned.apk"
    run(tool("zipalign"), "-f", "-p", "4", unsigned, aligned)
    ks, alias, pw = signing()
    DIST.mkdir(exist_ok=True)
    out = DIST / f"Queryopsy-v{ver['versionName']}.apk"
    env = dict(os.environ, KS_PASS=pw, PATH=f"{java / 'bin'}{os.pathsep}{os.environ['PATH']}")
    run(tool("apksigner"), "sign", "--ks", ks, "--ks-key-alias", alias, "--ks-pass", "env:KS_PASS", "--key-pass", "env:KS_PASS",
        "--v1-signing-enabled", "true", "--v2-signing-enabled", "true", "--v3-signing-enabled", "true", "--out", out, aligned, env=env)
    for f in DIST.glob("*.idsig"):
        f.unlink()
    print(f"apk: {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
