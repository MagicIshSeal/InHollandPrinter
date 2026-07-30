# Image Server API

The image server runs on port **8080** and serves three categories of endpoints: static files (raw snapshots for ML consumption), the latest-image API, and the ML detection endpoint.

## Static File Serving

Serves any file under the snapshot directory (`img/` by default).

```
GET /<path>
```

Used internally by the ML API to fetch raw snapshots for detection.

---

## Latest-Image API

Returns the most recent `.jpg` file (raw or annotated) for one or all printers, ordered by filesystem modification time.

### List latest per printer

```
GET /api/latest
```

**Response 200** — `application/json`

```json
{
  "PETG Printer": "snapshotPETG Printer.jpg",
  "Mock Printer": "snapshotMock Printer_1_annotated.jpg",
  "Printer 3": "snapshotPrinter 3_2.jpg"
}
```

Printers with no images are omitted from the object.

### Get latest for one printer

```
GET /api/latest/<PrinterName>
```

`<PrinterName>` must be URL-encoded (e.g. `Mock%20Printer` for "Mock Printer").

**Response 200** — `image/jpeg`

Binary JPEG data of the newest image for that printer.

**Response 404** — `application/json`

```json
{"error": "No images found for this printer"}
```

Returned when the printer directory does not exist or contains no `.jpg` files.

---

## ML Detection Endpoint

```
GET /?img=<url>
```

Used by the internal `ObicoMLClient` to submit an image for spaghetti detection. `<url>` is a fully qualified URL pointing back to the image server's static file serving (e.g. `http://printer-monitor:8080/img/Mock%20Printer/snapshot.jpg`).

**Response 200** — `application/json`

```json
{
  "detections": [
    ["spaghetti", 0.87, [320, 240, 100, 80]],
    ...
  ]
}
```

Each detection: `[label, confidence, [cx, cy, width, height]]`.

**Response non-2xx** — errors are caught and logged by the detection worker; no retry is attempted.
