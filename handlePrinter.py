import time
import datetime
import queue
import threading
from prusa.connect.client import PrusaConnectClient
import pandas as pd
import logging
import structlog
from getFailure import start_ml_api, start_image_server, check_spaghetti, overlay_detections
import os

IMG_DIR = "img"

class ColorFormatter(logging.Formatter):
    BLUE = "\033[34m"
    RESET = "\033[0m"
    def format(self, record):
        levelname = record.levelname
        if record.levelno == logging.INFO:
            record.levelname = f"{self.BLUE}{levelname}{self.RESET}"
        formatted = super().format(record)
        record.levelname = levelname
        return formatted

handler = logging.StreamHandler()
handler.setFormatter(ColorFormatter(
    fmt="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR),
)

# --- Spaghetti detection queue ---
spaghetti_queue = queue.Queue()
pending_checks = set()  # printer UUIDs currently queued or being processed

def spaghetti_worker():
    while True:
        printer_name, printer_uuid, filename = spaghetti_queue.get()
        try:
            logger.info(f"Checking {filename} for spaghetti ({printer_name})")
            detections = check_spaghetti(filename)
            if detections:
                logger.warning(f"Spaghetti detected on {printer_name}! ({filename})")
                overlay_detections(filename, detections)
            else:
                logger.info(f"No spaghetti on {printer_name} ({filename})")
        except Exception:
            logger.exception(f"Spaghetti check failed for {printer_name} ({filename})")
        finally:
            pending_checks.discard(printer_uuid)
            spaghetti_queue.task_done()

threading.Thread(target=spaghetti_worker, daemon=True, name="spaghetti-worker").start()


def getImage(cam, i=0):
    if cam is None:
        return None
    logger.info(f"Taking image from {cam.name}")
    image_data = client.get_snapshot(cam.id)

    cam_dir = os.path.join(IMG_DIR, str(cam.id))
    os.makedirs(cam_dir, exist_ok=True)

    if i == 0:
        name = f"snapshot{cam.id}.jpg"
    else:
        name = f"snapshot{cam.id}_{i}.jpg"

    filepath = os.path.join(cam_dir, name)
    with open(filepath, "wb") as f:
        f.write(image_data)
    return filepath

def updateDF(df, client):
    printers = client.printers.list_printers()
    df["State"] = [printer.job.state if printer.job else "NONE" for printer in printers]
    df["TimeRemaining"] = [printer.job.time_remaining if printer.job else datetime.timedelta(0) for printer in printers]

def startSpaghetti():
    start_ml_api()
    logger.info("Spaghetti Detector API started")
    time.sleep(2.5)
    start_image_server()
    logger.info("Image server started")

def checkPicture(df, t, i=0):
    logger.info(f"Checking printers for images at {datetime.datetime.fromtimestamp(t)}")
    for idx, row in df.iterrows():
        cam = row["Cam"]
        if cam is None:
            logger.info(f"No camera attached to printer {row['Name']}, skipping")
            continue
        t_remaining = row["TimeRemaining"]
        if t_remaining >= datetime.timedelta(0) and t >= row["LastImage"] + cycleTime:
            filename = getImage(cam, i)
            logger.info(f"Saved image to {filename}")
            df.at[idx, "LastImage"] = t

            printer_uuid = row["UUID"]
            if printer_uuid in pending_checks:
                logger.info(f"Spaghetti check already queued for {row['Name']}, skipping this round")
            else:
                pending_checks.add(printer_uuid)
                spaghetti_queue.put((row["Name"], printer_uuid, filename))
        # elif t_remaining <= datetime.timedelta(0):
        #     logger.info(f"{row['Name']} has no active job, skipping")


client = PrusaConnectClient()
printers = client.printers.list_printers()
cameras = client.cameras.list()
cameras_by_printer_uuid = {cam.printer_uuid: cam for cam in cameras if cam.printer_uuid}
matched_cams = [cameras_by_printer_uuid.get(printer.uuid) for printer in printers]
cycleTime = 15

n = len(printers)
printFrame = pd.DataFrame({
    "Name":         [printer.name for printer in printers],
    "UUID":         [printer.uuid for printer in printers],
    "State":        [printer.job.state if printer.job else "NONE" for printer in printers],
    "TimeRemaining":[printer.job.time_remaining if printer.job else datetime.timedelta(0) for printer in printers],
    "Cam":          matched_cams,
    "CamUUID":      [cam.id if cam else None for cam in matched_cams],
    "CamName":      [cam.name if cam else None for cam in matched_cams],
    "LastImage":    [cycleTime / n * (i) for i in range(n)],
})
printFrame.drop(columns=["Cam"]).to_csv("printer_info.csv", index=False)
logger.info(printFrame.head())

while True:
    updateDF(printFrame, client)
    checkPicture(printFrame, time.time())
    time.sleep(5)
