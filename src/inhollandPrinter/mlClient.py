"""
Serving saved images over HTTP so the ML API can fetch them, and asking
the ML API to check an image. The ML API container is now managed by
docker-compose rather than launched at runtime.
"""
import http.server
import json
import logging
import os
import threading
from urllib.parse import unquote

import requests

from inhollandPrinter.settings import settings

logger = logging.getLogger(__name__)


class _LatestHandler(http.server.SimpleHTTPRequestHandler):
    """Extends SimpleHTTPRequestHandler with /api/latest/ endpoints."""

    def _latest_image(self, printerName: str) -> str | None:
        baseDir = os.path.join(settings.snapshotDir, printerName)
        if not os.path.isdir(baseDir):
            return None
        candidates = []
        for root, _dirs, files in os.walk(baseDir):
            for f in files:
                if f.endswith(".jpg"):
                    candidates.append(os.path.join(root, f))
        if not candidates:
            return None
        return max(candidates, key=os.path.getmtime)

    def _all_latest(self) -> dict[str, str | None]:
        result = {}
        try:
            for entry in os.listdir(settings.snapshotDir):
                printerDir = os.path.join(settings.snapshotDir, entry)
                if os.path.isdir(printerDir):
                    latest = self._latest_image(entry)
                    if latest:
                        result[entry] = os.path.basename(latest)
                    else:
                        result[entry] = None
        except FileNotFoundError:
            pass
        return result

    def do_GET(self):
        path = self.path
        if path.startswith("/api/latest"):
            if path == "/api/latest" or path == "/api/latest/":
                data = self._all_latest()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data, indent=2).encode())
                return
            prefix = "/api/latest/"
            if path.startswith(prefix):
                printerName = unquote(path[len(prefix):])
                latest = self._latest_image(printerName)
                if latest:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.end_headers()
                    with open(latest, "rb") as f:
                        self.wfile.write(f.read())
                else:
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "No images found for this printer"}).encode())
                return
        super().do_GET()

    def log_message(self, format: str, *args) -> None:
        logger.debug("%s - - [%s] %s", self.address_string(), self.log_date_time_string(), format % args)


class ImageHttpServer:
    """Direct port of start_image_server()."""

    def __init__(
        self,
        imageDir=settings.imageDir,
        hostIp: str = settings.imageServerHostIp,
        port: int = settings.imageServerPort,
    ):
        self._imageDir = str(imageDir)
        self._hostIp = hostIp
        self._port = port
        self._server: http.server.HTTPServer | None = None

    def start(self) -> None:
        logger.info("Starting image server at http://%s:%s/", self._hostIp, self._port)
        from functools import partial

        handler = partial(_LatestHandler, directory=self._imageDir)
        self._server = http.server.HTTPServer((self._hostIp, self._port), handler)
        thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        thread.start()

    # TODO: stop()/shutdown() — the original never stops this once started.


class ObicoMLClient:
    """Direct port of check_spaghetti()."""

    def __init__(
        self,
        mlApiUrl: str = settings.mlApiUrl,
        publicHost: str = settings.imageServerPublicHost,
        port: int = settings.imageServerPort,
    ):
        self._mlApiUrl = mlApiUrl
        self._publicHost = publicHost
        self._port = port

    def checkForSpaghetti(self, filename: str) -> list:
        imageUrl = f"http://{self._publicHost}:{self._port}/{filename}"
        response = requests.get(self._mlApiUrl, params={"img": imageUrl}, timeout=settings.mlApiTimeout)
        response.raise_for_status()
        return response.json().get("detections", [])
