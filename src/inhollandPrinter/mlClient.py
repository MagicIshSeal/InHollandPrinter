"""
Everything needed to run the spaghetti-detection ML pipeline: starting
the ML API's Docker container, serving saved images over HTTP so the
ML API can fetch them, and asking the ML API to check an image.

Three separate classes, kept in one file since they're all just
different pieces of "getting the ML detection call to work" — direct
ports of start_ml_api(), start_image_server(), and check_spaghetti()
from the original getFailure.py.
"""
import http.server
import platform
import subprocess
import threading

import requests

from inhollandPrinter.settings import settings

IS_WINDOWS = platform.system() == "Windows"


class MLApiDockerLifecycle:
    """Direct port of docker_cmd() + start_ml_api()."""

    def __init__(self, projectDir=settings.mlApiProjectDir):
        self._projectDir = str(projectDir)

    def _dockerCmd(self, *args: str) -> list[str]:
        base = ["docker", "compose"] if IS_WINDOWS else ["sudo", "docker", "compose"]
        return base + list(args)

    def start(self) -> None:
        result = subprocess.run(
            self._dockerCmd("ps", "ml_api"),
            cwd=self._projectDir,
            capture_output=True,
            text=True,
            check=False,
        )
        if "Up" in result.stdout:
            print("ml_api container is already running")
            return

        print("Starting ml_api container...")
        subprocess.run(self._dockerCmd("up", "-d", "ml_api"), cwd=self._projectDir, check=True)

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
        print(f"Starting image server at http://{self._hostIp}:{self._port}/")
        from functools import partial

        handler = partial(http.server.SimpleHTTPRequestHandler, directory=self._imageDir)
        self._server = http.server.HTTPServer((self._hostIp, self._port), handler)
        thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        thread.start()

    # TODO: stop()/shutdown() — the original never stops this once started.


class ObicoMLClient:
    """Direct port of check_spaghetti()."""

    def __init__(
        self,
        mlApiUrl: str = settings.mlApiUrl,
        hostIp: str = settings.imageServerHostIp,
        port: int = settings.imageServerPort,
    ):
        self._mlApiUrl = mlApiUrl
        self._hostIp = hostIp
        self._port = port

    def checkForSpaghetti(self, filename: str) -> list:
        imageUrl = f"http://{self._hostIp}:{self._port}/{filename}"
        response = requests.get(self._mlApiUrl, params={"img": imageUrl}, timeout=10)
        response.raise_for_status()
        return response.json().get("detections", [])
