#!/usr/bin/env python3
"""Serves the repo for the motion page and saves recordings it uploads to marketing/motion/out/."""
import http.server
import os
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "marketing", "motion", "out")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(url.query)
        name = os.path.basename(q.get("name", ["recording.bin"])[0])
        os.makedirs(OUT, exist_ok=True)
        data = self.rfile.read(int(self.headers["Content-Length"]))
        with open(os.path.join(OUT, name), "wb") as f:
            f.write(data)
        print(f"saved {name} {len(data)} bytes fps={q.get('fps', ['?'])[0]} mime={q.get('mime', ['?'])[0]}", flush=True)
        self.send_response(204)
        self.end_headers()

    def log_message(self, *a):
        pass


http.server.ThreadingHTTPServer(("127.0.0.1", 8770), Handler).serve_forever()
