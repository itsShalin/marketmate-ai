"""Stand-in for the real backend so you can develop before it exists (stdlib only).
Run:  python mock_server.py     then set BACKEND_BASE_URL=http://localhost:8000
Routes: /api/business/{id}   /products   /inventory   /engagement
"""
import json, os, re
from http.server import BaseHTTPRequestHandler, HTTPServer
from marketing_agent.mock_data import get_mock

ROUTE = re.compile(r"^/api/business/([^/]+)(?:/(products|inventory|engagement))?$")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        m = ROUTE.match(self.path.split("?")[0])
        if not m:
            return self._send(404, {"error": "not found"})
        data = get_mock(os.getenv("MOCK_SCENARIO", "normal"))
        self._send(200, data[m.group(2) or "profile"])

    def _send(self, code, body):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("Mock backend on http://localhost:8000 (scenario:", os.getenv("MOCK_SCENARIO", "normal") + ")")
    HTTPServer(("localhost", 8000), Handler).serve_forever()
