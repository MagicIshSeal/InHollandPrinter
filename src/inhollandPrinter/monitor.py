"""
The core loop logic: check each printer for a new image, and run
spaghetti detection on any image that comes in — without blocking the
main polling loop while a detection check is in progress.

Three classes, kept in one file since debugging "why didn't this
printer get checked" always means looking at all three together anyway:

  - PrinterMonitor:    direct port of getImage(), updateDF(), checkPicture()
  - SpaghettiDetector: direct port of the check+overlay half of spaghetti_worker()
  - DetectionWorker:   direct port of the queue/thread half of spaghetti_worker(),
                       plus the module-level spaghetti_queue/pending_checks globals
"""
import datetime
import logging
import queue
import threading

from inhollandPrinter.settings import settings
from inhollandPrinter.config import *
from inhollandPrinter.auth import login
import prusa.connect.client.exceptions as prusa_exceptions


logger = logging.getLogger(__name__)

class PrinterMonitor:
    """Direct port of getImage(), updateDF(), and checkPicture()."""

    def __init__(self, printer_client, image_store, detector, cycleTime: int = settings.pollCycleSeconds):
        self._printerClient = printer_client
        self._imageStore = image_store
        self._detector = detector
        self._cycleTime = cycleTime

    def getImage(self, printerName: str, index: int = 0):
        """Direct port of getImage(). Combines fetching bytes (printer_client)
        with saving them (image_store) — the original did both in one
        function via the global `client`."""
        logger.info(f"Taking image for {printerName}")
        imageBytes = self._printerClient.getSnapshot(printerName)
        return self._imageStore.saveSnapshot(printerName, imageBytes, index=index)

    def updatePrinterStatus(self) -> None:
            for printerName in printers.keys():
                try:
                    client = login(printers.login_address(printerName), printers.get_password(printerName))
                    response = client.api_request("GET", "/api/v1/status")
    
                    printer_state = response.get("printer", {})
                    job_state = response.get("job", {})
    
                    dict.__getitem__(printers, printerName).update(
                        {
                            "status": printer_state.get("state", "UNKNOWN"),
                            "temp_nozzle": printer_state.get("temp_nozzle"),
                            "temp_bed": printer_state.get("temp_bed"),
                            "time_remaining": job_state.get("time_remaining"),
                            "job_id": job_state.get("id"),
                        }
                    )
    
                    # print(
                    #     f"{printerName}: {printers.get_status(printerName)}, "
                    #     f"bed={printers.get_bed_temp(printerName)}, "
                    #     f"nozzle={printers.get_nozzle_temp(printerName)}, "
                    #     f"remaining={printers.get_time_remaining(printerName)}, "
                    #     f"job={printers.get_job_id(printerName)}"
                    # )
                except prusa_exceptions.PrusaApiError:
                    dict.__getitem__(printers, printerName).update(
                        {
                            "status": "DISCONNECTED",
                            "temp_nozzle": None,
                            "temp_bed": None,
                            "time_remaining": None,
                            "job_id": None,
                        }
                    )
                    logger.warning(f"{printerName}: DISCONNECTED")    

    def checkPictures(self, t: datetime.datetime, onImageReady) -> None:
        logger.debug(f"Checking printers for images at {t}")
        for printerName in printers.keys():
            tRemaining = printers.get_time_remaining(printerName)
            if isinstance(tRemaining, (int, float)):
                tRemaining = datetime.timedelta(seconds=tRemaining)
            hasActiveJob = (
                tRemaining is not None and tRemaining >= datetime.timedelta(0)
            )
            if hasActiveJob and (
                printers.get_last_image(printerName) is None
                or t >= printers.get_last_image(printerName) + datetime.timedelta(seconds=self._cycleTime)
            ):
                filename = self.getImage(printerName, index=printers.get_index(printerName))
                printers.set_index(printerName, printers.get_index(printerName) + 1)
                
                if printers.get_index(printerName) > 4:
                    printers.set_index(printerName, 0)
                    
                logger.debug(f"Image index: {printers.get_index(printerName)}")
                logger.debug(f"Saved image to {filename}")
                
                printers.set_last_image(printerName, t)
                
                onImageReady(printerName, filename)
            elif not hasActiveJob:
                 logger.debug(f"{printerName} has no active job, skipping")
                 self._detector.reset(printerName)


class SpaghettiDetector:
    def __init__(self, ml_client, image_store, printer_client):
        self._mlClient = ml_client
        self._imageStore = image_store
        self._printerClient = printer_client
        self._failureCounts: dict[str, int] = {}

    def evaluate(self, printerName: str, filename: str) -> list:
        logger.info(f"Checking {filename} for spaghetti ({printerName})")
        detections = self._mlClient.checkForSpaghetti(filename)
        threshold = settings.confidenceThreshold
        filtered = [d for d in detections if d[1] >= threshold]
        if filtered:
            count = self._failureCounts.get(printerName, 0) + 1
            self._failureCounts[printerName] = count
            confs = ", ".join(f"{d[1]:.0%}" for d in filtered)
            logger.warning(f"Spaghetti detected on {printerName}! (consecutive failure {count}, confidence {confs}) ({filename})")
            self._imageStore.saveAnnotated(printerName, filename, detections, threshold)
            if count >= settings.consecutiveFailureLimit:
                logger.warning(f"Stopping print on {printerName} after {count} consecutive failures")
                try:
                    self._printerClient.stopPrint(printerName)
                except Exception:
                    logger.exception(f"Failed to stop print on {printerName}")
        elif detections:
            confs = ", ".join(f"{d[1]:.0%}" for d in detections)
            logger.info(f"Spaghetti detected on {printerName} but below {threshold:.0%} confidence ({confs}) ({filename})")
            self._failureCounts[printerName] = 0
        else:
            logger.info(f"No spaghetti on {printerName} ({filename})")
            self._failureCounts[printerName] = 0
        return filtered

    def reset(self, printerName: str) -> None:
        """Reset the consecutive-failure counter (e.g. when a job ends)."""
        if self._failureCounts.pop(printerName, None) is not None:
            logger.info(f"Reset spaghetti failure count for {printerName}")


class DetectionWorker:
    """Direct port of the queue/threading portion of handlePrinter.py:
    spaghetti_queue, pending_checks, spaghetti_worker(), and the
    threading.Thread(...).start() call that used to run at import time."""

    def __init__(self, detector: SpaghettiDetector):
        self._detector = detector
        self._queue: "queue.Queue" = queue.Queue()
        self._pendingChecks: set = set()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="spaghetti-worker")
        self._thread.start()

    def enqueue(self, printerName: str, filename: str) -> None:
        if printerName in self._pendingChecks:
            logger.debug(f"Spaghetti check already queued for {printerName}, skipping this round")
            return
        self._pendingChecks.add(printerName)
        self._queue.put((printerName, filename))

    def _run(self) -> None:
        while True:
            printerName, filename = self._queue.get()
            try:
                self._detector.evaluate(printerName, filename)
            except Exception:
                logger.exception(f"Spaghetti check failed for {printerName} ({filename})")
            finally:
                self._pendingChecks.discard(printerName)
                self._queue.task_done()

    # TODO: stop()/join() — the original never stops this once started.
