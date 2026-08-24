# AGENTS.md

## Architecture

- `src/inhollandPrinter` is a `src/`-layout package (`pyproject.toml`); entry point is `python -m inhollandPrinter.main`. `main.py` is the composition root that creates and wires everything.
- Pipeline: `main.py` loop → `monitor.py` `PrinterMonitor` (status poll + snapshot) → `DetectionWorker` thread queue → `SpaghettiDetector.evaluate()` → `ObicoMLClient.checkForSpaghetti()` (passes the image server's own URL to the ML API, which fetches the image back over HTTP) → `LocalImageStore.saveAnnotated()`. This is why `IMAGE_SERVER_PUBLIC_HOST` must be resolvable from inside the compose network.
- `settings.py` is the **only** place env vars / `.env` are read (pydantic-settings). Add new configurable values there, never read `os.environ` elsewhere.
- `config.py` loads `printers.json` (lives inside the package dir) at import time; both compose files bind-mount it read-only, so edits need no rebuild (tests use `test/printers.test.json`).
- `mlClient.py` also runs an HTTP image server with `/api/latest` endpoints (documented in `docs/api.md`).

## Verification (all Docker-based)

- **No pytest / lint / typecheck / CI exist.** The Docker test stack is the only automated verification.
- Test run:
  ```
  docker compose -f docker-compose.yml -f docker-compose.test.yml down -v
  docker compose -f docker-compose.yml -f docker-compose.test.yml build printer-monitor
  docker compose -f docker-compose.yml -f docker-compose.test.yml up --abort-on-container-exit
  ```
- `up --abort-on-container-exit` exits when `test-api` finishes (`test/test_api.py`, prints `ALL PASS`; any assertion failure makes the run exit non-zero).
- ML API has a 30s healthcheck `start_period`; the monitor only starts polling once it's healthy. Mock-printer behavior comes from env vars in `docker-compose.test.yml` (`SNAPSHOT_FILE`, `PRINTER_STATE`, `TIME_REMAINING`; negative time = no active job).
- Production: `docker compose up --build`. The Dockerfile installs the package from `pyproject.toml` (`pip install -e .`); `requirements.txt` is legacy pins, not used by any build.

## Gotchas

- **`ml_api` is a prebuilt image** (`ghcr.io/gabe565/obico/ml-api:latest`, built from obico-server commit `9b73caa7`), so no sibling checkout is needed — the obico-server repo is *not* a submodule (no `.gitmodules`; README's `--recurse-submodules` is stale).
- **`PrinterDict.__getitem__` returns a fresh merged dict for `copy_from` printers** (`config.py:14-26`). Mutating `printers[name][...]` writes to a throwaway copy. Writes must go through `dict.__getitem__(printers, name)` — see `monitor.py:53,71` and `set_index`/`set_last_image` (`config.py:67,70`).
- **PrusaLink uses HTTP Digest auth** (`auth.py`); every call creates a new client via `login()`. `test/mock_printer.py` also implements digest auth. A per-printer `password` key in `printers.json` overrides the global `LOCAL_PASSWORD` (`login()` second arg; read via `config.get_password`), inherited through `copy_from`.
- **Core One mode branches only the snapshot fetch**: when `settings.setCoreOne` is true, `PrinterClient.getSnapshot` fetches a plain unauthenticated GET to `http://{coreOneImg}{CORE_ONE_ENDPOINT}` (`CORE_ONE_ENDPOINT = "/image/{printerName}"`, printerClient.py:30; the `{printerName}` template is URL-encoded); status polling and stop/resume still use PrusaLink. `config.login_address()` returns the raw `public_ip` (no `/id`) when Core One mode is active, so the `id` key in `printers.json` is optional for that setup.
- **Snapshots only happen while a job is active**: `checkPictures` skips printers whose `time_remaining` is `None` or negative (`monitor.py:88-90`). A printer with no active job silently produces no images — expected, not a bug. When a printer has no active job, the consecutive-failure counter is reset via `SpaghettiDetector.reset`.
- **Image index cycles 0–4** then resets (`monitor.py:98-99`); filenames are `snapshot<PrinterName>[_<index>].jpg`, annotated copies under `<printer>/annotated/`.
- **`stopPrint`/`resumePrint` use the `job_id` cached from the last status poll** (`DELETE|POST /api/v1/job/{job_id}`, `printerClient.py:49-61`); raise if none cached.
- **`.env` is required** (mounted read-only), gitignored, and holds real credentials — don't print or commit it. `cp .env.example .env` to start.
- **`img/` is root-owned** (container writes as root); cleaning it on the host may need `sudo`.
- **ML detections are `[label, confidence, [cx, cy, width, height]]`**; `SpaghettiDetector` filters by `settings.confidenceThreshold` (default **0.5** in `settings.py` — README's table *and* `.env.example` still say 0.3; trust the code).
- **Logging**: `LOG_LEVEL` env (DEBUG/INFO/WARNING). `urllib3.connectionpool` is forced to WARNING in `main.py:48`; at DEBUG the 401→200 digest-auth handshake noise is normal.
