"""
Notifies the external printer-manager API when this monitor has stopped a
print itself after consecutive spaghetti detections (AI auto-cancel).

Provisional contract until the manager API spec is finalized:

    POST {MANAGER_API_URL}
    {"printer": "<name>", "reason": "manual"|"auto",
     "image": "<base64 JPEG or null>", "image_name": "<filename or null>"}

Only reason="auto" is ever sent today; manual cancellations are not
reported by this monitor. Core One mode never notifies (wired in main.py).
"""
import base64
import logging
import os

import requests

from inhollandPrinter.settings import settings

logger = logging.getLogger(__name__)


class ManagerApiClient:

    def __init__(self, url: str | None = settings.managerApiUrl, timeout: int = settings.managerApiTimeout):
        self._url = url or None
        self._timeout = timeout

    def notifyCancelled(self, printerName: str, reason: str, imagePath: str | None) -> None:
        """POST a cancellation notice with the latest image attached.

        Raises on failure — callers must catch; a failed notification must
        never take down the polling loop or the detection worker.
        """
        if not self._url:
            logger.debug("MANAGER_API_URL not set, skipping cancellation notice")
            return

        imageB64 = None
        imageName = None
        if imagePath and os.path.isfile(imagePath):
            with open(imagePath, "rb") as f:
                imageB64 = base64.b64encode(f.read()).decode("ascii")
            imageName = os.path.basename(imagePath)

        payload = {
            "printer": printerName,
            "reason": reason,
            "image": imageB64,
            "image_name": imageName,
        }
        response = requests.post(self._url, json=payload, timeout=self._timeout)
        response.raise_for_status()
        logger.info(
            "Notified manager API of %s cancel on %s (%s)",
            reason, printerName, imageName or "no image",
        )
