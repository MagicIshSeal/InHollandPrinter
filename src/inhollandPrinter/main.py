"""
The composition root — the only place that creates the "real" classes
and wires them together. Running this reproduces exactly what
`python handlePrinter.py` used to do: start the ML API container,
start the image server, build the printer/camera table, dump it to
printer_info.csv, then poll forever.
"""
import datetime
import logging
import time

import structlog

from inhollandPrinter.imageStore import LocalImageStore
from inhollandPrinter.mlClient import ImageHttpServer, ObicoMLClient
from inhollandPrinter.monitor import DetectionWorker, PrinterMonitor, SpaghettiDetector
from inhollandPrinter.printerClient import PrinterClient
from inhollandPrinter.settings import settings


class ColorFormatter(logging.Formatter):
    """Direct port of ColorFormatter from handlePrinter.py."""
    BLUE = "\033[34m"
    RESET = "\033[0m"

    def format(self, record):
        levelname = record.levelname
        if record.levelno == logging.INFO:
            record.levelname = f"{self.BLUE}{levelname}{self.RESET}"
        elif record.levelno == logging.WARNING:
            record.levelname = f"\033[33m{levelname}{self.RESET}"
        elif record.levelno == logging.ERROR:
            record.levelname = f"\033[31m{levelname}{self.RESET}"
        formatted = super().format(record)
        record.levelname = levelname
        return formatted


def configureLogging() -> logging.Logger:
    """Direct port of the module-level logging setup in handlePrinter.py."""
    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logging.basicConfig(level=getattr(logging, settings.logLevel.upper(), logging.INFO), handlers=[handler])

    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR),
    )
    return logging.getLogger(__name__)


def main() -> None:
    logger = configureLogging()

    # --- the "real" implementations, created once, here ---
    printer_client = PrinterClient()
    ml_client = ObicoMLClient()
    image_store = LocalImageStore()
    image_server = ImageHttpServer()

    # --- wiring ---
    detector = SpaghettiDetector(ml_client, image_store, printer_client)
    worker = DetectionWorker(detector)
    worker.start()
    monitor = PrinterMonitor(printer_client, image_store, detector)

    # --- startup sequence ---
    image_server.start()
    logger.info("Image server started")

    # --- main loop: direct port of the trailing `while True` ---
    while True:
        monitor.updatePrinterStatus()
        monitor.checkPictures(datetime.datetime.now(), onImageReady=worker.enqueue)
        time.sleep(settings.mainLoopSleepSeconds)


if __name__ == "__main__":
    main()
