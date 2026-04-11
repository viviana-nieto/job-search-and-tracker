#!/usr/bin/env python3
"""
Local server for the job search dashboard.

Serves dashboard/*.html at http://localhost:8777/ and handles tracking API
requests backed by data/tracking.json. The HTML pages auto-detect localhost
and talk to this server's /api/* endpoints; when the server is not running
they fall back to the embedded dashboard/data.js.

Run:
    python scripts/local_server.py
"""

import json
import sys
from datetime import date, datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
DASHBOARD_DIR = PROJECT_DIR / "dashboard"
ALL_JOBS_FILE = PROJECT_DIR / "data" / "jobs" / "all-jobs.json"
PORT = 8777

# Ensure the scripts dir is importable before we import tracking — the shared
# module lives next to this file.
sys.path.insert(0, str(Path(__file__).parent))
import tracking  # noqa: E402


class JobSearchHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/tracking":
            self._send_json(tracking.load())
            return

        if self.path == "/api/jobs":
            if ALL_JOBS_FILE.exists():
                with open(ALL_JOBS_FILE) as f:
                    data = json.load(f)
            else:
                data = []
            self._send_json(data)
            return

        super().do_GET()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        if self.path == "/api/tracking":
            tracking.save(data)
            self._send_json({"status": "saved"})
            print(f"  Saved tracking data ({len(data.get('applications', []))} applications)")
            return

        if self.path == "/api/tracking/apply":
            tracking_data = tracking.load()
            company = data.get("company", "")
            role = data.get("role", "")

            try:
                from company_classifier import classify
                size = classify(company)
            except Exception:
                size = "unknown"

            app = tracking.find_or_create_application(
                tracking_data,
                company=company,
                role=role,
                company_size=size,
                url=data.get("url"),
                source=data.get("source", "linkedin"),
                salary_range=data.get("salary_range"),
                location=data.get("location"),
            )

            now_iso = datetime.now(timezone.utc).isoformat()
            today = date.today().isoformat()
            app["status"] = "applied"
            if not app.get("dates", {}).get("applied"):
                app.setdefault("dates", {})
                app["dates"]["applied"] = today
                app["dates"]["applied_at"] = now_iso

            tracking.save(tracking_data)
            self._send_json({"status": "saved"})
            print(f"  Marked applied: {company} / {role}")
            return

        if self.path == "/api/tracking/outreach":
            tracking_data = tracking.load()
            company = data.get("company", "")

            app = next(
                (a for a in tracking_data["applications"]
                 if a["company"].lower() == company.lower()),
                None,
            )
            if not app:
                self._send_json({"error": f"No application found for {company}"}, 404)
                return

            outreach_entry = tracking.build_outreach_entry(
                name=data.get("name", ""),
                recipient_role=data.get("recipient_role", "unknown"),
                msg_type=data.get("type", "connection-request"),
                message=data.get("message", ""),
                linkedin_url=data.get("linkedin_url"),
                variant=data.get("variant"),
            )
            app.setdefault("outreach", []).append(outreach_entry)
            tracking.save(tracking_data)
            self._send_json({"status": "saved"})
            print(f"  Logged outreach: {outreach_entry.get('name')} at {company}")
            return

        self.send_response(404)
        self.end_headers()

    def do_PUT(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        if self.path.startswith("/api/tracking/outreach/"):
            tracking_data = tracking.load()
            outreach_id = self.path.split("/")[-1]

            found = False
            for app in tracking_data["applications"]:
                for o in app.get("outreach", []):
                    if o["id"] == outreach_id:
                        for key in ("outcome", "recipient_role"):
                            if key in data:
                                o[key] = data[key]
                        if "status" in data:
                            status = data["status"]
                            today = date.today().isoformat()
                            if status == "accepted":
                                o["dates"]["accepted"] = today
                                o["outcome"] = "accepted"
                                if o["dates"].get("sent"):
                                    o["response_time_days"] = (
                                        datetime.fromisoformat(today) - datetime.fromisoformat(o["dates"]["sent"])
                                    ).days
                            elif status == "replied":
                                o["dates"]["replied"] = today
                                o["outcome"] = "replied"
                            elif status == "interview":
                                o["dates"]["interview"] = today
                                o["outcome"] = "interview"
                            elif status in ("declined", "no_response"):
                                o["outcome"] = status
                        found = True
                        break
                if found:
                    break

            if found:
                tracking.save(tracking_data)
                self._send_json({"status": "updated"})
            else:
                self._send_json({"error": "Outreach not found"}, 404)
            return

        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        if "/api/" in str(args[0]):
            print(f"  {args[0]}")


def main():
    sys.path.insert(0, str(PROJECT_DIR / "scripts"))

    # Materialize tracking.json on disk so file-backed reads work from the
    # moment the server starts. tracking.load() handles template copying and
    # legacy migration lazily; the save() call persists the result.
    tracking.save(tracking.load(), regen_js=False)

    if not DASHBOARD_DIR.exists():
        print(f"Error: dashboard directory not found at {DASHBOARD_DIR}")
        sys.exit(1)

    # Regenerate dashboard/data.js so the HTML has embedded fallback data
    # even when someone launches this server directly (bypassing dashboard.py).
    try:
        from generate_data_js import generate
        generate()
    except Exception as e:
        print(f"  (warning: data.js regeneration failed: {e})")

    server = HTTPServer(("localhost", PORT), JobSearchHandler)
    print(f"Job Search Server running at http://localhost:{PORT}")
    print(f"Dashboard: http://localhost:{PORT}/dashboard.html")
    print(f"All Jobs:  http://localhost:{PORT}/jobs.html")
    print(f"Companies: http://localhost:{PORT}/companies.html")
    print(f"Tracking:  {tracking.TRACKING_FILE}")
    print("Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
