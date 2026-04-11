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
import os
import re
import sys
from datetime import date, datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
DASHBOARD_DIR = PROJECT_DIR / "dashboard"
TRACKING_FILE = PROJECT_DIR / "data" / "tracking.json"
TRACKING_TEMPLATE = PROJECT_DIR / "data" / "tracking-template.json"
ALL_JOBS_FILE = PROJECT_DIR / "data" / "jobs" / "all-jobs.json"
PORT = 8777


def _empty_tracking():
    return {
        "metadata": {"version": "3.0", "created": "", "last_updated": ""},
        "applications": [],
        "unlinked_outreach": [],
        "legacy_applications": [],
        "stats": {},
    }


def load_tracking():
    if TRACKING_FILE.exists():
        with open(TRACKING_FILE) as f:
            return json.load(f)
    return _empty_tracking()


def save_tracking(data):
    data.setdefault("metadata", {})
    data["metadata"]["last_updated"] = date.today().isoformat()

    all_outreach = []
    for app in data.get("applications", []):
        all_outreach.extend(app.get("outreach", []))
    all_outreach.extend(data.get("unlinked_outreach", []))
    positive = sum(1 for o in all_outreach if o.get("outcome") in ("accepted", "replied", "interview"))
    interviews = sum(1 for o in all_outreach if o.get("outcome") == "interview")
    data["stats"] = {
        "total_applications": len(data.get("applications", [])),
        "total_outreach_sent": len(all_outreach),
        "positive_outcomes": positive,
        "interviews_scheduled": interviews,
    }

    TRACKING_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRACKING_FILE, "w") as f:
        json.dump(data, f, indent=2)

    try:
        from generate_data_js import generate
        generate()
    except Exception as e:
        print(f"  (warning: generate_data_js failed: {e})")


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
            self._send_json(load_tracking())
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
            save_tracking(data)
            self._send_json({"status": "saved"})
            print(f"  Saved tracking data ({len(data.get('applications', []))} applications)")
            return

        if self.path == "/api/tracking/apply":
            tracking = load_tracking()
            company = data.get("company", "")
            role = data.get("role", "")

            app = next(
                (a for a in tracking["applications"]
                 if a["company"].lower() == company.lower()
                 and a.get("role", "").lower() == role.lower()),
                None,
            )
            now_iso = datetime.now(timezone.utc).isoformat()
            today = date.today().isoformat()
            if app:
                app["status"] = "applied"
                if not app["dates"].get("applied"):
                    app["dates"]["applied"] = today
                    app["dates"]["applied_at"] = now_iso
            else:
                slug = re.sub(r"[^a-z0-9]+", "-", f"{company} {role}".lower()).strip("-")
                try:
                    from company_classifier import classify
                    size = classify(company)
                except Exception:
                    size = "unknown"
                tracking["applications"].append({
                    "id": f"{today}-{slug}",
                    "company": company,
                    "role": role,
                    "url": data.get("url"),
                    "source": data.get("source", "linkedin"),
                    "company_size": size,
                    "salary_range": data.get("salary_range"),
                    "location": data.get("location"),
                    "status": "applied",
                    "dates": {
                        "saved": today,
                        "applied": today,
                        "applied_at": now_iso,
                        "rejected": None,
                        "offer": None,
                    },
                    "cover_letter": None,
                    "outreach": [],
                    "notes": "",
                })

            save_tracking(tracking)
            self._send_json({"status": "saved"})
            print(f"  Marked applied: {company} / {role}")
            return

        if self.path == "/api/tracking/outreach":
            tracking = load_tracking()
            company = data.get("company", "")

            app = next(
                (a for a in tracking["applications"]
                 if a["company"].lower() == company.lower()),
                None,
            )
            if not app:
                self._send_json({"error": f"No application found for {company}"}, 404)
                return

            today = date.today().isoformat()
            name = data.get("name", "")
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            msg = data.get("message", "")

            outreach_entry = {
                "id": f"outreach-{today}-{slug}",
                "name": name,
                "recipient_role": data.get("recipient_role", "unknown"),
                "linkedin_url": data.get("linkedin_url"),
                "type": data.get("type", "connection-request"),
                "variant": data.get("variant"),
                "message": msg,
                "message_length": len(msg),
                "dates": {"sent": today, "accepted": None, "replied": None, "interview": None},
                "outcome": "pending",
                "response_time_days": None,
                "follow_ups": [],
            }
            app["outreach"].append(outreach_entry)
            save_tracking(tracking)
            self._send_json({"status": "saved"})
            print(f"  Logged outreach: {name} at {company}")
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
            tracking = load_tracking()
            outreach_id = self.path.split("/")[-1]

            found = False
            for app in tracking["applications"]:
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
                save_tracking(tracking)
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


def _ensure_tracking_file():
    if TRACKING_FILE.exists():
        return
    TRACKING_FILE.parent.mkdir(parents=True, exist_ok=True)
    if TRACKING_TEMPLATE.exists():
        with open(TRACKING_TEMPLATE) as src, open(TRACKING_FILE, "w") as dst:
            dst.write(src.read())
    else:
        with open(TRACKING_FILE, "w") as f:
            json.dump(_empty_tracking(), f, indent=2)


def main():
    sys.path.insert(0, str(PROJECT_DIR / "scripts"))
    _ensure_tracking_file()

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
    print(f"Tracking:  {TRACKING_FILE}")
    print("Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
