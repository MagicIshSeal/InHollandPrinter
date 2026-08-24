"""
Saves raw snapshots and annotated (spaghetti-boxed) images to disk.

save_snapshot() is a direct port of the file-writing half of getImage()
from handlePrinter.py — fetching the actual bytes now happens in
printer_client.py's get_snapshot(); monitor.py combines the two calls
back together, same as getImage() did originally.

save_annotated() is a direct port of overlay_detections() from
getFailure.py, including its use of cv2, its hardcoded
confidence_threshold default, and its hardcoded "output.jpg" filename.
"""
import os

import cv2

from inhollandPrinter.settings import settings


class LocalImageStore:
    def __init__(self, snapshotDir=settings.snapshotDir):
        self._snapshotDir = str(snapshotDir)

    def saveSnapshot(self, printerName: str, imageBytes: bytes, index: int = 0) -> str:
        camDir = os.path.join(self._snapshotDir, str(printerName))
        os.makedirs(camDir, exist_ok=True)

        if index == 0:
            name = f"snapshot{printerName}.jpg"
        else:
            name = f"snapshot{printerName}_{index}.jpg"

        filepath = os.path.join(camDir, name)
        with open(filepath, "wb") as f:
            f.write(imageBytes)
        return filepath

    def saveAnnotated(self, printerName: str, filename: str, detections: list, confidenceThreshold: float | None = None) -> str:
        if confidenceThreshold is None:
            confidenceThreshold = settings.confidenceThreshold
        img = cv2.imread(filename)
        if img is None:
            raise FileNotFoundError(f"Unable to read image for annotation: {filename}")
        for label, confidence, (cx, cy, w, h) in detections:
            if confidence < confidenceThreshold:
                continue
            x1 = int(cx - w / 2)
            y1 = int(cy - h / 2)
            x2 = int(cx + w / 2)
            y2 = int(cy + h / 2)
            color = (0, int(255 * (1 - confidence)), int(255 * confidence))
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                img, f"{confidence:.0%}", (x1, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2,
            )
        outDir = os.path.join(self._snapshotDir, str(printerName), "annotated")
        os.makedirs(outDir, exist_ok=True)
        base = os.path.splitext(os.path.basename(filename))[0]
        output = os.path.join(outDir, f"{base}_annotated.jpg")
        cv2.imwrite(output, img)
        return output

    def getLatestImagePath(self, printerName: str) -> str | None:
        """Newest annotated image for the printer, falling back to the
        newest raw snapshot (same mtime approach as mlClient's latest-image
        endpoints). Used for cancellation notifications."""
        baseDir = os.path.join(self._snapshotDir, str(printerName))
        if not os.path.isdir(baseDir):
            return None
        annotated, raw = [], []
        for root, _dirs, files in os.walk(baseDir):
            isAnnotated = os.path.basename(root) == "annotated"
            for f in files:
                if f.endswith(".jpg"):
                    (annotated if isAnnotated else raw).append(os.path.join(root, f))
        pool = annotated or raw
        if not pool:
            return None
        return max(pool, key=os.path.getmtime)
