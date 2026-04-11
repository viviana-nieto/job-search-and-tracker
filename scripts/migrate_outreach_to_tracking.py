#!/usr/bin/env python3
"""One-shot migration: data/outreach-history.json → data/tracking.json.

For users upgrading from the pre-dashboard version of the open project. Reads
the legacy outreach-history.json and merges its entries into the unified
tracking.json v3.0 schema so the dashboard picks them up.

Safe to run multiple times — it merges rather than overwrites.

Usage:
    python scripts/migrate_outreach_to_tracking.py
"""

import json
import sys
from datetime import date
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
LEGACY_FILE = PROJECT_DIR / "data" / "outreach-history.json"
TRACKING_FILE = PROJECT_DIR / "data" / "tracking.json"
TRACKING_TEMPLATE = PROJECT_DIR / "data" / "tracking-template.json"


def _load_json(path, default):
    if not path.exists():
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _empty_tracking():
    if TRACKING_TEMPLATE.exists():
        return _load_json(TRACKING_TEMPLATE, None) or {}
    return {
        "metadata": {"version": "3.0", "created": "", "last_updated": ""},
        "applications": [],
        "unlinked_outreach": [],
        "legacy_applications": [],
        "stats": {},
    }


def main():
    legacy = _load_json(LEGACY_FILE, None)
    if legacy is None:
        print(f"  Nothing to migrate — {LEGACY_FILE} not found.")
        return

    tracking = _load_json(TRACKING_FILE, None) or _empty_tracking()
    tracking.setdefault("metadata", {})
    tracking.setdefault("applications", [])
    tracking.setdefault("unlinked_outreach", [])
    tracking.setdefault("legacy_applications", [])

    today = date.today().isoformat()
    tracking["metadata"]["last_updated"] = today
    if not tracking["metadata"].get("created"):
        tracking["metadata"]["created"] = legacy.get("metadata", {}).get("created", today)

    # Legacy connections → unlinked_outreach entries
    migrated_outreach = 0
    existing_outreach_ids = {o.get("id") for o in tracking["unlinked_outreach"]}
    for conn in legacy.get("connections", []):
        name = conn.get("name", "")
        company = conn.get("company", "")
        slug = f"{name.lower().replace(' ', '-')}-{company.lower().replace(' ', '-')}"
        oid = f"outreach-legacy-{slug}"
        if oid in existing_outreach_ids:
            continue
        tracking["unlinked_outreach"].append({
            "id": oid,
            "name": name,
            "company": company,
            "recipient_role": conn.get("recipient_role", "unknown"),
            "linkedin_url": conn.get("linkedin_url", ""),
            "type": conn.get("type", "connection-request"),
            "variant": conn.get("variant"),
            "message": conn.get("message", ""),
            "message_length": len(conn.get("message", "")),
            "dates": {
                "sent": conn.get("sent_at", today),
                "accepted": None,
                "replied": None,
                "interview": None,
            },
            "outcome": conn.get("status", "pending"),
            "response_time_days": None,
            "follow_ups": [],
        })
        migrated_outreach += 1

    # Legacy applications → legacy_applications bucket (safe, non-destructive)
    migrated_apps = 0
    existing_legacy_ids = {a.get("id") for a in tracking["legacy_applications"]}
    for app in legacy.get("applications", []):
        aid = f"legacy-{app.get('company', '').lower()}-{app.get('title', '').lower()}"
        if aid in existing_legacy_ids:
            continue
        tracking["legacy_applications"].append({
            "id": aid,
            **app,
        })
        migrated_apps += 1

    TRACKING_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRACKING_FILE, "w") as f:
        json.dump(tracking, f, indent=2)

    print(f"  Migrated {migrated_outreach} outreach entries and {migrated_apps} legacy applications.")
    print(f"  Wrote {TRACKING_FILE}")
    print(f"  Legacy file left in place at {LEGACY_FILE} (safe to delete if this looks right).")


if __name__ == "__main__":
    main()
