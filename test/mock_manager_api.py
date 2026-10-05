"""
Mock printer-manager API for the Docker test stack.

Accepts POST /cancelled with JSON {printer, reason, image, image_name},
validates the shape (and that `image` really is base64 JPEG when set),
then appends each valid record as a JSON line to a shared volume file
that test/test_api.py asserts against.
"""
import base64
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

RECEIVED_FILE = os.environ.get("MANAGER_RECEIVED_FILE", "/data/manager_received.jsonl")
PORT = int(os.environ.get("MANAGER_API_PORT", "9990"))


class ManagerApiHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length))
            required = {"printer", "reason", "image", "image_name"}
            missing = required - set(payload)
            if missing:
                raise ValueError(f"missing keys: {sorted(missing)}")
            if payload.get("image"):
                if base64.b64decode(payload["image"])[:2] != b"\xff\xd8":
                    raise ValueError("image field is not base64-encoded JPEG")
        except Exception as e:
            print(f"[manager-api] rejected POST: {e}")
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

        os.makedirs(os.path.dirname(RECEIVED_FILE), exist_ok=True)
        with open(RECEIVED_FILE, "a") as f:
            f.write(json.dumps(payload) + "\n")
        print(f"[manager-api] recorded cancel for {payload['printer']!r} "
              f"(reason={payload['reason']!r}, image={payload['image_name']!r})")
        self.send_response(204)
        self.end_headers()

    def log_message(self, fmt, *args):
        print(f"[manager-api] {args[0]} {args[1]} {args[2]}")


if __name__ == "__main__":
    print(f"[manager-api] listening on :{PORT}, recording to {RECEIVED_FILE}")
    HTTPServer(("0.0.0.0", PORT), ManagerApiHandler).serve_forever()
