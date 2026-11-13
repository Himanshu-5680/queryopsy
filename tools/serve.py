"""Local dev server with the right MIME types (WebAssembly needs application/wasm).

    python tools/serve.py [port]      -> http://localhost:8000
"""
import functools
import http.server
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".wasm": "application/wasm", ".py": "text/plain; charset=utf-8", ".sqlite": "application/octet-stream",
                      ".webmanifest": "application/manifest+json", ".json": "application/json", ".js": "text/javascript"}

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, *args):
        if "-v" in sys.argv:
            super().log_message(*args)


def main(port: int = 8000) -> None:
    handler = functools.partial(Handler, directory=str(ROOT))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as srv:
        print(f"Queryopsy on http://localhost:{port}  (Ctrl+C to stop)")
        srv.serve_forever()


if __name__ == "__main__":
    main(int(next((a for a in sys.argv[1:] if a.isdigit()), 8000)))
