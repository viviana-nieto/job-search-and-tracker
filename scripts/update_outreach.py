#!/usr/bin/env python3
"""Log outreach, update outcomes, and show stats for job search networking."""

import argparse
import json
import os
import sys
from datetime import date, datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(PROJECT_DIR, "data", "outreach-history.json")

# Import company classifier
sys.path.insert(0, os.path.join(PROJECT_DIR, "scripts"))
from company_classifier import classify


def load_history():
    with open(HISTORY_FILE) as f:
        return json.load(f)


def save_history(data):
    data["metadata"]["last_updated"] = date.today().isoformat()
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=2)


def log_outreach(name, company, recipient_role, msg_type, message,
                 job_id=None, linkedin_url=None, context="job_search"):
    """Log a new outreach entry."""
    history = load_history()
    company_size = classify(company)

    entry = {
        "name": name,
        "company": company,
        "position": recipient_role,
        "date": date.today().isoformat(),
        "direction": "OUTGOING",
        "message": message,
        "linkedin_url": linkedin_url,
        "context": context,
        "status": "pending",
        "type": msg_type,
        "job_id": job_id,
        "company_size": company_size,
        "recipient_role": recipient_role,
        "sent_date": None,
        "accepted_date": None,
        "replied_date": None,
        "interview_date": None,
        "outcome": "pending",
        "response_time_days": None
    }

    history["connections"].append(entry)
    history["stats"]["total_connections_sent"] = len([
        c for c in history["connections"] if c.get("direction") == "OUTGOING"
    ])
    save_history(history)

    print(f"Logged outreach to {name} at {company} ({msg_type}, {company_size})")
    if job_id:
        print(f"Linked to job: {job_id}")


def update_outcome(name, company, status, update_date=None):
    """Update the outcome of an existing outreach entry."""
    history = load_history()
    update_date = update_date or date.today().isoformat()

    found = False
    for entry in history["connections"]:
        if (entry["name"].lower() == name.lower() and
                entry.get("company", "").lower() == company.lower()):
            found = True

            if status == "sent":
                entry["sent_date"] = update_date
                entry["status"] = "pending"
            elif status == "accepted":
                entry["accepted_date"] = update_date
                entry["status"] = "connected"
                entry["outcome"] = "accepted"
                if entry.get("sent_date"):
                    sent = datetime.fromisoformat(entry["sent_date"])
                    accepted = datetime.fromisoformat(update_date)
                    entry["response_time_days"] = (accepted - sent).days
            elif status == "replied":
                entry["replied_date"] = update_date
                entry["status"] = "connected"
                entry["outcome"] = "replied"
            elif status == "interview":
                entry["interview_date"] = update_date
                entry["outcome"] = "interview"
            elif status == "no_response":
                entry["outcome"] = "no_response"
            elif status == "declined":
                entry["status"] = "declined"
                entry["outcome"] = "declined"

            print(f"Updated {name} at {company}: {status} ({update_date})")
            break

    if not found:
        print(f"Error: No outreach found for {name} at {company}", file=sys.stderr)
        sys.exit(1)

    # Update stats
    outcomes = [c.get("outcome") for c in history["connections"]]
    history["stats"]["responses_received"] = sum(1 for o in outcomes if o in ("replied", "interview"))
    history["stats"]["interviews_scheduled"] = sum(1 for o in outcomes if o == "interview")

    save_history(history)


def show_stats():
    """Display outreach statistics and performance breakdown."""
    history = load_history()
    connections = history["connections"]

    total = len([c for c in connections if c.get("direction") == "OUTGOING"])
    print(f"\n=== Outreach Stats ===\n")
    print(f"Total outreach sent: {total}")
    print(f"Applications: {len(history.get('applications', []))}")
    print()

    # Outcome breakdown
    outcomes = {}
    for c in connections:
        outcome = c.get("outcome", c.get("status", "unknown"))
        outcomes[outcome] = outcomes.get(outcome, 0) + 1

    if outcomes:
        print("Outcomes:")
        for outcome, count in sorted(outcomes.items(), key=lambda x: -x[1]):
            pct = (count / total * 100) if total > 0 else 0
            print(f"  {outcome:<15} {count:>3}  ({pct:.0f}%)")

    # By message type
    by_type = {}
    for c in connections:
        t = c.get("type", "unknown")
        by_type.setdefault(t, {"total": 0, "responded": 0})
        by_type[t]["total"] += 1
        if c.get("outcome") in ("replied", "interview", "accepted"):
            by_type[t]["responded"] += 1

    if any(v["total"] > 0 for v in by_type.values() if v.get("total")):
        print("\nBy Message Type:")
        for t, v in sorted(by_type.items()):
            rate = (v["responded"] / v["total"] * 100) if v["total"] > 0 else 0
            print(f"  {t:<25} {v['responded']}/{v['total']}  ({rate:.0f}% response)")

    # By company size
    by_size = {}
    for c in connections:
        s = c.get("company_size", "unknown")
        by_size.setdefault(s, {"total": 0, "responded": 0})
        by_size[s]["total"] += 1
        if c.get("outcome") in ("replied", "interview", "accepted"):
            by_size[s]["responded"] += 1

    if any(v["total"] > 0 for v in by_size.values()):
        print("\nBy Company Size:")
        for s, v in sorted(by_size.items()):
            rate = (v["responded"] / v["total"] * 100) if v["total"] > 0 else 0
            print(f"  {s:<15} {v['responded']}/{v['total']}  ({rate:.0f}% response)")

    # By recipient role
    by_role = {}
    for c in connections:
        r = c.get("recipient_role", "unknown")
        by_role.setdefault(r, {"total": 0, "responded": 0})
        by_role[r]["total"] += 1
        if c.get("outcome") in ("replied", "interview", "accepted"):
            by_role[r]["responded"] += 1

    if any(v["total"] > 0 for v in by_role.values()):
        print("\nBy Recipient Role:")
        for r, v in sorted(by_role.items()):
            rate = (v["responded"] / v["total"] * 100) if v["total"] > 0 else 0
            print(f"  {r:<25} {v['responded']}/{v['total']}  ({rate:.0f}% response)")

    # Average response time
    times = [c["response_time_days"] for c in connections
             if c.get("response_time_days") is not None]
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
