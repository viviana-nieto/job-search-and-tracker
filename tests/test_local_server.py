"""HTTP integration tests for scripts/local_server.py.

Starts a real HTTPServer bound to a throwaway port per test, hits the API via
urllib, and asserts tracking state through the same endpoints.
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

import tracking  # noqa: E402
import local_server  # noqa: E402

try:
    from fixtures import FixedClock  # noqa: F401
except ImportError:
    from datetime import date

    class FixedClock:  # type: ignore
        def __init__(self, iso_date: str = "2026-04-11"):
            self._today = date.fromisoformat(iso_date)

        def today_str(self) -> str:
            return self._today.isoformat()


class BaseServerTest(unittest.TestCase):
    """Spin up a JobSearchHandler on a random port with isolated file paths."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

        # Preserve originals so we can put them back in tearDown.
        self._orig_tracking = tracking.TRACKING_FILE
        self._orig_template = tracking.TRACKING_TEMPLATE
        self._orig_legacy = tracking.LEGACY_FILE
        self._orig_regen = tracking._regen_data_js_silently
        self._orig_dashboard_dir = local_server.DASHBOARD_DIR
        self._orig_all_jobs = local_server.ALL_JOBS_FILE

        # Redirect tracking module state to our temp dir.
        tracking.TRACKING_FILE = self.tmp_path / "tracking.json"
        tracking.TRACKING_TEMPLATE = self.tmp_path / "tracking-template.json"
        tracking.LEGACY_FILE = self.tmp_path / "outreach-history.json"
        tracking._regen_data_js_silently = lambda: None

        # Seed empty template + tracking so load() is fully offline.
        tracking.TRACKING_TEMPLATE.write_text(
            json.dumps(tracking._empty_tracking())
        )
        tracking.TRACKING_FILE.write_text(
            json.dumps(tracking._empty_tracking())
        )

        # Stub dashboard dir with a placeholder file for static-file serving.
        self.dashboard_dir = self.tmp_path / "dashboard"
        self.dashboard_dir.mkdir()
        (self.dashboard_dir / "dashboard.html").write_text(
            "<html><body>stub dashboard</body></html>"
        )
        local_server.DASHBOARD_DIR = self.dashboard_dir

        # Route ALL_JOBS_FILE into the temp dir — tests may or may not create it.
        local_server.ALL_JOBS_FILE = self.tmp_path / "all-jobs.json"

        # Start server on a random free port.
        self.server = HTTPServer(("localhost", 0), local_server.JobSearchHandler)
        self.port = self.server.server_port
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()
        self.base_url = f"http://localhost:{self.port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

        tracking.TRACKING_FILE = self._orig_tracking
        tracking.TRACKING_TEMPLATE = self._orig_template
        tracking.LEGACY_FILE = self._orig_legacy
        tracking._regen_data_js_silently = self._orig_regen
        local_server.DASHBOARD_DIR = self._orig_dashboard_dir
        local_server.ALL_JOBS_FILE = self._orig_all_jobs
        self.tmp.cleanup()

    # ---- helpers ---------------------------------------------------------

    def _request(self, method, path, data=None):
        url = self.base_url + path
        body = None
        headers = {}
        if data is not None:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as r:
                raw = r.read()
                status = r.status
        except urllib.error.HTTPError as e:
            raw = e.read()
            status = e.code
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw.decode(errors="replace")
        return status, parsed

    def _get(self, path):
        return self._request("GET", path)

    def _post(self, path, data):
        return self._request("POST", path, data)

    def _put(self, path, data):
        return self._request("PUT", path, data)

    def _options(self, path):
        req = urllib.request.Request(self.base_url + path, method="OPTIONS")
        with urllib.request.urlopen(req) as r:
            return r.status, dict(r.headers)


# ---------------------------------------------------------------------------
# GET endpoints
# ---------------------------------------------------------------------------

class TestGetEndpoints(BaseServerTest):
    def test_get_tracking_empty_state(self):
        status, body = self._get("/api/tracking")
        self.assertEqual(status, 200)
        self.assertIsInstance(body, dict)
        self.assertEqual(body["applications"], [])
        self.assertEqual(body["unlinked_outreach"], [])
        self.assertEqual(body["metadata"]["version"], "3.0")
        self.assertIn("stats", body)

    def test_get_jobs_missing_file_returns_empty_list(self):
        # ALL_JOBS_FILE intentionally does not exist.
        self.assertFalse(local_server.ALL_JOBS_FILE.exists())
        status, body = self._get("/api/jobs")
        self.assertEqual(status, 200)
        self.assertEqual(body, [])

    def test_get_jobs_with_file(self):
        local_server.ALL_JOBS_FILE.write_text(json.dumps([{"title": "Test"}]))
        status, body = self._get("/api/jobs")
        self.assertEqual(status, 200)
        self.assertEqual(body, [{"title": "Test"}])


# ---------------------------------------------------------------------------
# POST /api/tracking/apply
# ---------------------------------------------------------------------------

class TestPostTrackingApply(BaseServerTest):
    def test_apply_creates_application(self):
        status, body = self._post(
            "/api/tracking/apply",
            {
                "company": "Acme",
                "role": "PM",
                "url": "https://x",
                "source": "linkedin",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "saved"})

        _, data = self._get("/api/tracking")
        self.assertEqual(len(data["applications"]), 1)
        app = data["applications"][0]
        self.assertEqual(app["company"], "Acme")
        self.assertEqual(app["role"], "PM")
        self.assertEqual(app["status"], "applied")
        self.assertIsNotNone(app["dates"]["applied"])

    def test_apply_is_idempotent_on_duplicate(self):
        payload = {"company": "Acme", "role": "PM", "url": "https://x"}
        self._post("/api/tracking/apply", payload)
        self._post("/api/tracking/apply", payload)

        _, data = self._get("/api/tracking")
        self.assertEqual(len(data["applications"]), 1)
        self.assertEqual(data["stats"]["total_applications"], 1)
        self.assertEqual(data["stats"]["total_outreach_sent"], 0)


# ---------------------------------------------------------------------------
# POST /api/tracking/outreach
# ---------------------------------------------------------------------------

class TestPostTrackingOutreach(BaseServerTest):
    def _seed_apply(self):
        self._post(
            "/api/tracking/apply",
            {"company": "Acme", "role": "PM", "url": "https://x"},
        )

    def test_outreach_nests_under_application(self):
        self._seed_apply()
        status, body = self._post(
            "/api/tracking/outreach",
            {
                "company": "Acme",
                "name": "Alice",
                "recipient_role": "recruiter",
                "type": "connection-request",
                "message": "Hi",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "saved"})

        _, data = self._get("/api/tracking")
        self.assertEqual(len(data["applications"]), 1)
        nested = data["applications"][0]["outreach"]
        self.assertEqual(len(nested), 1)
        entry = nested[0]
        self.assertTrue(entry["id"].startswith("outreach-"))
        self.assertEqual(entry["outcome"], "pending")
        self.assertIsNotNone(entry["dates"]["sent"])
        self.assertEqual(entry["name"], "Alice")
        self.assertEqual(data["stats"]["total_outreach_sent"], 1)

    def test_outreach_without_matching_app_returns_404(self):
        status, body = self._post(
            "/api/tracking/outreach",
            {
                "company": "Ghost",
                "name": "Nobody",
                "recipient_role": "recruiter",
                "type": "connection-request",
                "message": "Hello",
            },
        )
        self.assertEqual(status, 404)
        self.assertIn("error", body)
        self.assertIn("Ghost", body["error"])


# ---------------------------------------------------------------------------
# PUT /api/tracking/outreach/<id>
# ---------------------------------------------------------------------------

class TestPutTrackingOutreach(BaseServerTest):
    def _seed_apply_and_outreach(self):
        self._post(
            "/api/tracking/apply",
            {"company": "Acme", "role": "PM", "url": "https://x"},
        )
        self._post(
            "/api/tracking/outreach",
            {
                "company": "Acme",
                "name": "Alice",
                "recipient_role": "recruiter",
                "type": "connection-request",
                "message": "Hi",
            },
        )
        _, data = self._get("/api/tracking")
        return data["applications"][0]["outreach"][0]["id"]

    def test_put_accepted_updates_outcome_and_dates(self):
        oid = self._seed_apply_and_outreach()
        status, body = self._put(
            f"/api/tracking/outreach/{oid}", {"status": "accepted"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "updated"})

        _, data = self._get("/api/tracking")
        entry = data["applications"][0]["outreach"][0]
        self.assertEqual(entry["outcome"], "accepted")
        self.assertIsNotNone(entry["dates"]["accepted"])
        self.assertEqual(data["stats"]["positive_outcomes"], 1)

    def test_put_nonexistent_id_returns_404(self):
        self._seed_apply_and_outreach()  # at least one app must exist to iterate
        status, body = self._put(
            "/api/tracking/outreach/outreach-does-not-exist",
            {"status": "accepted"},
        )
        self.assertEqual(status, 404)
        self.assertIn("error", body)


# ---------------------------------------------------------------------------
# POST /api/tracking (full state dump)
# ---------------------------------------------------------------------------

class TestPostFullTrackingDump(BaseServerTest):
    def test_full_state_persists(self):
        dump = tracking._empty_tracking()
        dump["applications"].append(
            {
                "id": "2026-04-11-acme-pm",
                "company": "Acme",
                "role": "PM",
                "status": "applied",
                "dates": {"saved": "2026-04-11", "applied": "2026-04-11"},
                "outreach": [],
            }
        )
        status, body = self._post("/api/tracking", dump)
        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "saved"})

        _, data = self._get("/api/tracking")
        self.assertEqual(len(data["applications"]), 1)
        self.assertEqual(data["applications"][0]["company"], "Acme")


# ---------------------------------------------------------------------------
# OPTIONS (CORS preflight)
# ---------------------------------------------------------------------------

class TestOptions(BaseServerTest):
    def test_options_sets_cors_headers(self):
        status, headers = self._options("/api/tracking")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "*")
        self.assertIn("POST", headers.get("Access-Control-Allow-Methods", ""))
        self.assertIn("Content-Type", headers.get("Access-Control-Allow-Headers", ""))


# ---------------------------------------------------------------------------
# Static file serving
# ---------------------------------------------------------------------------

class TestStaticFile(BaseServerTest):
    def test_static_dashboard_html(self):
        # The base test class already seeds dashboard/dashboard.html.
        with urllib.request.urlopen(self.base_url + "/dashboard.html") as r:
            body = r.read().decode()
            self.assertEqual(r.status, 200)
        self.assertIn("stub dashboard", body)


if __name__ == "__main__":
    unittest.main()
