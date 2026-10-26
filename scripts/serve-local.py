#!/usr/bin/env python3
"""Serve a generated archive only on loopback."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


ACTIVE_MEDIA_SUFFIXES = {".htm", ".html", ".mht", ".mhtml", ".svg", ".xhtml"}


class ArchiveHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        path = unquote(urlsplit(self.path).path)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if path.startswith("/media/"):
            self.send_header("Content-Security-Policy", "sandbox; default-src 'none'")
            if Path(path).suffix.lower() in ACTIVE_MEDIA_SUFFIXES:
                self.send_header("Content-Disposition", "attachment")
        super().end_headers()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    directory = args.directory.resolve()
    if not directory.is_dir():
        parser.error(f"archive directory does not exist: {directory}")

    handler = partial(ArchiveHandler, directory=str(directory))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"Serving {directory} at http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
