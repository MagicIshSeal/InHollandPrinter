import json
from pathlib import Path

from inhollandPrinter.settings import settings

REQUEST_TIMEOUT = 5
# seconds; keep short so one dead printer doesn't stall the rest

PRINTERS_FILE = Path(__file__).parent / "printers.json"


class PrinterDict(dict):

    def __getitem__(self, key):
        value = dict.__getitem__(self, key)

        if isinstance(value, dict) and "copy_from" in value:
            parent = self[value["copy_from"]]

            # Child overrides parent
            return {
                **parent,
                **{k: v for k, v in value.items() if k != "copy_from"},
            }

        return value

    def local_ip_id(self, key):
        return f"{self[key]['local_ip']}/{self[key]['id']}"

    def public_ip_id(self, key):
        return f"{self[key]['public_ip']}/{self[key]['id']}"

    def login_address(self, key):
        """Address used for PrusaLink login. In Core One mode the printer
        is reachable at the raw public IP; otherwise <ip>/<id>."""
        if settings.setCoreOne:
            return self[key]["public_ip"]
        return self.public_ip_id(key)

    def get_status(self, key):
        return self[key]["status"] if "status" in self[key] else "UNKNOWN"

    def get_nozzle_temp(self, key):
        return self[key]["temp_nozzle"] if "temp_nozzle" in self[key] else None

    def get_bed_temp(self, key):
        return self[key]["temp_bed"] if "temp_bed" in self[key] else None

    def get_time_remaining(self, key):
        return self[key]["time_remaining"] if "time_remaining" in self[key] else None

    def get_job_id(self, key):
        return self[key]["job_id"] if "job_id" in self[key] else None

    def get_password(self, key):
        """Per-printer password override from printers.json, if set."""
        return self[key].get("password") if "password" in self[key] else None

    def get_last_image(self, key):
        return self[key]["last_image"] if "last_image" in self[key] else None

    def get_index(self, key):
        return self[key]["index"] if "index" in self[key] else 0

    def set_index(self, key, value):
        dict.__getitem__(self, key)["index"] = value

    def set_last_image(self, key, value):
        dict.__getitem__(self, key)["last_image"] = value

    def get_uuid(self, key):
        return self[key].get("uuid", "00000000-0000-0000-0000-000000000000")


def load_printers(path: Path = PRINTERS_FILE) -> PrinterDict:
    with open(path) as f:
        data = json.load(f)
    return PrinterDict(data)


printers = load_printers()


if __name__ == "__main__":
    print(printers.local_ip_id("Printer 6"))
