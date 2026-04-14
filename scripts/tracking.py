"""Single source of truth for reading and writing data/tracking.json.

This module owns the v3.0 tracking schema. Every caller that logs outreach,
updates outcomes, recomputes stats, or serves the dashboard API goes through
here — never touching tracking.json or the legacy outreach-history.json
directly.

Key design notes:
- Stdlib only. No external deps.
- Clock is injectable on every function that timestamps anything: pass a
  `today` (str 'YYYY-MM-DD') or `now` (datetime) to make tests deterministic.
  Production callers omit the argument.
- Auto-migrates from data/outreach-history.json on load when tracking is
  empty and legacy has data. Prints a single informational line. The
  legacy file is left untouched.
- Mutates dicts in place rather than returning new copies, so the caller
  can load() once, mutate, and save() without worrying about staleness.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator, Optional, Tuple

PROJECT_DIR = Path(os.environ.get("JOB_SEARCH_DIR", Path(__file__).parent.parent))
TRACKING_FILE = PROJECT_DIR / "data" / "tracking.json"
TRACKING_TEMPLATE = PROJECT_DIR / "data" / "tracking-template.json"
LEGACY_FILE = PROJECT_DIR / "data" / "outreach-history.json"
DATA_JS_FILE = PROJECT_DIR / "dashboard" / "data.js"


# ---------------------------------------------------------------------------
# Empty state and schema helpers
# ---------------------------------------------------------------------------

def _empty_tracking() -> dict:
    return {
        "metadata": {"version": "3.0", "created": "", "last_updated": ""},
        "applications": [],
        "unlinked_outreach": [],
        "legacy_applications": [],
        "stats": {},
    }


def _normalize_schema(data: dict) -> dict:
    """Ensure every v3.0 key is present. Mutates and returns data."""
    data.setdefault("metadata", {})
    data["metadata"].setdefault("version", "3.0")
    data["metadata"].setdefault("created", "")
    data["metadata"].setdefault("last_updated", "")
    data.setdefault("applications", [])
    data.setdefault("unlinked_outreach", [])
    data.setdefault("legacy_applications", [])
    data.setdefault("stats", {})
    return data


def _is_empty_enough_to_migrate(data: dict) -> bool:
    """True if tracking has no real data yet — safe to merge legacy into it."""
    return (
        not data.get("applications")
        and not data.get("unlinked_outreach")
        and not data.get("legacy_applications")
    )


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def _today_str(today: Optional[str] = None) -> str:
    return today if today is not None else date.today().isoformat()


def _now_iso(now: Optional[datetime] = None) -> str:
    dt = now if now is not None else datetime.now(timezone.utc)
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load(
    path: Optional[Path] = None,
    template_path: Optional[Path] = None,
    legacy_path: Optional[Path] = None,
    auto_migrate: bool = True,
    log: bool = True,
) -> dict:
    """Load tracking.json, creating it from the template and optionally merging
    legacy outreach-history.json if tracking is empty.

    Args:
        path: Override TRACKING_FILE (useful for tests).
        template_path: Override TRACKING_TEMPLATE.
        legacy_path: Override LEGACY_FILE.
        auto_migrate: If True, merge legacy data into tracking when tracking
            is empty-ish and legacy has entries.
        log: Whether to print a one-line notice on auto-migration.

    Returns:
        A dict matching the v3.0 schema. Always has all top-level keys.
    """
    tracking_path = path or TRACKING_FILE
    tmpl_path = template_path or TRACKING_TEMPLATE
    legacy = legacy_path or LEGACY_FILE

    if tracking_path.exists():
        try:
            with open(tracking_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = _empty_tracking()
    elif tmpl_path.exists():
        try:
            with open(tmpl_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = _empty_tracking()
    else:
        data = _empty_tracking()

    data = _normalize_schema(data)

    if auto_migrate and _is_empty_enough_to_migrate(data) and legacy.exists():
        migrated = _merge_legacy(data, legacy)
        if migrated > 0 and log:
            print(f"  Migrated {migrated} legacy outreach entries from {legacy.name}.")

    return data


def save(
    data: dict,
    path: Optional[Path] = None,
    today: Optional[str] = None,
    regen_js: bool = True,
) -> None:
    """Persist tracking data. Recomputes stats and updates metadata.last_updated.

    Args:
        data: The tracking dict to save. Mutated in place (metadata + stats).
        path: Override TRACKING_FILE (useful for tests).
        today: 'YYYY-MM-DD' to inject a fixed date for the last_updated stamp.
        regen_js: Whether to regenerate dashboard/data.js. Disable in tests.
    """
    tracking_path = path or TRACKING_FILE

    _normalize_schema(data)
    data["metadata"]["last_updated"] = _today_str(today)
    recompute_stats(data)

    tracking_path.parent.mkdir(parents=True, exist_ok=True)
    with open(tracking_path, "w") as f:
        json.dump(data, f, indent=2)

    if regen_js:
        _regen_data_js_silently()


def _regen_data_js_silently() -> None:
    """Best-effort data.js regen. Never raises — the caller has already saved."""
    try:
        # Lazy import avoids a circular dep at module load time.
        import sys
        sys.path.insert(0, str(PROJECT_DIR / "scripts"))
        from generate_data_js import generate  # type: ignore
        generate()
    except Exception:
        # Dashboard regen is a nice-to-have; a save should never fail over it.
        pass


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def recompute_stats(data: dict) -> dict:
    """Compute the v3.0 stats block from current applications + outreach.

    Mutates data['stats'] in place and returns data.
    """
    all_outreach = list(_flat_outreach(data))
    positive = sum(
        1 for o in all_outreach if o.get("outcome") in ("accepted", "replied", "interview")
    )
    interviews = sum(1 for o in all_outreach if o.get("outcome") == "interview")
    data["stats"] = {
        "total_applications": len(data.get("applications", [])),
        "total_outreach_sent": len(all_outreach),
        "positive_outcomes": positive,
        "interviews_scheduled": interviews,
    }
    return data


def _flat_outreach(data: dict):
    """Yield every outreach dict in tracking, from apps and unlinked."""
    for app in data.get("applications", []):
        for o in app.get("outreach", []):
            yield o
    for o in data.get("unlinked_outreach", []):
        yield o


def iter_outreach(data: dict) -> Iterator[Tuple[dict, Optional[dict]]]:
    """Yield (outreach_entry, parent_application_or_None) pairs for every outreach.

    Parent is None for entries in unlinked_outreach.
    """
    for app in data.get("applications", []):
        for o in app.get("outreach", []):
            yield o, app
    for o in data.get("unlinked_outreach", []):
        yield o, None


# ---------------------------------------------------------------------------
# Lookups and mutation
# ---------------------------------------------------------------------------

def find_outreach(
    data: dict, name: str, company: str
) -> Tuple[Optional[dict], Optional[dict]]:
    """Case-insensitive lookup by (name, company).

    Returns (outreach_entry, parent_application_or_None), or (None, None).
    When a matching outreach exists in multiple places, returns the first.
    """
    name_lower = (name or "").lower()
    company_lower = (company or "").lower()

    for app in data.get("applications", []):
        if (app.get("company") or "").lower() != company_lower:
            continue
        for o in app.get("outreach", []):
            if (o.get("name") or "").lower() == name_lower:
                return o, app

    for o in data.get("unlinked_outreach", []):
        if (
            (o.get("name") or "").lower() == name_lower
            and (o.get("company") or "").lower() == company_lower
        ):
            return o, None

    return None, None


def find_or_create_application(
    data: dict,
    company: str,
    role: str,
    today: Optional[str] = None,
    now: Optional[datetime] = None,
    url: Optional[str] = None,
    source: str = "linkedin",
    company_size: str = "unknown",
    salary_range: Optional[str] = None,
    location: Optional[str] = None,
) -> dict:
    """Return an existing application matching (company, role) or create one.

    New applications start in status 'saved' with no applied date — only the
    dashboard's 'apply' action or an explicit caller sets that.
    """
    company_lower = (company or "").lower()
    role_lower = (role or "").lower()

    for app in data.get("applications", []):
        if (
            (app.get("company") or "").lower() == company_lower
            and (app.get("role") or "").lower() == role_lower
        ):
            return app

    today_str = _today_str(today)
    now_iso = _now_iso(now)
    slug = _slug(f"{company} {role}")

    new_app = {
        "id": f"{today_str}-{slug}",
        "company": company,
        "role": role,
        "url": url,
        "source": source,
        "company_size": company_size,
        "salary_range": salary_range,
        "location": location,
        "status": "saved",
        "dates": {
            "saved": today_str,
            "saved_at": now_iso,
            "applied": None,
            "applied_at": None,
            "rejected": None,
            "offer": None,
        },
        "cover_letter": None,
        "outreach": [],
        "notes": "",
    }
    data.setdefault("applications", []).append(new_app)
    return new_app


def build_outreach_entry(
    name: str,
    recipient_role: str,
    msg_type: str,
    message: str,
    today: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    variant: Optional[str] = None,
    context: str = "job_search",
    company: Optional[str] = None,
) -> dict:
    """Construct a v3.0 outreach dict. Caller attaches it to the right list."""
    today_str = _today_str(today)
    msg = message or ""
    slug = _slug(name)
    entry = {
        "id": f"outreach-{today_str}-{slug}",
        "name": name,
        "recipient_role": recipient_role,
        "linkedin_url": linkedin_url,
        "type": msg_type,
        "variant": variant,
        "message": msg,
        "message_length": len(msg),
        "context": context,
        "dates": {"sent": today_str, "accepted": None, "replied": None, "interview": None},
        "outcome": "pending",
        "response_time_days": None,
        "follow_ups": [],
    }
    if company is not None:
        entry["company"] = company
    return entry


def log_outreach(
    data: dict,
    name: str,
    company: str,
    recipient_role: str,
    msg_type: str,
    message: str,
    today: Optional[str] = None,
    now: Optional[datetime] = None,
    job_id: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    company_size: str = "unknown",
    role_for_application: Optional[str] = None,
    variant: Optional[str] = None,
    context: str = "job_search",
) -> Tuple[dict, Optional[dict]]:
    """Add a new outreach entry to tracking data.

    If an application matches by `job_id` (preferred) or by company + role
    (fallback), the outreach is nested under it. Otherwise it goes into
    `unlinked_outreach` with the company recorded on the entry itself.

    Returns (outreach_entry, parent_application_or_None).
    """
    parent_app = None

    if job_id:
        for app in data.get("applications", []):
            if app.get("id") == job_id:
                parent_app = app
                break

    if parent_app is None and role_for_application:
        company_lower = (company or "").lower()
        role_lower = role_for_application.lower()
        for app in data.get("applications", []):
            if (
                (app.get("company") or "").lower() == company_lower
                and (app.get("role") or "").lower() == role_lower
            ):
                parent_app = app
                break

    entry_company = None if parent_app is not None else company
    entry = build_outreach_entry(
        name=name,
        recipient_role=recipient_role,
        msg_type=msg_type,
        message=message,
        today=today,
        linkedin_url=linkedin_url,
        variant=variant,
        context=context,
        company=entry_company,
    )

    if parent_app is not None:
        parent_app.setdefault("outreach", []).append(entry)
    else:
        data.setdefault("unlinked_outreach", []).append(entry)

    return entry, parent_app


def update_outcome(
    data: dict,
    name: str,
    company: str,
    status: str,
    today: Optional[str] = None,
) -> bool:
    """Apply a status transition to an existing outreach entry.

    Valid statuses: sent, accepted, replied, interview, no_response, declined.
    Returns True if an entry was found and updated, False otherwise.
    """
    entry, _parent = find_outreach(data, name, company)
    if entry is None:
        return False

    today_str = _today_str(today)
    entry.setdefault("dates", {})

    if status == "sent":
        entry["dates"]["sent"] = today_str
        entry["outcome"] = entry.get("outcome", "pending")
    elif status == "accepted":
        entry["dates"]["accepted"] = today_str
        entry["outcome"] = "accepted"
        if entry["dates"].get("sent"):
            try:
                sent = datetime.fromisoformat(entry["dates"]["sent"])
                acc = datetime.fromisoformat(today_str)
                entry["response_time_days"] = (acc - sent).days
            except ValueError:
                pass
    elif status == "replied":
        entry["dates"]["replied"] = today_str
        entry["outcome"] = "replied"
    elif status == "interview":
        entry["dates"]["interview"] = today_str
        entry["outcome"] = "interview"
    elif status in ("declined", "no_response"):
        entry["outcome"] = status
    else:
        return False

    return True


# ---------------------------------------------------------------------------
# Legacy auto-migration
# ---------------------------------------------------------------------------

def _merge_legacy(data: dict, legacy_path: Path) -> int:
    """Merge data/outreach-history.json into tracking data, non-destructively.

    Legacy `connections` become entries in `unlinked_outreach` with the
    original message, company, and dates preserved. Legacy `applications`
    are stashed in `legacy_applications` for manual review.

    Returns the number of outreach entries migrated. The legacy file is
    not modified. Safe to re-run — existing ids are preserved.
    """
    try:
        with open(legacy_path) as f:
            legacy = json.load(f)
    except (json.JSONDecodeError, OSError):
        return 0

    existing_outreach_ids = {o.get("id") for o in data.get("unlinked_outreach", [])}
    migrated = 0

    for conn in legacy.get("connections", []):
        if conn.get("direction") and conn["direction"] != "OUTGOING":
            continue
        name = conn.get("name", "")
        company = conn.get("company", "")
        sent = conn.get("sent_date") or conn.get("date") or ""
        slug = _slug(f"{name} {company}")
        oid = f"outreach-legacy-{slug}"
        if oid in existing_outreach_ids:
            continue

        entry = {
            "id": oid,
            "name": name,
            "company": company,
            "recipient_role": conn.get("recipient_role") or conn.get("position") or "unknown",
            "linkedin_url": conn.get("linkedin_url"),
            "type": conn.get("type", "connection-request"),
            "variant": conn.get("variant"),
            "message": conn.get("message", ""),
            "message_length": len(conn.get("message", "")),
            "context": conn.get("context", "job_search"),
            "dates": {
                "sent": sent,
                "accepted": conn.get("accepted_date"),
                "replied": conn.get("replied_date"),
                "interview": conn.get("interview_date"),
            },
            "outcome": conn.get("outcome", "pending"),
            "response_time_days": conn.get("response_time_days"),
            "follow_ups": [],
            "company_size": conn.get("company_size", "unknown"),
            "job_id": conn.get("job_id"),
        }
        data.setdefault("unlinked_outreach", []).append(entry)
        existing_outreach_ids.add(oid)
        migrated += 1

    existing_legacy_ids = {a.get("id") for a in data.get("legacy_applications", [])}
    for app in legacy.get("applications", []):
        aid = (
            f"legacy-{_slug(app.get('company', ''))}-{_slug(app.get('title', app.get('role', '')))}"
        )
        if aid in existing_legacy_ids:
            continue
        data.setdefault("legacy_applications", []).append({"id": aid, **app})
        existing_legacy_ids.add(aid)

    return migrated
