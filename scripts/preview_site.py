#!/usr/bin/env python3
"""Preview only the public site files on the loopback interface."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent.parent
PUBLIC_ROUTES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/privacy.html": "privacy.html",
    "/terms.html": "terms.html",
    "/styles.css": "styles.css",
}


def make_server(root: Path = ROOT, port: int = 8000) -> ThreadingHTTPServer:
    """Create a loopback server with no directory listing or private-file routes."""
    site_root = Path(root).resolve()

    class PublicHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            filename = PUBLIC_ROUTES.get(unquote(urlsplit(self.path).path))
            if filename is None:
                self.send_error(404)
                return
            target = site_root / filename
            if target.is_symlink():
                self.send_error(404)
                return
            try:
                content = target.read_bytes()
            except OSError:
                self.send_error(404)
                return
            content_type = "text/css; charset=utf-8" if filename.endswith(".css") else "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, format, *args):
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), PublicHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    with make_server(port=args.port) as server:
        print(f"Preview: http://127.0.0.1:{server.server_port}/ (Ctrl-C to stop)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
