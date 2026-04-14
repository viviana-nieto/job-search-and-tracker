#!/usr/bin/env python3
"""
Convenience launcher for the job search dashboard.

Regenerates dashboard/data.js, starts the local server, and opens the
dashboard in your browser.

Run:
    python scripts/dashboard.py              # regen + serve + open browser
    python scripts/dashboard.py --no-browser # regen + serve, no browser
    python scripts/dashboard.py --port 9000  # use a different port
"""

import argparse
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

PROJECT_DIR = Path(os.environ.get("JOB_SEARCH_DIR", Path(__file__).parent.parent))
sys.path.insert(0, str(PROJECT_DIR / "scripts"))


def main():
    parser = argparse.ArgumentParser(description="Start the job search dashboard.")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open the browser.")
    parser.add_argument("--port", type=int, default=None, help="Override the default port (8777).")
    args = parser.parse_args()

    import generate_data_js
    import local_server

    jobs_count, apps_count = generate_data_js.generate()
    print(f"  Regenerated dashboard/data.js ({jobs_count} jobs, {apps_count} applications)")

    if args.port:
        local_server.PORT = args.port

    url = f"http://localhost:{local_server.PORT}/dashboard.html"

    if not args.no_browser:
        def _open_browser():
            time.sleep(0.6)
            webbrowser.open(url)
        threading.Thread(target=_open_browser, daemon=True).start()

    local_server.main()


if __name__ == "__main__":
    main()
