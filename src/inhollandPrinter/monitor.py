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

logger = logging.getLogger(__name__)


class PrinterMonitor:
    """Direct port of getImage(), updateDF(), and checkPicture()."""

    def __init__(self, printer_client, image_store, cycleTime: int = settings.pollCycleSeconds):
        self._printerClient = printer_client
        self._imageStore = image_store
        self._cycleTime = cycleTime

    def getImage(self, cam, index: int = 0):
        """Direct port of getImage(). Combines fetching bytes (printer_client)
        with saving them (image_store) — the original did both in one
        function via the global `client`."""
        if cam is None:
            return None
        logger.info(f"Taking image from {cam.name}")
        imageBytes = self._printerClient.getSnapshot(cam.id)
        return self._imageStore.saveSnapshot(cam.id, imageBytes, index=index)

    def updateDataFrame(self, df) -> None:
        """Direct port of updateDF()."""
        printers = self._printerClient.listPrinters()
        df["State"] = [printer.job.state if printer.job else "NONE" for printer in printers]
        df["TimeRemaining"] = [
            printer.job.time_remaining if printer.job else datetime.timedelta(0)
            for printer in printers
        ]

    def checkPictures(self, df, t: float, onImageReady) -> None:
        """
        Direct port of checkPicture(). `onImageReady(printer_name,
        printer_uuid, filename)` replaces the original's direct calls
        to `pending_checks.add(...)` / `spaghetti_queue.put(...)` —
        that bookkeeping now lives in DetectionWorker.enqueue below.
        """
        logger.info(f"Checking printers for images at {datetime.datetime.fromtimestamp(t)}")
        for idx, row in df.iterrows():
            cam = row["Cam"]
            if cam is None:
                logger.info(f"No camera attached to printer {row['Name']}, skipping")
                continue
            tRemaining = row["TimeRemaining"]
            if tRemaining >= datetime.timedelta(0) and t >= row["LastImage"] + self._cycleTime:
                filename = self.getImage(cam, index=row["index"])
                row["index"] += 1
                if row["index"] > 4:
                    row["index"] = 0
                logger.info(f"Image index: {row['index']}")
                logger.info(f"Saved image to {filename}")
                df.at[idx, "LastImage"] = t
                onImageReady(row["Name"], row["UUID"], filename)
            # elif t_remaining <= datetime.timedelta(0):
            #     logger.info(f"{row['Name']} has no active job, skipping")


class SpaghettiDetector:
    """Direct port of the check+overlay half of spaghetti_worker()."""

    def __init__(self, ml_client, image_store):
        self._mlClient = ml_client
        self._imageStore = image_store

    def evaluate(self, printerName: str, filename: str) -> list:
        logger.info(f"Checking {filename} for spaghetti ({printerName})")
        detections = self._mlClient.checkForSpaghetti(filename)
        if detections:
            logger.warning(f"Spaghetti detected on {printerName}! ({filename})")
            self._imageStore.saveAnnotated(filename, detections)
        else:
            logger.info(f"No spaghetti on {printerName} ({filename})")
        return detections

    # TODO: confidence thresholds / N-consecutive-detections logic, and
    # an actual call to pause the print. The original code — and this
    # port — only ever detects and logs/annotates. Nothing anywhere
    # stops a real print yet. That's the next real feature to build,
    # once printer_client.py has a pause_print() method to call.


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

    def enqueue(self, printerName: str, printerUuid: str, filename: str) -> None:
        """Direct port of the pending_checks/spaghetti_queue.put logic
        that lived inline inside checkPicture()."""
        if printerUuid in self._pendingChecks:
            logger.info(f"Spaghetti check already queued for {printerName}, skipping this round")
            return
        self._pendingChecks.add(printerUuid)
        self._queue.put((printerName, printerUuid, filename))

    def _run(self) -> None:
        """Direct port of spaghetti_worker()."""
        while True:
            printerName, printerUuid, filename = self._queue.get()
            try:
                self._detector.evaluate(printerName, filename)
            except Exception:
                logger.exception(f"Spaghetti check failed for {printerName} ({filename})")
            finally:
                self._pendingChecks.discard(printerUuid)
                self._queue.task_done()

    # TODO: stop()/join() — the original never stops this once started.
