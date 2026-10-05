"""
Notifies the external printer-manager API when this monitor has stopped a
print itself after consecutive spaghetti detections (AI auto-cancel).

Implements the manager's `POST /webhook/spaghetti-detected` contract:

    Auth:    X-Api-Key header (shared secret)
    Request: multipart/form-data
               printer_name: str|null
               ip:           str|null
               cancelled_at: str        ISO-8601 (always sent)
               progress:     str|null   0-100
               image:        file|null
    Response: 202 fresh record, 204 idempotent re-POST,
              400 invalid input, 401 bad key, 404 unknown printer/run

Manual cancellations and finished prints are never reported by this
monitor, and Core One mode never notifies (wired in main.py).
"""
import datetime
import logging
import os

import requests

from inhollandPrinter.settings import settings

logger = logging.getLogger(__name__)


class ManagerApiClient:

    def __init__(
        self,
        url: str | None = settings.managerApiUrl,
        apiKey: str | None = settings.managerApiKey,
        timeout: int = settings.managerApiTimeout,
    ):
        self._url = url or None
        self._apiKey = apiKey or None
        self._timeout = timeout

    def notifyCancelled(
        self,
        printerName: str,
        ip: str | None,
        progress: str | int | None,
        imagePath: str | None,
    ) -> None:
        """POST a multipart auto-cancel notice with the latest image.

        Raises on failure — callers must catch; a failed notification must
        never take down the polling loop or the detection worker.
        """
        if not self._url:
            logger.debug("MANAGER_API_URL not set, skipping cancellation notice")
            return
        if not self._apiKey:
            logger.warning("MANAGER_API_URL set but MANAGER_API_KEY missing, skipping cancellation notice")
            return

        data = {
            "printer_name": printerName,
            "ip": ip,
            "cancelled_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        if progress is not None:
            data["progress"] = str(progress)

        files = None
        imageName = None
        if imagePath and os.path.isfile(imagePath):
            imageName = os.path.basename(imagePath)
            with open(imagePath, "rb") as f:
                files = {"image": (imageName, f.read(), "image/jpeg")}
        else:
            logger.warning("No image on disk for %s, notifying manager API without one", printerName)

        response = requests.post(
            self._url,
            data=data,
            files=files,
            headers={"X-Api-Key": self._apiKey},
            timeout=self._timeout,
        )
        response.raise_for_status()
        logger.info(
            "Notified manager API of auto cancel on %s (HTTP %s, %s)",
            printerName, response.status_code, imageName or "no image",
        )
