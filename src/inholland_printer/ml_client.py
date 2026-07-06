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
import os
import platform
import subprocess
import threading

import requests

from inholland_printer.settings import settings

IS_WINDOWS = platform.system() == "Windows"


class MLApiDockerLifecycle:
    """Direct port of docker_cmd() + start_ml_api()."""

    def __init__(self, project_dir=settings.ml_api_project_dir):
        self._project_dir = str(project_dir)

    def _docker_cmd(self, *args: str) -> list[str]:
        base = ["docker", "compose"] if IS_WINDOWS else ["sudo", "docker", "compose"]
        return base + list(args)

    def start(self) -> None:
        result = subprocess.run(
            self._docker_cmd("ps", "ml_api"),
            cwd=self._project_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if "Up" in result.stdout:
            print("ml_api container is already running")
            return

        print("Starting ml_api container...")
        subprocess.run(self._docker_cmd("up", "-d", "ml_api"), cwd=self._project_dir, check=True)

class ImageHttpServer:
    """Direct port of start_image_server()."""

    def __init__(
        self,
        image_dir=settings.image_dir,
        host_ip: str = settings.image_server_host_ip,
        port: int = settings.image_server_port,
    ):
        self._image_dir = str(image_dir)
        self._host_ip = host_ip
        self._port = port
        self._server: http.server.HTTPServer | None = None

    def start(self) -> None:
        print(f"Starting image server at http://{self._host_ip}:{self._port}/")
        from functools import partial

        handler = partial(http.server.SimpleHTTPRequestHandler, directory=self._image_dir)
        self._server = http.server.HTTPServer((self._host_ip, self._port), handler)
        thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        thread.start()

    # TODO: stop()/shutdown() — the original never stops this once started.


class ObicoMLClient:
    """Direct port of check_spaghetti()."""

    def __init__(
        self,
        ml_api_url: str = settings.ml_api_url,
        host_ip: str = settings.image_server_host_ip,
        port: int = settings.image_server_port,
    ):
        self._ml_api_url = ml_api_url
        self._host_ip = host_ip
        self._port = port

    def check_for_spaghetti(self, filename: str) -> list:
        image_url = f"http://{self._host_ip}:{self._port}/{filename}"
        response = requests.get(self._ml_api_url, params={"img": image_url})
        return response.json().get("detections", [])
