#!/usr/bin/env python3
"""Match LinkedIn connections to fetched jobs.

Reads data/connections.csv and data/jobs/all-jobs.json, produces
data/connection-matches.json. Match tiers:
  DIRECT  — connection works at the same company as the job
"""

import csv
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
CONNECTIONS_FILE = PROJECT_DIR / "data" / "connections.csv"
ALL_JOBS_FILE = PROJECT_DIR / "data" / "jobs" / "all-jobs.json"
MATCHES_FILE = PROJECT_DIR / "data" / "connection-matches.json"
OVERRIDES_FILE = PROJECT_DIR / "data" / "match-overrides.json"

ROLE_KEYWORDS = [
    "product manager", "product lead", "head of product", "vp of product",
    "director of product", "pm ", "product management",
    "machine learning", "ml ", "ai ", "artificial intelligence",
    "data scientist", "data engineer", "data analyst",
    "recruiter", "talent", "hiring",
    "software engineer", "staff engineer", "principal engineer",
]


def load_connections():
    """Load LinkedIn connections CSV.

    LinkedIn's export has a few preamble lines before the header row. We try
    DictReader first (works when the CSV starts with the header, which is our
    shipped template format) and fall back to skipping up to 3 preamble lines
    (the raw LinkedIn export format).
    """
    if not CONNECTIONS_FILE.exists():
        return []

    # Detect whether the first row is the header
    with open(CONNECTIONS_FILE, newline="", encoding="utf-8") as f:
        first_line = f.readline()
    first_lower = first_line.lower()
    needs_skip = not ("first name" in first_lower and "last name" in first_lower)

    connections = []
    with open(CONNECTIONS_FILE, newline="", encoding="utf-8") as f:
        if needs_skip:
            # LinkedIn's raw export has 3 preamble lines before the header
            for _ in range(3):
                next(f, None)
        reader = csv.DictReader(f)
        for row in reader:
            name = f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip()
            if not name:
                continue
            connections.append({
                "name": name,
                "company": (row.get("Company") or "").strip(),
                "position": (row.get("Position") or "").strip(),
                "linkedin_url": (row.get("URL") or "").strip(),
                "email": (row.get("Email Address") or "").strip(),
            })
    return connections


def load_jobs():
    if not ALL_JOBS_FILE.exists():
        return []
    with open(ALL_JOBS_FILE) as f:
        return json.load(f)


def normalize(text):
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def companies_match(conn_company, job_company):
    """Match company names with word-boundary containment to avoid false positives."""
    c = normalize(conn_company)
    j = normalize(job_company)
    if not c or not j:
        return False
    if c == j:
        return True
    c_words = c.split()
    j_words = j.split()
    if len(c_words) <= len(j_words) and c_words == j_words[:len(c_words)]:
        return True
    if len(j_words) <= len(c_words) and j_words == c_words[:len(j_words)]:
        return True
    c_first = c_words[0] if c_words else ""
    j_first = j_words[0] if j_words else ""
    if len(c_first) >= 6 and c_first == j_first:
        return True
    return False


def is_relevant_role(position):
    pos = position.lower()
    return any(k in pos for k in ROLE_KEYWORDS)


def match_all(quiet=False):
    connections = load_connections()
    jobs = load_jobs()

    if not connections:
        if not quiet:
            print("  No connections found. Skipping match. Run setup with")
            print("  --connections to import your LinkedIn export.")
        return None
    if not jobs:
        if not quiet:
            print("  No jobs found. Skipping match. Run fetch first.")
        return None

    if not quiet:
        print(f"  Matching {len(connections)} connections against {len(jobs)} jobs...")

    conn_by_company = {}
    for c in connections:
        if c["company"]:
            norm = normalize(c["company"])
            conn_by_company.setdefault(norm, []).append(c)

    matches = {}
    for job in jobs:
        job_company = job.get("company", "")
        job_title = job.get("title", "")
        key = f"{job_company}|||{job_title}"
        job_matches = []

        for norm_company, conns in conn_by_company.items():
            if companies_match(norm_company, job_company):
                for c in conns:
                    job_matches.append({
                        "name": c["name"],
                        "company": c["company"],
                        "position": c["position"],
                        "linkedin_url": c["linkedin_url"],
                        "email": c["email"],
                        "match_type": "DIRECT",
                        "score": 100,
                    })

        if job_matches:
            job_matches.sort(key=lambda m: (
                0 if is_relevant_role(m["position"]) else 1,
                m["name"],
            ))
            matches[key] = job_matches

    # Apply overrides if present
    overrides = {}
    if OVERRIDES_FILE.exists():
        try:
            with open(OVERRIDES_FILE) as f:
                overrides = json.load(f)
        except (json.JSONDecodeError, OSError):
            overrides = {}

    for exc in overrides.get("exclude", []):
        exc_name = exc.get("connection", "").lower()
        exc_company = normalize(exc.get("company", ""))
        for key, conns in list(matches.items()):
            matches[key] = [
                m for m in conns
                if not (m["name"].lower() == exc_name and normalize(m["company"]) == exc_company)
            ]
            if not matches[key]:
                del matches[key]

    for add in overrides.get("add", []):
        add_company = add.get("company", "")
        for job in jobs:
            if companies_match(normalize(add_company), job.get("company", "")):
                key = f"{job['company']}|||{job.get('title', '')}"
                entry = {
                    "name": add.get("name", ""),
                    "company": add_company,
                    "position": add.get("position", ""),
                    "linkedin_url": add.get("linkedin_url", ""),
                    "email": add.get("email", ""),
                    "match_type": add.get("match_type", "MANUAL"),
                    "context": add.get("context", ""),
                    "score": 90,
                }
                existing = matches.get(key, [])
                if not any(m["name"].lower() == entry["name"].lower() for m in existing):
                    matches.setdefault(key, []).append(entry)

    jobs_with_matches = len(matches)
    direct_count = sum(len(v) for v in matches.values())

    if not quiet:
        print(f"  Total matches: {direct_count} connections across {jobs_with_matches} jobs")

    result = {
        "last_updated": date.today().isoformat(),
        "total_connections": len(connections),
        "total_jobs": len(jobs),
        "jobs_with_direct_matches": jobs_with_matches,
        "total_direct_matches": direct_count,
        "matches": matches,
    }

    MATCHES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MATCHES_FILE, "w") as f:
        json.dump(result, f, indent=2)

    if not quiet:
        print(f"  Saved to {MATCHES_FILE}")

    # Regenerate data.js so the dashboard picks up new matches
    try:
        sys.path.insert(0, str(PROJECT_DIR / "scripts"))
        from generate_data_js import generate
        generate()
    except Exception:
        pass

    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Match connections to jobs")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")
    args = parser.parse_args()
    match_all(quiet=args.quiet)


if __name__ == "__main__":
    main()
