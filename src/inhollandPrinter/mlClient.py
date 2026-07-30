"""
Serving saved images over HTTP so the ML API can fetch them, and asking
the ML API to check an image. The ML API container is now managed by
docker-compose rather than launched at runtime.
"""
import http.server
import logging
import threading

import requests

from inhollandPrinter.settings import settings

logger = logging.getLogger(__name__)


class ImageHttpServer:
    """Direct port of start_image_server()."""

    class _LoggedRequestHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            logger.info("%s - - [%s] %s", self.address_string(), self.log_date_time_string(), format % args)

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
        print(f"Starting image server at http://{self._hostIp}:{self._port}/")
        from functools import partial

        handler = partial(self._LoggedRequestHandler, directory=self._imageDir)
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
        response = requests.get(self._mlApiUrl, params={"img": imageUrl}, timeout=10)
        response.raise_for_status()
        return response.json().get("detections", [])
