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

NOTE found while porting: the original code has TWO separate,
inconsistent directories for images — IMG_DIR ("img", relative, used
for saving snapshots) and IMAGE_DIR (an absolute path, used by the
image HTTP server to know what to serve). They look like they're meant
to be the same folder but are defined independently in the two
original files. Kept as two separate settings here to replicate
current behavior exactly — but if they ever drift apart, the image
server won't find the files monitor.py just saved. Worth pointing both
at the same value once you touch this again.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # --- ML detection API ---
    ml_api_url: str = "http://localhost:3333/p/"
    ml_api_project_dir: Path = Path("/home/mvane/Documents/GitClone/obico-server")

    # --- Local image HTTP server ---
    image_server_host_ip: str = "10.127.122.135"
    image_server_port: int = 8080
    image_dir: Path = Path("/home/mvane/Documents/GitClone/InHollandPrinter/")

    # --- Snapshot storage — see NOTE above about the IMG_DIR/IMAGE_DIR mismatch ---
    snapshot_dir: Path = Path("img")

    # --- Polling loop ---
    poll_cycle_seconds: int = 15
    main_loop_sleep_seconds: int = 5

    # TODO: PrusaConnect credentials currently come from wherever
    # PrusaConnectClient() reads them by default. If that ever needs to
    # be explicit here, add a field, e.g.: prusa_api_token: str | None = None


settings = Settings()
