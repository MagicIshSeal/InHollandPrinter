import datetime
import json
import time
import urllib.error
import urllib.request

BASE = "http://printer-monitor:8080"
MANAGER_RECORDS = "/data/manager_received.jsonl"


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


def test_manager_cancel_notification(timeout: int = 300):
    print("[test-api] Waiting for manager API auto-cancel notification...")
    deadline = time.time() + timeout
    last_err = "no records yet"
    while time.time() < deadline:
        try:
            with open(MANAGER_RECORDS) as f:
                records = [json.loads(line) for line in f if line.strip()]
        except FileNotFoundError:
            records = []
        for rec in records:
            if rec.get("printer_name") != "Mock Printer":
                continue
            datetime.datetime.fromisoformat(rec["cancelled_at"])  # ISO-8601
            assert rec["ip"] == "mock-printer", f"Expected public_ip 'mock-printer', got {rec['ip']!r}"
            assert rec["progress"] == "42", f"Expected progress '42', got {rec['progress']!r}"
            assert rec["image_name"].endswith(".jpg"), f"Bad image_name: {rec['image_name']!r}"
            assert rec["image_size"] > 1000, f"Manager image too small: {rec['image_size']} bytes"
            print(f"[test-api]   PASS — manager got AUTO_CANCELLED for {rec['printer_name']} "
                  f"(ip={rec['ip']}, progress={rec['progress']}, image={rec['image_name']})")
            return
        last_err = f"{len(records)} record(s), none for 'Mock Printer'"
        time.sleep(5)
    raise AssertionError(f"No manager cancel notification within {timeout}s ({last_err})")


if __name__ == "__main__":
    print("[test-api] Waiting for printer-monitor to produce images...")
    _wait_for_annotated()
    test_list_all()
    test_latest_image()
    test_latest_404()
    test_manager_cancel_notification()
    print("[test-api] ALL PASS")
