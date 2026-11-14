"""Entry point executed by src/boot.js once Pyodide and sqlite3 are ready."""
import json
import sys

from js import document
from pyodide.http import pyfetch


async def start():
    resp = await pyfetch("data/cases.json")
    data = json.loads(await resp.string())
    data["python"] = ".".join(map(str, sys.version_info[:2]))
    if document.documentElement.classList.contains("app-mode"):
        from ui.appmode import IOSApp as App      # Android app, installed PWA, phones: native-style shell
    else:
        from ui.app import App                   # website: case-file dossier layout
    app = App(data)
    app.start()
    document.documentElement.setAttribute("data-engine", "ready")
    return app
