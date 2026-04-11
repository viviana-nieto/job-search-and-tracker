"""
Job Fetcher - JSearch via RapidAPI

Searches across LinkedIn, Indeed, Glassdoor, and ZipRecruiter.
Free tier: 200 requests/month.

Setup:
  Create free RapidAPI account, subscribe to JSearch, set RAPIDAPI_KEY

Usage:
    python fetch_jobs.py                          # Default search
    python fetch_jobs.py --keywords "PM AI"       # Custom keywords
    python fetch_jobs.py --locations "New York"   # Custom locations
"""

import os
import json
import re
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("Please install requests: pip install requests")
    exit(1)

# Load defaults from config if available
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from config_loader import get_default_keywords, get_default_locations, is_configured
    if is_configured():
        DEFAULT_KEYWORDS = get_default_keywords()
        DEFAULT_LOCATIONS = get_default_locations()
    else:
        DEFAULT_KEYWORDS = ["Product Manager", "Software Engineer"]
        DEFAULT_LOCATIONS = ["San Francisco Bay Area", "Remote"]
except ImportError:
    DEFAULT_KEYWORDS = ["Product Manager", "Software Engineer"]
    DEFAULT_LOCATIONS = ["San Francisco Bay Area", "Remote"]

# Configuration
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")

DEFAULT_LOCATION = DEFAULT_LOCATIONS[0] if DEFAULT_LOCATIONS else "San Francisco Bay Area"

# Output directory
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data" / "jobs"


# --- Salary Extraction ---

def _extract_salary(description: str) -> str:
    """Extract salary range from job description text."""
    patterns = [
        r'\$[\d,.]+[Kk]?\s*[-\u2013\u2014to]+\s*\$[\d,.]+[Kk]?(?:\s*(?:per year|annually|/yr|a year|/year))?',
        r'(?:base salary|salary range|compensation range|total.*?compensation)[:\s]*\$[\d,.]+[Kk]?\s*[-\u2013\u2014to]+\s*\$[\d,.]+[Kk]?',
        r'\$[\d,.]+\s*[-\u2013\u2014]\s*\$[\d,.]+\s*(?:per year|annually|/yr|a year)',
        r'(?:hourly rate)[:\s]*\$[\d,.]+\s*[-\u2013\u2014to]+\s*\$[\d,.]+\s*per hour',
    ]
    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return ""


# --- JSearch (RapidAPI) ---

def fetch_jsearch(keywords: list[str], locations: list[str] = None, max_jobs: int = 100):
    """
    Fetch jobs via JSearch on RapidAPI.
    Searches across LinkedIn, Indeed, Glassdoor, ZipRecruiter.
    Free tier: 500 requests/month.
    """
    if not RAPIDAPI_KEY:
        print("Error: Please set your RAPIDAPI_KEY environment variable")
        print("Get your key at: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch")
        return []

    if locations is None:
        locations = [DEFAULT_LOCATION, "Remote"]

    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
    }

    all_jobs = []
    requests_used = 0

    for keyword in keywords:
        for location in locations:
            query = f"{keyword} in {location}"
            print(f"Searching: {query}")

            params = {
                "query": query,
                "page": "1",
                "num_pages": "1",
                "date_posted": "week",
                "country": "us",
            }

            if "remote" in location.lower():
                params["remote_jobs_only"] = "true"
                params["query"] = keyword

            try:
                response = requests.get(
                    "https://jsearch.p.rapidapi.com/search",
                    headers=headers,
                    params=params,
                    timeout=30,
                )
                requests_used += 1

                if response.status_code == 200:
                    data = response.json()
                    jobs = data.get("data", [])
                    print(f"  Found {len(jobs)} jobs")
                    all_jobs.extend(jobs)
                elif response.status_code == 429:
                    print("  Rate limited. Waiting 2 seconds...")
                    time.sleep(2)
                else:
                    print(f"  Error: {response.status_code} - {response.text[:200]}")

            except requests.exceptions.Timeout:
                print(f"  Timeout for: {query}")
            except Exception as e:
                print(f"  Error: {e}")

    print(f"\nJSearch requests used: {requests_used} (of 500/month free)")
    return all_jobs


def normalize_jsearch(jobs: list) -> list:
    """Normalize JSearch results to our standard format."""
    normalized = []
    seen_ids = set()

    for job in jobs:
        job_id = job.get("job_id", "")
        if job_id in seen_ids:
            continue
        seen_ids.add(job_id)

        desc = job.get("job_description", "")
        salary_min = job.get("job_min_salary")
        salary_max = job.get("job_max_salary")
        salary_period = job.get("job_salary_period", "")

        salary = ""
        if salary_min and salary_max:
            salary = f"${salary_min:,.0f} - ${salary_max:,.0f}"
            if salary_period:
                salary += f" {salary_period}"
        elif not salary and desc:
            salary = _extract_salary(desc)

        city = job.get("job_city", "")
        state = job.get("job_state", "")
        location = f"{city}, {state}" if city and state else city or state or ""
        if job.get("job_is_remote"):
            location = f"{location} (Remote)" if location else "Remote"

        normalized.append({
            "id": job_id,
            "title": job.get("job_title", ""),
            "company": job.get("employer_name", ""),
            "location": location,
            "description": desc,
            "url": job.get("job_apply_link", job.get("job_google_link", "")),
            "posted_date": job.get("job_posted_at_datetime_utc", ""),
            "salary": salary,
            "employment_type": job.get("job_employment_type", ""),
            "seniority_level": "",
            "industries": [],
            "job_functions": [],
            "applicants": "",
            "fetched_at": datetime.now().isoformat(),
            "source": "jsearch",
            "employer_logo": job.get("employer_logo", ""),
            "job_apply_link": job.get("job_apply_link", ""),
        })

    return normalized


# --- Save ---

ALL_JOBS_FILE = DATA_DIR / "all-jobs.json"


def save_jobs(normalized_jobs: list, filename: str = None, source: str = "jsearch"):
    """Save normalized jobs to both a dated file and the master all-jobs.json repository."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")

    for job in normalized_jobs:
        if not job.get("fetch_date"):
            job["fetch_date"] = today

    if filename is None:
        filename = f"{today}-{source}.json"
    filepath = DATA_DIR / filename
    with open(filepath, "w") as f:
        json.dump(normalized_jobs, f, indent=2)
    print(f"\nSaved {len(normalized_jobs)} jobs to {filepath}")

    existing = []
    if ALL_JOBS_FILE.exists():
        with open(ALL_JOBS_FILE) as f:
            existing = json.load(f)

    existing_keys = set()
    for job in existing:
        key = _dedup_key(job)
        existing_keys.add(key)

    new_count = 0
    for job in normalized_jobs:
        key = _dedup_key(job)
        if key not in existing_keys:
            existing.append(job)
            existing_keys.add(key)
            new_count += 1

    with open(ALL_JOBS_FILE, "w") as f:
        json.dump(existing, f, indent=2)

    print(f"Master repository: {len(existing)} total jobs ({new_count} new, {len(normalized_jobs) - new_count} duplicates skipped)")
    print(f"Repository: {ALL_JOBS_FILE}")
    return filepath


def _dedup_key(job):
    """Generate a dedup key from title + company (case-insensitive)."""
    title = job.get("title", "").lower().strip()
    company = job.get("company", "").lower().strip()
    return f"{company}|||{title}"


# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="Fetch jobs via JSearch (RapidAPI)")
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=DEFAULT_KEYWORDS,
        help="Search keywords",
    )
    parser.add_argument(
        "--locations",
        nargs="+",
        default=None,
        help="Job locations (default from config or Bay Area + Remote)",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=100,
        help="Max jobs per keyword (default: 100)",
    )
    parser.add_argument(
        "--output",
        help="Output filename",
    )

    args = parser.parse_args()
    locations = args.locations or [DEFAULT_LOCATION, "Remote"]

    print("Job Fetcher (JSEARCH)")
    print("=" * 50)
    print(f"Keywords: {args.keywords}")
    print(f"Locations: {locations}")
    print(f"Max jobs per keyword: {args.max_jobs}")

    requests_estimate = len(args.keywords) * len(locations)
    print(f"Estimated requests: {requests_estimate} (of 200/month free)")

    print("=" * 50)

    raw_jobs = fetch_jsearch(args.keywords, locations, args.max_jobs)
    normalized = normalize_jsearch(raw_jobs)

    if normalized:
        save_jobs(normalized, args.output, "jsearch")
        print(f"\nTotal unique jobs: {len(normalized)}")
    else:
        print("\nNo jobs found. Check your API key and search parameters.")
        return

    # Chain: refresh connection matches if the user has provided connections.
    connections_file = SCRIPT_DIR.parent / "data" / "connections.csv"
    if connections_file.exists():
        print("\nRefreshing connection matches...")
        try:
            from match_connections import match_all
            match_all()
        except Exception as e:
            print(f"  (warning: connection matching failed: {e})")

    # Regenerate dashboard data.js so new jobs appear immediately
    try:
        from generate_data_js import generate
        jobs_count, apps_count = generate()
        print(f"\nDashboard updated: {jobs_count} jobs, {apps_count} applications")
    except Exception as e:
        print(f"  (warning: dashboard data regeneration failed: {e})")


if __name__ == "__main__":
    main()
