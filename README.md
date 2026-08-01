# InHollandPrinter — Spaghetti Detection for 3D Printers

Monitors PrusaLink-connected printers, captures snapshots during active prints, and runs them through a YOLO-based ML model to detect spaghetti failures.

## Prerequisites

- Docker & Docker Compose v2

## Quick Start

```bash
# 1. Clone
git clone <repo-url>
cd InHollandPrinter

# 2. Configure credentials
cp .env.example .env
# Edit .env with your PrusaLink credentials

# 3. Start production
docker compose up --build
```

View images while running (separate terminal):
```bash
xdg-open img/<PrinterName>/          # raw snapshots + annotated images (use your printer name)
```

## Test (with mock printer)

Uses a mock printer (Digest Auth, hardcoded `test_img/fail.jpg` snapshot) so you don't need real hardware.

```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml down -v
docker compose -f docker-compose.yml -f docker-compose.test.yml build printer-monitor
docker compose -f docker-compose.yml -f docker-compose.test.yml up --abort-on-container-exit
```

The ML API healthcheck + model load takes ~30s, then the monitor starts polling.

Output locations (on host):
- Raw snapshots: `./img/<PrinterName>/snapshot<PrinterName>_<index>.jpg`
- Annotated images: `./img/<PrinterName>/annotated/snapshot<PrinterName>_<index>_annotated.jpg`

View images while the test runs (separate terminal):
```bash
xdg-open img/Mock\ Printer/        # raw snapshots + annotated images
```

The image server also exposes a latest-image API on port 8080:

```bash
# List latest annotated image per printer
curl http://localhost:8080/api/latest

# Get the latest annotated image for a specific printer
curl -o latest.jpg http://localhost:8080/api/latest/Mock%20Printer
xdg-open latest.jpg
```

## Configuration

All via environment variables (or `.env` file):

| Variable | Default | Description |
|---|---|---|---|
| `LOCAL_USERNAME` | — | PrusaLink username |
| `LOCAL_PASSWORD` | — | PrusaLink password |
| `ML_API_URL` | `http://ml_api:3333/p/` | ML detection endpoint |
| `IMAGE_SERVER_PUBLIC_HOST` | `printer-monitor` | Hostname ML API uses to fetch snapshots |
| `SNAPSHOT_DIR` | `img/` | Directory for raw snapshots & annotated images |
| `POLL_CYCLE_SECONDS` | `15` | Min seconds between snapshots of the same printer |
| `MAIN_LOOP_SLEEP_SECONDS` | `5` | Sleep between main loop iterations |
| `CONFIDENCE_THRESHOLD` | `0.3` | Minimum ML confidence to report/annotate spaghetti |
| `CONSECUTIVE_FAILURE_LIMIT` | `3` | Consecutive spaghetti detections before stopping the print |
| `ML_API_TIMEOUT` | `30` | Seconds to wait for ML API response before timing out |

## Printers

Edit `src/inhollandPrinter/printers.json`:

```json
{
  "My Printer": {"public_ip": "192.168.0.1", "local_ip": "192.168.0.1", "id": "1"},
  "Second Printer": {"copy_from": "My Printer", "id": "2"}
}
```

## Project Structure

```
InHollandPrinter/
├── Dockerfile
├── docker-compose.yml          # Production (printer-monitor + ml_api)
├── docker-compose.test.yml     # Test override (adds mock-printer)
├── test/
│   ├── mock_printer.py         # Digest-auth mock printer
│   └── printers.test.json      # Test printer config
├── test_img/
│   └── fail.jpg                # Known spaghetti image
├── img/                        # Output: raw snapshots + annotated/ subfolders
├── src/inhollandPrinter/
│   ├── main.py                 # Entry point
│   ├── monitor.py              # Polling loop + spaghetti detection pipeline
│   ├── settings.py             # pydantic-settings config
│   ├── printerClient.py        # PrusaLink HTTP client
│   ├── imageStore.py           # Save raw & annotated images
│   └── mlClient.py             # Image server (+ /api/latest endpoint) + ML API client
└── .env                        # Credentials (gitignored)
```
