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
from inhollandPrinter.auth import login
from inhollandPrinter.config import *

class PrinterClient:
    def getSnapshot(self, printerName: str) -> bytes:
        client = login(printers.public_ip_id(printerName))
        _image = client.api_request("GET", "/api/v1/cameras/snap", raw=True)
        return _image.content

    def stopPrint(self, printerName: str) -> None:
        client = login(printers.public_ip_id(printerName))
        response = client.api_request("GET", "/api/v1/status")
        jobid = response["job"]["id"]
        response = client.api_request("DELETE", f"/api/v1/job/{jobid}")

    def resumePrint(self, printerName: str) -> None:
        client = login(printers.public_ip_id(printerName))
        response = client.api_request("GET", "/api/v1/status")
        jobid = response["job"]["id"]
        response = client.api_request("POST", f"/api/v1/job/{jobid}/resume")


    # TODO: pause_print(printer) -> None
    # Not implemented anywhere in the current code — detection happens,
    # but nothing ever actually stops a print. This is the method
    # you'll need once you build actual stop logic (see monitor.py's
    # TODO on SpaghettiDetector).
