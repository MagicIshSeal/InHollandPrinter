"""
Everything that talks to the PrusaConnect SDK.

Direct port of what handlePrinter.py did directly at module level:

    client = PrusaConnectClient()
    client.printers.list_printers()
    client.cameras.list()
    client.get_snapshot(cam.id)

No new behavior — just wrapped in a class instead of a bare global
`client`, so main.py creates it once and passes it to whatever needs it.
"""
from prusa.connect.client import PrusaConnectClient


class PrinterClient:
    def __init__(self):
        self._client = PrusaConnectClient()

    def list_printers(self):
        return self._client.printers.list_printers()

    def list_cameras(self):
        return self._client.cameras.list()

    def get_snapshot(self, camera_id: str) -> bytes:
        return self._client.get_snapshot(camera_id)

    # TODO: pause_print(printer) -> None
    # Not implemented anywhere in the current code — detection happens,
    # but nothing ever actually stops a print. This is the method
    # you'll need once you build actual stop logic (see monitor.py's
    # TODO on SpaghettiDetector).
