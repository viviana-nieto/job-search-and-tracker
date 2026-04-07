#!/usr/bin/env python3
"""Save a job posting as structured JSON for tracking and linking to outreach."""

import argparse
import json
import os
import re
import sys
from datetime import date

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS_DIR = os.path.join(PROJECT_DIR, "data", "jobs")


def slugify(text):
    """Convert text to URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


def make_job_id(company, role, date_str=None):
    """Generate a job ID like 2026-04-06-plaid-product-manager."""
    if date_str is None:
        date_str = date.today().isoformat()
    return f"{date_str}-{slugify(company)}-{slugify(role)}"


def save_job(company, role, url=None, salary=None, location=None,
             description=None, description_file=None, source="linkedin",
             date_applied=None, status="applied"):
    """Save a job posting to data/jobs/ as JSON."""
    os.makedirs(JOBS_DIR, exist_ok=True)

    today = date.today().isoformat()
    job_id = make_job_id(company, role, today)
    filepath = os.path.join(JOBS_DIR, f"{job_id}.json")

    # Load description from file if provided
    desc_text = description or ""
    if description_file and os.path.exists(description_file):
        with open(description_file) as f:
            desc_text = f.read()

    job = {
        "id": job_id,
        "company": company,
        "role": role,
        "url": url,
        "salary_range": salary,
        "location": location,
        "description": desc_text,
        "date_saved": today,
        "date_applied": date_applied or today,
        "source": source,
        "status": status,
        "outreach": [],
        "cover_letter": None
    }

    # Check for existing file to preserve outreach links
    if os.path.exists(filepath):
        with open(filepath) as f:
            existing = json.load(f)
        job["outreach"] = existing.get("outreach", [])
        job["cover_letter"] = existing.get("cover_letter")
        print(f"Updated existing job: {filepath}")
    else:
        print(f"Created new job: {filepath}")

    with open(filepath, "w") as f:
        json.dump(job, f, indent=2)

    return job_id, filepath


def link_outreach(job_id, outreach_id):
    """Add an outreach entry ID to a job's outreach list."""
    filepath = os.path.join(JOBS_DIR, f"{job_id}.json")
    if not os.path.exists(filepath):
        print(f"Error: Job file not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    with open(filepath) as f:
        job = json.load(f)

    if outreach_id not in job.get("outreach", []):
        job.setdefault("outreach", []).append(outreach_id)
        with open(filepath, "w") as f:
            json.dump(job, f, indent=2)
        print(f"Linked outreach '{outreach_id}' to job '{job_id}'")
    else:
        print(f"Outreach '{outreach_id}' already linked to job '{job_id}'")


def link_cover_letter(job_id, cover_letter_path):
    """Set the cover letter path for a job."""
    filepath = os.path.join(JOBS_DIR, f"{job_id}.json")
    if not os.path.exists(filepath):
        print(f"Error: Job file not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    with open(filepath) as f:
        job = json.load(f)

    job["cover_letter"] = cover_letter_path
    with open(filepath, "w") as f:
        json.dump(job, f, indent=2)
    print(f"Linked cover letter to job '{job_id}'")


def list_jobs():
    """List all saved jobs."""
    if not os.path.exists(JOBS_DIR):
        print("No jobs saved yet.")
        return

    jobs = []
    for f in sorted(os.listdir(JOBS_DIR)):
        if f.endswith(".json") and not f.startswith("sample"):
            filepath = os.path.join(JOBS_DIR, f)
            with open(filepath) as fh:
                data = json.load(fh)
                # Skip array-format files (bulk exports)
                if isinstance(data, list):
                    continue
                if "id" in data:
                    jobs.append(data)

    if not jobs:
        print("No jobs saved yet.")
        return

    print(f"{'ID':<45} {'Company':<20} {'Role':<30} {'Status':<10}")
    print("-" * 105)
    for job in jobs:
        print(f"{job['id']:<45} {job['company']:<20} {job['role']:<30} {job.get('status', 'unknown'):<10}")


def main():
    parser = argparse.ArgumentParser(description="Save and manage job postings")
    sub = parser.add_subparsers(dest="command", help="Command")

    # Save command
    save_p = sub.add_parser("save", help="Save a new job posting")
    save_p.add_argument("--company", required=True)
    save_p.add_argument("--role", required=True)
    save_p.add_argument("--url", default=None)
    save_p.add_argument("--salary", default=None)
    save_p.add_argument("--location", default=None)
    save_p.add_argument("--description", default=None, help="Job description text")
    save_p.add_argument("--description-file", default=None, help="File with job description")
    save_p.add_argument("--source", default="linkedin")
    save_p.add_argument("--date-applied", default=None)
    save_p.add_argument("--status", default="applied")

    # Link commands
    link_p = sub.add_parser("link-outreach", help="Link outreach to a job")
    link_p.add_argument("--job-id", required=True)
    link_p.add_argument("--outreach-id", required=True)

    cl_p = sub.add_parser("link-cover-letter", help="Link cover letter to a job")
    cl_p.add_argument("--job-id", required=True)
    cl_p.add_argument("--path", required=True)

    # List command
    sub.add_parser("list", help="List all saved jobs")

    args = parser.parse_args()

    if args.command == "save":
        job_id, filepath = save_job(
            company=args.company, role=args.role, url=args.url,
            salary=args.salary, location=args.location,
            description=args.description, description_file=args.description_file,
            source=args.source, date_applied=args.date_applied, status=args.status
        )
        print(f"Job ID: {job_id}")
    elif args.command == "link-outreach":
        link_outreach(args.job_id, args.outreach_id)
    elif args.command == "link-cover-letter":
        link_cover_letter(args.job_id, args.path)
    elif args.command == "list":
        list_jobs()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
