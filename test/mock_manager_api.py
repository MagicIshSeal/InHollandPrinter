"""
Mock printer-manager API for the Docker test stack.

Implements the `POST /webhook/spaghetti-detected` contract:
  - X-Api-Key header is required (env MANAGER_API_KEY, default test-secret-key)
  - multipart/form-data with printer_name, ip, cancelled_at, progress, image
  - 202 fresh record, 204 idempotent re-POST, 400 invalid, 401 bad key, 404 wrong path

Each accepted record is appended as a JSON line to a shared volume file
that test/test_api.py asserts against (the image bytes themselves are
summarised by name/size, not stored).
"""
import json
import os
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, HTTPServer

RECEIVED_FILE = os.environ.get("MANAGER_RECEIVED_FILE", "/data/manager_received.jsonl")
PORT = int(os.environ.get("MANAGER_API_PORT", "9990"))
API_KEY = os.environ.get("MANAGER_API_KEY", "test-secret-key")
PATH = "/webhook/spaghetti-detected"

_seen = set()


class ManagerApiHandler(BaseHTTPRequestHandler):

    def _respond(self, status, body=None):
        self.send_response(status)
        if body is not None:
            self.send_header("Content-Type", "application/json")
        self.end_headers()
        if body is not None:
            self.wfile.write(json.dumps(body).encode())

    def do_POST(self):
        if self.path != PATH:
            self._respond(404, {"error": f"unknown path {self.path}"})
            return
        if self.headers.get("X-Api-Key") != API_KEY:
            self._respond(401, {"error": "bad or missing X-Api-Key"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            message = BytesParser(policy=email_policy).parsebytes(
                b"Content-Type: " + self.headers.get("Content-Type", "").encode() + b"\r\n\r\n" + raw
            )
            fields, imageName, imageSize = {}, None, 0
            for part in message.iter_parts():
                name = part.get_param("name", header="content-disposition")
                payload = part.get_payload(decode=True) or b""
                if part.get_filename():
                    if name == "image":
                        imageName = part.get_filename()
                        imageSize = len(payload)
                        if payload[:2] != b"\xff\xd8":
                            raise ValueError("image field is not a JPEG")
                else:
                    fields[name] = payload.decode()

            if not fields.get("cancelled_at"):
                raise ValueError("cancelled_at is required")
        except Exception as e:
            print(f"[manager-api] rejected POST: {e}")
            self._respond(400, {"error": str(e)})
            return

        record = {
            "printer_name": fields.get("printer_name"),
            "ip": fields.get("ip"),
            "cancelled_at": fields.get("cancelled_at"),
            "progress": fields.get("progress"),
            "image_name": imageName,
            "image_size": imageSize,
        }
        key = (record["printer_name"], record["cancelled_at"])
        os.makedirs(os.path.dirname(RECEIVED_FILE), exist_ok=True)
        with open(RECEIVED_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")

        if key in _seen:
            print(f"[manager-api] idempotent re-POST for {record['printer_name']!r} -> 204")
            self._respond(204)
            return
        _seen.add(key)
        print(f"[manager-api] recorded AUTO_CANCELLED for {record['printer_name']!r} "
              f"(progress={record['progress']!r}, image={imageName!r}) -> 202")
        self._respond(202)

    def log_message(self, fmt, *args):
        print(f"[manager-api] {args[0]} {args[1]} {args[2]}")


if __name__ == "__main__":
    print(f"[manager-api] listening on :{PORT}, path {PATH}, recording to {RECEIVED_FILE}")
    HTTPServer(("0.0.0.0", PORT), ManagerApiHandler).serve_forever()
