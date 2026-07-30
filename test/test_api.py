import json
import time
import urllib.error
import urllib.request

BASE = "http://printer-monitor:8080"


def _get(path: str):
    req = urllib.request.Request(f"{BASE}{path}")
    return urllib.request.urlopen(req, timeout=10)


def _wait_for_annotated(timeout: int = 120, interval: int = 5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = _get("/api/latest/Mock%20Printer")
            if resp.status == 200:
                print(f"[test-api] Annotated image available after {int(timeout - (deadline - time.time()))}s")
                return resp.read()
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            print(f"[test-api] Waiting... ({e})")
        time.sleep(interval)
    raise TimeoutError("No annotated image appeared within timeout")


def test_list_all():
    print("[test-api] Testing GET /api/latest")
    resp = _get("/api/latest")
    assert resp.status == 200, f"Expected 200, got {resp.status}"
    assert resp.headers.get("Content-Type") == "application/json", \
        f"Expected application/json, got {resp.headers.get('Content-Type')}"
    data = json.loads(resp.read())
    assert isinstance(data, dict), f"Expected dict, got {type(data)}"
    assert "Mock Printer" in data, f"Expected 'Mock Printer' in response, got {list(data.keys())}"
    latest = data["Mock Printer"]
    assert latest is not None and latest.endswith(".jpg"), \
        f"Expected a .jpg filename, got {latest!r}"
    print(f"[test-api]   PASS — Mock Printer latest: {latest}")
    return data


def test_latest_image():
    print("[test-api] Testing GET /api/latest/Mock%20Printer")
    resp = _get("/api/latest/Mock%20Printer")
    assert resp.status == 200, f"Expected 200, got {resp.status}"
    assert resp.headers.get("Content-Type") == "image/jpeg", \
        f"Expected image/jpeg, got {resp.headers.get('Content-Type')}"
    body = resp.read()
    assert len(body) > 1000, f"Response body too small: {len(body)} bytes"
    assert body[:2] == b"\xff\xd8", "Not a valid JPEG (missing SOI marker)"
    print(f"[test-api]   PASS — {len(body)} bytes, valid JPEG")


def test_latest_404():
    print("[test-api] Testing GET /api/latest/NonExistentPrinter")
    try:
        _get("/api/latest/NonExistentPrinter")
        assert False, "Expected 404"
    except urllib.error.HTTPError as e:
        assert e.code == 404, f"Expected 404, got {e.code}"
        err = json.loads(e.read())
        assert "error" in err, f"Expected 'error' key in response, got {err}"
        print(f"[test-api]   PASS — 404: {err['error']}")


if __name__ == "__main__":
    print("[test-api] Waiting for printer-monitor to produce images...")
    _wait_for_annotated()
    test_list_all()
    test_latest_image()
    test_latest_404()
    print("[test-api] ALL PASS")
