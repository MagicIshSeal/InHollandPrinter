"""
Every value that was previously hardcoded across the two original files
lives here now, read from environment variables / a .env file:

  - IMG_DIR              (handlePrinter.py)  -> snapshot_dir
  - ML_API                (getFailure.py)     -> ml_api_url
  - ML_API_DIR            (getFailure.py)     -> ml_api_project_dir
  - HOST_IP               (getFailure.py)     -> image_server_host_ip
  - IMAGE_DIR             (getFailure.py)     -> image_dir
  - PORT                  (getFailure.py)     -> image_server_port
  - cycleTime             (handlePrinter.py)  -> poll_cycle_seconds
  - the `time.sleep(5)`   (handlePrinter.py)  -> main_loop_sleep_seconds

Nothing else in the codebase should read os.environ directly or
hardcode a path/IP. Need a new configurable value? Add it here first.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # --- ML detection API ---
    mlApiUrl: str = "http://localhost:3333/p/"
    mlApiProjectDir: Path = Path("/home/mvane/Documents/GitClone/obico-server")

    # --- Local image HTTP server ---
    imageServerHostIp: str = "145.81.121.204"
    imageServerPort: int = 8080
    imageDir: Path = Path("/home/mvane/Documents/GitClone/InHollandPrinter/")

    # --- Snapshot storage — see NOTE above about the IMG_DIR/IMAGE_DIR mismatch ---
    snapshotDir: Path = Path("img")

    # --- Polling loop ---
    pollCycleSeconds: int = 15
    mainLoopSleepSeconds: int = 5

    # TODO: PrusaConnect credentials currently come from wherever
    # PrusaConnectClient() reads them by default. If that ever needs to
    # be explicit here, add a field, e.g.: prusa_api_token: str | None = None


settings = Settings()
