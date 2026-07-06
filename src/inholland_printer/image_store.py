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

from inholland_printer.settings import settings


class LocalImageStore:
    def __init__(self, snapshot_dir=settings.snapshot_dir):
        self._snapshot_dir = str(snapshot_dir)

    def save_snapshot(self, camera_id: str, image_bytes: bytes, index: int = 0) -> str:
        cam_dir = os.path.join(self._snapshot_dir, str(camera_id))
        os.makedirs(cam_dir, exist_ok=True)

        if index == 0:
            name = f"snapshot{camera_id}.jpg"
        else:
            name = f"snapshot{camera_id}_{index}.jpg"

        filepath = os.path.join(cam_dir, name)
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        return filepath

    def save_annotated(self, filename: str, detections: list, confidence_threshold: float = 0.3) -> str:
        img = cv2.imread(filename)
        for label, confidence, (cx, cy, w, h) in detections:
            if confidence < confidence_threshold:
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
        output = "output.jpg"
        cv2.imwrite(output, img)
        return output

    # NOTE found while porting: `label` is unpacked but never used, and
    # `output` is always the literal "output.jpg" — every annotated
    # image overwrites the previous one. Kept as-is to match current
    # behavior; worth fixing once you touch this again.
