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

import pandas as pd
import structlog

from inholland_printer.image_store import LocalImageStore
from inholland_printer.ml_client import ImageHttpServer, MLApiDockerLifecycle, ObicoMLClient
from inholland_printer.monitor import DetectionWorker, PrinterMonitor, SpaghettiDetector
from inholland_printer.printer_client import PrinterClient
from inholland_printer.settings import settings


class ColorFormatter(logging.Formatter):
    """Direct port of ColorFormatter from handlePrinter.py."""
    BLUE = "\033[34m"
    RESET = "\033[0m"

    def format(self, record):
        levelname = record.levelname
        if record.levelno == logging.INFO:
            record.levelname = f"{self.BLUE}{levelname}{self.RESET}"
        formatted = super().format(record)
        record.levelname = levelname
        return formatted


def configure_logging() -> logging.Logger:
    """Direct port of the module-level logging setup in handlePrinter.py."""
    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logging.basicConfig(level=logging.INFO, handlers=[handler])

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR),
    )
    return logging.getLogger(__name__)


def build_printer_dataframe(printer_client) -> pd.DataFrame:
    """Direct port of the module-level DataFrame construction in handlePrinter.py."""
    printers = printer_client.list_printers()
    cameras = printer_client.list_cameras()
    cameras_by_printer_uuid = {cam.printer_uuid: cam for cam in cameras if cam.printer_uuid}
    matched_cams = [cameras_by_printer_uuid.get(printer.uuid) for printer in printers]

    n = len(printers)
    cycle_time = settings.poll_cycle_seconds
    if n == 0:
        return pd.DataFrame({
            "Name": [],
            "UUID": [],
            "State": [],
            "TimeRemaining": [],
            "Cam": [],
            "CamUUID": [],
            "CamName": [],
            "LastImage": [],
        })
    return pd.DataFrame({
        "Name":          [printer.name for printer in printers],
        "UUID":          [printer.uuid for printer in printers],
        "State":         [printer.job.state if printer.job else "NONE" for printer in printers],
        "TimeRemaining": [
            printer.job.time_remaining if printer.job else datetime.timedelta(0)
            for printer in printers
        ],
        "Cam":           matched_cams,
        "CamUUID":       [cam.id if cam else None for cam in matched_cams],
        "CamName":       [cam.name if cam else None for cam in matched_cams],
        "LastImage":     [cycle_time / n * i for i in range(n)],
    })


def main() -> None:
    logger = configure_logging()

    # --- the "real" implementations, created once, here ---
    printer_client = PrinterClient()
    ml_client = ObicoMLClient()
    image_store = LocalImageStore()
    image_server = ImageHttpServer()
    ml_api_lifecycle = MLApiDockerLifecycle()

    # --- wiring ---
    detector = SpaghettiDetector(ml_client, image_store)
    worker = DetectionWorker(detector)
    worker.start()
    monitor = PrinterMonitor(printer_client, image_store)

    # --- startup sequence: direct port of startSpaghetti() ---
    ml_api_lifecycle.start()
    logger.info("Spaghetti Detector API started")
    time.sleep(2.5)
    image_server.start()
    logger.info("Image server started")

    # --- initial printer/camera table: direct port of module-level setup ---
    print_frame = build_printer_dataframe(printer_client)
    print_frame.drop(columns=["Cam"]).to_csv("printer_info.csv", index=False)
    logger.info(print_frame.head())

    # --- main loop: direct port of the trailing `while True` ---
    while True:
        monitor.update_dataframe(print_frame)
        monitor.check_pictures(print_frame, time.time(), index=0, on_image_ready=worker.enqueue)
        time.sleep(settings.main_loop_sleep_seconds)


if __name__ == "__main__":
    main()
