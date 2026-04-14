#!/usr/bin/env python3
"""Classify companies as 'startup' or 'large' for outreach tone adjustment."""

import argparse
import json
import os
import sys

PROJECT_DIR = os.environ.get("JOB_SEARCH_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SIZES_FILE = os.path.join(PROJECT_DIR, "data", "company-sizes.json")
CRITERIA_FILE = os.path.join(PROJECT_DIR, "data", "search-criteria.json")


def load_sizes():
    if os.path.exists(SIZES_FILE):
        with open(SIZES_FILE) as f:
            return json.load(f)
    return {"large": [], "startup": []}


def save_sizes(data):
    with open(SIZES_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved to {SIZES_FILE}")


def classify(company_name, sizes=None):
    """Return 'large', 'startup', or 'unknown' for a company name."""
    if sizes is None:
        sizes = load_sizes()

    name_lower = company_name.lower().strip()

    for size_type in ["large", "startup"]:
        for name in sizes.get(size_type, []):
            if name.lower() == name_lower:
                return size_type

    # Fallback: check search-criteria.json categories
    if os.path.exists(CRITERIA_FILE):
        with open(CRITERIA_FILE) as f:
            criteria = json.load(f)
        big_tech = []
        fintech = []
        enterprise = []
        for industry in criteria.get("industries", {}).get("secondary", []):
            if industry["name"] == "Big Tech AI":
                big_tech = industry.get("companies", [])
            elif industry["name"] == "Fintech":
                fintech = industry.get("companies", [])
            elif industry["name"] == "Enterprise SaaS":
                enterprise = industry.get("companies", [])

        big_tech_lower = [c.lower() for c in big_tech + fintech]
        if name_lower in big_tech_lower:
            return "large"

    return "unknown"


def add_company(company_name, size_type):
    """Add a company to the classification database."""
    if size_type not in ("large", "startup"):
        print(f"Error: size must be 'large' or 'startup', got '{size_type}'")
        sys.exit(1)

    sizes = load_sizes()

    # Remove from other category if present
    other = "startup" if size_type == "large" else "large"
    sizes[other] = [c for c in sizes[other] if c.lower() != company_name.lower()]

    # Add if not already present
    existing = [c.lower() for c in sizes[size_type]]
    if company_name.lower() not in existing:
        sizes[size_type].append(company_name)
        save_sizes(sizes)
        print(f"Added '{company_name}' as {size_type}")
    else:
        print(f"'{company_name}' is already classified as {size_type}")


def main():
    parser = argparse.ArgumentParser(description="Classify company as startup or large")
    parser.add_argument("company", help="Company name to classify")
    parser.add_argument("--add", choices=["large", "startup"],
                        help="Add company to classification database")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON")
    args = parser.parse_args()

    if args.add:
        add_company(args.company, args.add)
        return

    result = classify(args.company)

    if args.json:
        print(json.dumps({"company": args.company, "size": result}))
    else:
        print(result)

    if result == "unknown":
        print(f"Warning: '{args.company}' not found. Use --add to classify it.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
