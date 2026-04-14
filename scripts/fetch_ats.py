#!/usr/bin/env python3
"""Fetch jobs directly from ATS APIs (Greenhouse, Lever, Ashby).

Free, no API key required. Uses company career page public APIs. Pulls open
roles at companies listed in data/company-ats.json, filtered by the user's
configured target roles and preferred locations.

Usage:
    python scripts/fetch_ats.py                      # fetch all configured companies
    python scripts/fetch_ats.py --company "Stripe"   # single company
    python scripts/fetch_ats.py --probe "New Corp"   # auto-detect ATS, cache result
    python scripts/fetch_ats.py --dry-run             # preview, no API calls
"""

import argparse
import html
import json
import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("fetch_ats.py requires the 'requests' package.")
    print("Install with: pip install -r requirements.txt")
    sys.exit(1)

PROJECT_DIR = Path(__file__).parent.parent
COMPANY_ATS_FILE = PROJECT_DIR / "data" / "company-ats.json"
ALL_JOBS_FILE = PROJECT_DIR / "data" / "jobs" / "all-jobs.json"

# Default role keywords (used when config/search-criteria.json is absent)
DEFAULT_ROLE_KEYWORDS = [
    "product manager", "product lead", "head of product",
    "vp of product", "vp product", "director of product",
    "principal product", "staff product", "senior product",
    "lead product", "program manager", "technical program manager",
    "product owner", "chief product", "software engineer",
    "staff engineer", "senior engineer",
]

# ATS slugs known to have broken deep links
BROKEN_ATS_SLUGS = {
    "greenhouse": {"googlefiber"},
    "lever": set(),
    "ashby": set(),
}


# ---------------------------------------------------------------------------
# Config readers
# ---------------------------------------------------------------------------

def _load_role_keywords():
    """Read target role titles from config/search-criteria.json if available."""
    cfg_path = PROJECT_DIR / "config" / "search-criteria.json"
    if cfg_path.exists():
        try:
            with open(cfg_path) as f:
                cfg = json.load(f)
            targets = cfg.get("roles", {}).get("target", [])
            if targets:
                return [t.lower() for t in targets]
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_ROLE_KEYWORDS


def _load_preferred_locations():
    """Read preferred + acceptable locations from config/search-criteria.json."""
    cfg_path = PROJECT_DIR / "config" / "search-criteria.json"
    if cfg_path.exists():
        try:
            with open(cfg_path) as f:
                cfg = json.load(f)
            locs = cfg.get("locations", {})
            preferred = locs.get("preferred", [])
            acceptable = locs.get("acceptable", [])
            all_locs = [l.lower() for l in preferred + acceptable]
            if all_locs:
                return all_locs
        except (json.JSONDecodeError, OSError):
            pass
    return None  # None means "accept all locations"


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

def _strip_html(text):
    """Remove HTML tags for plaintext fallback."""
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _is_relevant_title(title, keywords=None):
    """Check if job title matches any of the configured keywords."""
    t = (title or "").lower()
    kw = keywords if keywords else _load_role_keywords()
    return any(k in t for k in kw)


def _is_relevant_location(location, is_remote=False, preferred_locations=None):
    """Check if job location is acceptable based on user's preferences.

    If no preferred_locations are configured, accept all locations.
    If preferred_locations exist, keep jobs that match any of them (or are Remote).
    """
    if is_remote:
        return True
    loc = (location or "").lower()
    if not loc:
        return True  # unknown location, keep it

    # Always keep remote/distributed
    if any(k in loc for k in ["remote", "anywhere", "distributed"]):
        return True

    # If no preferences configured, accept everything
    if preferred_locations is None:
        return True

    # Check if any preferred location appears in the job's location string
    return any(pref in loc for pref in preferred_locations)


# ---------------------------------------------------------------------------
# ATS fetchers
# ---------------------------------------------------------------------------

def fetch_greenhouse(slug, company_name, keywords=None, preferred_locations=None):
    """Fetch jobs from Greenhouse public board API."""
    if slug in BROKEN_ATS_SLUGS["greenhouse"]:
        return []
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            print(f"  Greenhouse {slug}: HTTP {r.status_code}")
            return []
        data = r.json()
    except Exception as e:
        print(f"  Greenhouse {slug}: {e}")
        return []

    jobs = []
    for j in data.get("jobs", []):
        title = j.get("title", "")
        location = (j.get("location") or {}).get("name", "")
        if not _is_relevant_title(title, keywords):
            continue
        if not _is_relevant_location(location, preferred_locations=preferred_locations):
            continue

        content = j.get("content", "")
        description = html.unescape(content) if content else ""
        job_id = j.get("id", "")
        canonical_url = f"https://job-boards.greenhouse.io/{slug}/jobs/{job_id}"

        jobs.append({
            "id": f"greenhouse-{slug}-{job_id}",
            "title": title,
            "company": company_name,
            "location": location,
            "description": description,
            "url": canonical_url,
            "posted_date": j.get("updated_at", ""),
            "salary": "",
            "employment_type": "",
            "seniority_level": "",
            "industries": [],
            "job_functions": [],
            "applicants": "",
            "fetched_at": datetime.now().isoformat(),
            "source": "greenhouse",
            "employer_logo": "",
            "job_apply_link": canonical_url,
            "fetch_source": "ats",
            "fetch_date": date.today().isoformat(),
        })
    return jobs


def fetch_lever(slug, company_name, keywords=None, preferred_locations=None):
    """Fetch jobs from Lever public postings API."""
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            print(f"  Lever {slug}: HTTP {r.status_code}")
            return []
        postings = r.json()
    except Exception as e:
        print(f"  Lever {slug}: {e}")
        return []

    jobs = []
    for p in postings:
        title = p.get("text", "")
        cats = p.get("categories", {}) or {}
        location = cats.get("location", "")
        workplace = p.get("workplaceType", "")
        is_remote = workplace and "remote" in workplace.lower()

        if not _is_relevant_title(title, keywords):
            continue
        if not _is_relevant_location(location, is_remote, preferred_locations):
            continue

        salary = ""
        sr = p.get("salaryRange") or {}
        if sr.get("min") and sr.get("max"):
            currency = sr.get("currency", "USD")
            salary = f"${sr['min']:,.0f} - ${sr['max']:,.0f} {currency}"

        jobs.append({
            "id": f"lever-{slug}-{p.get('id', '')}",
            "title": title,
            "company": company_name,
            "location": location,
            "description": p.get("descriptionPlain", "") or _strip_html(p.get("description", "")),
            "url": p.get("hostedUrl", ""),
            "posted_date": (
                datetime.fromtimestamp((p.get("createdAt") or 0) / 1000).isoformat()
                if p.get("createdAt") else ""
            ),
            "salary": salary,
            "employment_type": cats.get("commitment", ""),
            "seniority_level": "",
            "industries": [],
            "job_functions": [cats.get("team", "")] if cats.get("team") else [],
            "applicants": "",
            "fetched_at": datetime.now().isoformat(),
            "source": "lever",
            "employer_logo": "",
            "job_apply_link": p.get("applyUrl") or p.get("hostedUrl", ""),
            "fetch_source": "ats",
            "fetch_date": date.today().isoformat(),
        })
    return jobs


def fetch_ashby(slug, company_name, keywords=None, preferred_locations=None):
    """Fetch jobs from Ashby public job board API."""
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            print(f"  Ashby {slug}: HTTP {r.status_code}")
            return []
        data = r.json()
    except Exception as e:
        print(f"  Ashby {slug}: {e}")
        return []

    jobs = []
    for j in data.get("jobs", []):
        title = j.get("title", "")
        location = j.get("location", "")
        is_remote = j.get("isRemote", False)

        if not _is_relevant_title(title, keywords):
            continue
        if not _is_relevant_location(location, is_remote, preferred_locations):
            continue

        salary = ""
        comp = j.get("compensation") or {}
        summary = comp.get("compensationTierSummary", "")
        if summary:
            salary = summary

        jobs.append({
            "id": f"ashby-{slug}-{j.get('id', '')}",
            "title": title,
            "company": company_name,
            "location": location,
            "description": (
                j.get("descriptionPlain", "")
                or _strip_html(j.get("descriptionHtml", ""))
            ),
            "url": j.get("jobUrl", ""),
            "posted_date": j.get("publishedAt", ""),
            "salary": salary,
            "employment_type": j.get("employmentType", ""),
            "seniority_level": "",
            "industries": [],
            "job_functions": [j.get("team", "")] if j.get("team") else [],
            "applicants": "",
            "fetched_at": datetime.now().isoformat(),
            "source": "ashby",
            "employer_logo": "",
            "job_apply_link": j.get("applyUrl") or j.get("jobUrl", ""),
            "fetch_source": "ats",
            "fetch_date": date.today().isoformat(),
        })
    return jobs


ADAPTERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
}


# ---------------------------------------------------------------------------
# Probe (auto-detect a company's ATS)
# ---------------------------------------------------------------------------

def generate_slug_candidates(company_name):
    """Generate likely slug candidates for a company name.

    Examples:
      "Ambience Healthcare" -> ["ambiencehealthcare", "ambience-healthcare", "ambience"]
      "PayPal" -> ["paypal", "pay-pal"]
    """
    name = company_name.strip()
    name = re.sub(r",?\s*(Inc|LLC|Corp|Ltd|Co\.?|Company)\.?$", "", name, flags=re.I)
    lower = name.lower()
    clean = re.sub(r"[^a-z0-9 ]", "", lower)
    words = clean.split()

    candidates = []
    if words:
        candidates.append("".join(words))
        if len(words) > 1:
            candidates.append("-".join(words))
        if len(words[0]) >= 4:
            candidates.append(words[0])
        if len(words) == 1:
            candidates.append(words[0] + "work")

    seen = set()
    return [c for c in candidates if c and not (c in seen or seen.add(c))]


def _probe_one(ats, slug):
    """Try a single ATS+slug combo. Returns {"count": N} or None."""
    urls = {
        "greenhouse": f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
        "lever": f"https://api.lever.co/v0/postings/{slug}?mode=json",
        "ashby": f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
    }
    try:
        r = requests.get(urls[ats], timeout=10)
        if r.status_code == 200:
            data = r.json()
            if ats == "greenhouse" and isinstance(data, dict) and data.get("jobs"):
                return {"count": len(data["jobs"])}
            elif ats == "lever" and isinstance(data, list) and data:
                return {"count": len(data)}
            elif ats == "ashby" and isinstance(data, dict) and data.get("jobs"):
                return {"count": len(data["jobs"])}
    except Exception:
        pass
    return None


def probe_company(company_name, verbose=False):
    """Auto-detect whether a company uses Greenhouse, Lever, or Ashby.

    Returns {"ats": "greenhouse", "slug": "...", "count": 42} or None.
    Caches the result (including "none") in data/company-ats.json.
    """
    ats_map = load_ats_map()

    # Cache check (case-insensitive)
    for cached_name, info in ats_map.items():
        if cached_name.lower() == company_name.lower():
            result = {"ats": info.get("ats"), "slug": info.get("slug")}
            if verbose:
                if result["ats"] and result["ats"] != "none":
                    print(f"  {company_name}: {result['ats']}/{result['slug']} (cached)")
                else:
                    print(f"  {company_name}: no ATS (cached)")
            return result if result["ats"] and result["ats"] != "none" else None

    # Probe
    candidates = generate_slug_candidates(company_name)
    if verbose:
        print(f"  Probing {company_name} with slugs: {candidates}")

    for slug in candidates:
        for ats in ["greenhouse", "ashby", "lever"]:
            result = _probe_one(ats, slug)
            if result:
                if verbose:
                    print(f"  Found: {ats}/{slug} ({result['count']} jobs)")
                entry = {"ats": ats, "slug": slug}
                ats_map[company_name] = entry
                _save_ats_map(ats_map)
                return {"ats": ats, "slug": slug, "count": result["count"]}
            time.sleep(0.1)

    if verbose:
        print(f"  No ATS found for {company_name}")
    ats_map[company_name] = {"ats": "none", "slug": None, "probed_at": date.today().isoformat()}
    _save_ats_map(ats_map)
    return None


# ---------------------------------------------------------------------------
# ATS map I/O
# ---------------------------------------------------------------------------

def load_ats_map():
    """Load company -> ATS slug map from data/company-ats.json."""
    if not COMPANY_ATS_FILE.exists():
        return {}
    try:
        with open(COMPANY_ATS_FILE) as f:
            data = json.load(f)
        return data.get("companies", {})
    except (json.JSONDecodeError, OSError):
        return {}


def _save_ats_map(ats_map):
    """Write the updated ATS cache to disk."""
    data = {"_comment": "ATS slug cache. Add companies via: python scripts/fetch_ats.py --probe 'Company Name'"}
    if COMPANY_ATS_FILE.exists():
        try:
            with open(COMPANY_ATS_FILE) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    data["companies"] = ats_map
    COMPANY_ATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(COMPANY_ATS_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Fetch all + save
# ---------------------------------------------------------------------------

def fetch_all_ats_companies(companies_filter=None, dry_run=False, keywords=None):
    """Fetch jobs from all companies in the ATS map.

    This is the public API that fetch_jobs.py imports and calls.

    Args:
        companies_filter: Only fetch these companies (fuzzy match by name)
        dry_run: Preview without fetching
        keywords: Custom role keywords to filter titles (default: from config)

    Returns:
        list of job dicts in the standard schema
    """
    ats_map = load_ats_map()
    # Remove entries with ats=none (probed but no ATS found)
    ats_map = {k: v for k, v in ats_map.items() if v.get("ats") and v["ats"] != "none"}

    if not ats_map:
        return []

    if companies_filter:
        filter_lower = [c.lower() for c in companies_filter]
        ats_map = {
            k: v for k, v in ats_map.items()
            if any(f in k.lower() or k.lower() in f for f in filter_lower)
        }

    if not ats_map:
        return []

    print(f"ATS fetch: {len(ats_map)} companies")

    if dry_run:
        for name, info in ats_map.items():
            print(f"  {name} -> {info['ats']}/{info['slug']}")
        print("[DRY RUN] No API calls made.")
        return []

    kw = keywords or _load_role_keywords()
    preferred_locs = _load_preferred_locations()

    all_jobs = []
    for name, info in ats_map.items():
        ats = info.get("ats")
        slug = info.get("slug")
        adapter = ADAPTERS.get(ats)
        if not adapter:
            continue

        print(f"  {name} ({ats}/{slug})...", end="", flush=True)
        jobs = adapter(slug, name, keywords=kw, preferred_locations=preferred_locs)
        print(f" {len(jobs)} jobs")
        all_jobs.extend(jobs)
        time.sleep(0.5)  # gentle rate limit

    return all_jobs


def _save_to_all_jobs(new_jobs):
    """Merge fetched ATS jobs into data/jobs/all-jobs.json with dedup."""
    ALL_JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)

    existing = []
    if ALL_JOBS_FILE.exists():
        try:
            with open(ALL_JOBS_FILE) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = []

    existing_keys = set()
    for j in existing:
        key = f"{(j.get('company') or '').lower().strip()}|||{(j.get('title') or '').lower().strip()}"
        existing_keys.add(key)

    new_count = 0
    for j in new_jobs:
        key = f"{(j.get('company') or '').lower().strip()}|||{(j.get('title') or '').lower().strip()}"
        if key not in existing_keys:
            existing.append(j)
            existing_keys.add(key)
            new_count += 1

    with open(ALL_JOBS_FILE, "w") as f:
        json.dump(existing, f, indent=2)

    print(f"  Saved to {ALL_JOBS_FILE}: {len(existing)} total ({new_count} new)")
    return new_count


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fetch jobs from company career pages (Greenhouse, Lever, Ashby)"
    )
    parser.add_argument("--company", help="Fetch jobs from a single company")
    parser.add_argument("--companies", nargs="+", help="Fetch from specific companies")
    parser.add_argument("--dry-run", action="store_true", help="Preview without fetching")
    parser.add_argument("--probe", help="Auto-detect ATS for a company and cache the result")
    args = parser.parse_args()

    if args.probe:
        result = probe_company(args.probe, verbose=True)
        if result:
            print(f"\n{args.probe} -> {result['ats']}/{result['slug']}")
        else:
            print(f"\n{args.probe} -> no ATS detected (cached as 'none')")
        return

    companies_filter = None
    if args.company:
        companies_filter = [args.company]
    elif args.companies:
        companies_filter = args.companies

    jobs = fetch_all_ats_companies(companies_filter=companies_filter, dry_run=args.dry_run)
    if jobs:
        _save_to_all_jobs(jobs)
        print(f"\nTotal ATS jobs: {len(jobs)}")


if __name__ == "__main__":
    main()
