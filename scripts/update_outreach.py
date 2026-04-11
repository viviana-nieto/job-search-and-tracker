#!/usr/bin/env python3
"""Log outreach, update outcomes, and show stats for job search networking.

Thin CLI wrapper around scripts/tracking.py — the v3.0 tracking module is the
single source of truth for reading and writing data/tracking.json.
"""

import argparse
import os
import sys
from datetime import date

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Same-directory imports (matches the existing pattern for company_classifier).
sys.path.insert(0, os.path.join(PROJECT_DIR, "scripts"))
import tracking  # noqa: E402
from company_classifier import classify  # noqa: E402


def log_outreach(name, company, recipient_role, msg_type, message,
                 job_id=None, linkedin_url=None, context="job_search"):
    """Log a new outreach entry via the tracking module."""
    data = tracking.load()
    company_size = classify(company)

    tracking.log_outreach(
        data,
        name=name,
        company=company,
        recipient_role=recipient_role,
        msg_type=msg_type,
        message=message,
        job_id=job_id,
        linkedin_url=linkedin_url,
        company_size=company_size,
        role_for_application=None,
        context=context,
    )
    tracking.save(data)

    print(f"Logged outreach to {name} at {company} ({msg_type}, {company_size})")
    if job_id:
        print(f"Linked to job: {job_id}")


def update_outcome(name, company, status, update_date=None):
    """Update the outcome of an existing outreach entry via the tracking module."""
    data = tracking.load()
    update_date = update_date or date.today().isoformat()

    ok = tracking.update_outcome(data, name, company, status, today=update_date)
    if not ok:
        print(f"Error: No outreach found for {name} at {company}", file=sys.stderr)
        sys.exit(1)

    tracking.save(data)
    print(f"Updated {name} at {company}: {status} ({update_date})")


def show_stats():
    """Display outreach statistics and performance breakdown."""
    data = tracking.load()

    # Flatten every outreach entry (nested under applications + unlinked).
    entries = [entry for entry, _parent in tracking.iter_outreach(data)]

    total = len(entries)
    print(f"\n=== Outreach Stats ===\n")
    print(f"Total outreach sent: {total}")
    print(f"Applications: {len(data.get('applications', []))}")
    print()

    # Outcome breakdown
    outcomes = {}
    for entry in entries:
        outcome = entry.get("outcome", "unknown")
        outcomes[outcome] = outcomes.get(outcome, 0) + 1

    if outcomes:
        print("Outcomes:")
        for outcome, count in sorted(outcomes.items(), key=lambda x: -x[1]):
            pct = (count / total * 100) if total > 0 else 0
            print(f"  {outcome:<15} {count:>3}  ({pct:.0f}%)")

    # By message type
    by_type = {}
    for entry in entries:
        t = entry.get("type", "unknown")
        by_type.setdefault(t, {"total": 0, "responded": 0})
        by_type[t]["total"] += 1
        if entry.get("outcome") in ("replied", "interview", "accepted"):
            by_type[t]["responded"] += 1

    if any(v["total"] > 0 for v in by_type.values() if v.get("total")):
        print("\nBy Message Type:")
        for t, v in sorted(by_type.items()):
            rate = (v["responded"] / v["total"] * 100) if v["total"] > 0 else 0
            print(f"  {t:<25} {v['responded']}/{v['total']}  ({rate:.0f}% response)")

    # By company size
    by_size = {}
    for entry in entries:
        s = entry.get("company_size", "unknown")
        by_size.setdefault(s, {"total": 0, "responded": 0})
        by_size[s]["total"] += 1
        if entry.get("outcome") in ("replied", "interview", "accepted"):
            by_size[s]["responded"] += 1

    if any(v["total"] > 0 for v in by_size.values()):
        print("\nBy Company Size:")
        for s, v in sorted(by_size.items()):
            rate = (v["responded"] / v["total"] * 100) if v["total"] > 0 else 0
            print(f"  {s:<15} {v['responded']}/{v['total']}  ({rate:.0f}% response)")

    # By recipient role
    by_role = {}
    for entry in entries:
        r = entry.get("recipient_role", "unknown")
        by_role.setdefault(r, {"total": 0, "responded": 0})
        by_role[r]["total"] += 1
        if entry.get("outcome") in ("replied", "interview", "accepted"):
            by_role[r]["responded"] += 1

    if any(v["total"] > 0 for v in by_role.values()):
        print("\nBy Recipient Role:")
        for r, v in sorted(by_role.items()):
            rate = (v["responded"] / v["total"] * 100) if v["total"] > 0 else 0
            print(f"  {r:<25} {v['responded']}/{v['total']}  ({rate:.0f}% response)")

    # Average response time
    times = [entry["response_time_days"] for entry in entries
             if entry.get("response_time_days") is not None]
    if times:
        print(f"\nAvg response time: {sum(times)/len(times):.1f} days")

    print()


def main():
    parser = argparse.ArgumentParser(description="Track job search outreach")
    sub = parser.add_subparsers(dest="command")

    # Log
    log_p = sub.add_parser("log", help="Log new outreach")
    log_p.add_argument("--name", required=True)
    log_p.add_argument("--company", required=True)
    log_p.add_argument("--role", required=True,
                       choices=["recruiter", "hiring-manager", "executive", "peer", "ceo"],
                       help="Recipient's role type")
    log_p.add_argument("--type", required=True, dest="msg_type",
                       choices=["connection-request", "inmail", "linkedin-message", "email"])
    log_p.add_argument("--message", required=True, help="Message text")
    log_p.add_argument("--job-id", default=None, help="Linked job ID")
    log_p.add_argument("--url", default=None, help="LinkedIn profile URL")
    log_p.add_argument("--context", default="job_search")

    # Update
    upd_p = sub.add_parser("update", help="Update outreach outcome")
    upd_p.add_argument("--name", required=True)
    upd_p.add_argument("--company", required=True)
    upd_p.add_argument("--status", required=True,
                       choices=["sent", "accepted", "replied", "interview", "no_response", "declined"])
    upd_p.add_argument("--date", default=None, help="Date of update (YYYY-MM-DD)")

    # Stats
    sub.add_parser("stats", help="Show outreach statistics")

    args = parser.parse_args()

    if args.command == "log":
        log_outreach(
            name=args.name, company=args.company, recipient_role=args.role,
            msg_type=args.msg_type, message=args.message,
            job_id=args.job_id, linkedin_url=args.url, context=args.context
        )
    elif args.command == "update":
        update_outcome(args.name, args.company, args.status, args.date)
    elif args.command == "stats":
        show_stats()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
