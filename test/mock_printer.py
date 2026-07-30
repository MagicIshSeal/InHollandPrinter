import hashlib
import http.server
import json
import os
import socketserver

PORT = 80
REALM = "PrusaLink"
NONCE = "mock-nonce-abc123"

EXPECTED_USERNAME = os.environ.get("LOCAL_USERNAME", "test123")
EXPECTED_PASSWORD = os.environ.get("LOCAL_PASSWORD", "test123")
SNAPSHOT_FILE = os.environ.get("SNAPSHOT_FILE", "/test_img/fail.jpg")
STATE = os.environ.get("PRINTER_STATE", "PRINTING")
TIME_REMAINING = int(os.environ.get("TIME_REMAINING", "3600"))


def _md5(data: str) -> str:
    return hashlib.md5(data.encode()).hexdigest()


def _digest_response(
    username: str, realm: str, password: str,
    method: str, uri: str, nonce: str,
    nc: str, cnonce: str, qop: str,
) -> str:
    ha1 = _md5(f"{username}:{realm}:{password}")
    ha2 = _md5(f"{method}:{uri}")
    return _md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}")


class MockPrusaLinkHandler(http.server.BaseHTTPRequestHandler):

    def _send_401(self):
        self.send_response(401)
        self.send_header(
            "WWW-Authenticate",
            f'Digest realm="{REALM}", nonce="{NONCE}", qop="auth", '
            f'opaque="mock-opaque"',
        )
        self.end_headers()

    def _parse_auth(self) -> dict:
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Digest "):
            return {}
        params = {}
        for part in auth[7:].split(","):
            k, _, v = part.strip().partition("=")
            params[k] = v.strip('"')
        return params

    def _check_auth(self) -> bool:
        params = self._parse_auth()
        if not params:
            print(f"[mock-printer] No auth header, sending 401")
            return False
        expected = _digest_response(
            EXPECTED_USERNAME, REALM, EXPECTED_PASSWORD,
            self.command, params.get("uri", ""),
            params.get("nonce", ""),
            params.get("nc", "00000001"),
            params.get("cnonce", ""),
            params.get("qop", "auth"),
        )
        result = params.get("response") == expected
        if not result:
            print(f"[mock-printer] Auth mismatch: got={params.get('response')}, "
                  f"expected={expected}, uri={params.get('uri')}")
        return result

    def _status(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        body = {
            "printer": {
                "state": STATE,
                "temp_nozzle": 215,
                "temp_bed": 60,
            },
            "job": {
                "id": "42",
                "time_remaining": TIME_REMAINING,
            },
        }
        self.wfile.write(json.dumps(body).encode())

    def _snapshot(self):
        try:
            with open(SNAPSHOT_FILE, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(500)
            self.end_headers()

    def do_GET(self):
        path = self.path
        if not self._check_auth():
            return self._send_401()
        if path.endswith("/api/v1/status"):
            self._status()
        elif path.endswith("/api/v1/cameras/snap"):
            self._snapshot()
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        if not self._check_auth():
            return self._send_401()
        print(f"[mock-printer] Job cancelled via {self.path}")
        self.send_response(204)
        self.end_headers()

    def log_message(self, fmt, *args):
        print(f"[mock-printer] {args[0]} {args[1]} {args[2]}")


if __name__ == "__main__":
    with socketserver.TCPServer(("0.0.0.0", PORT), MockPrusaLinkHandler) as httpd:
        print(f"Mock PrusaLink printer on port {PORT}, "
              f"state={STATE}, "
              f"time_remaining={TIME_REMAINING}s")
        print(f"Snapshot file: {SNAPSHOT_FILE}")
        print(f"Credentials: {EXPECTED_USERNAME} / {EXPECTED_PASSWORD}")
        httpd.serve_forever()
