# InHollandPrinter — Spaghetti Detection for 3D Printers

Monitors PrusaLink-connected printers, captures snapshots during active prints, and runs them through a YOLO-based ML model to detect spaghetti failures.

## Prerequisites

- Docker & Docker Compose v2

## Quick Start

```bash
# 1. Clone with submodules
git clone --recurse-submodules <repo-url>
cd InHollandPrinter

# 2. Configure credentials
cp .env.example .env
# Edit .env with your PrusaLink credentials

# 3. Start production
docker compose up --build
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
- Annotated images (spaghetti boxes drawn): `./img/test/<PrinterName>/snapshot<PrinterName>_<index>_annotated.jpg`

## Configuration

All via environment variables (or `.env` file):

| Variable | Default | Description |
|---|---|---|
| `LOCAL_USERNAME` | — | PrusaLink username |
| `LOCAL_PASSWORD` | — | PrusaLink password |
| `ML_API_URL` | `http://ml_api:3333/p/` | ML detection endpoint |
| `IMAGE_SERVER_PUBLIC_HOST` | `printer-monitor` | Hostname ML API uses to fetch snapshots |
| `SNAPSHOT_DIR` | `img/` | Directory for raw snapshots |

## Printers

Edit `src/inhollandPrinter/printers.json`:

```json
[
"Printer Name": {"public_ip": "192.168.0.1", 
                  "local_ip": "192.168.0.1", 
                  "id": "1", 
                  }
]
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
├── img/                        # Output: raw snapshots + annotated images
├── src/inhollandPrinter/
│   ├── main.py                 # Entry point
│   ├── monitor.py              # Polling loop + spaghetti detection pipeline
│   ├── settings.py             # pydantic-settings config
│   ├── printerClient.py        # PrusaLink HTTP client
│   ├── imageStore.py           # Save raw & annotated images
│   └── mlClient.py             # ML API client
└── .env                        # Credentials (gitignored)
```
