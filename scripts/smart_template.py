#!/usr/bin/env python3
"""Generate LinkedIn outreach messages based on company size, recipient role, and message type."""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_loader import (
    get_first_name, get_credibility, get_sign_off, get_pm_phrase, load_profile
)
from company_classifier import classify

# Character limits
LIMITS = {
    "connection-request": 300,
    "inmail": 1900,
    "linkedin-message": 1900,
}

# Role-specific hooks
ROLE_HOOKS = {
    "recruiter": {
        "opener": "I just applied for the {job_title} role at {company}.",
        "cta_short": "Would love to connect!",
        "cta_long": "Would love to connect and learn more about the team.",
    },
    "hiring-manager": {
        "opener": "I just applied for the {job_title} role at {company}.",
        "cta_short": "Would love to connect!",
        "cta_long": "I'd love to learn more about your vision for the team and how this role fits in.",
    },
    "ceo": {
        "opener": "love what you're building at {company}.",
        "cta_short": "Would love to connect!",
        "cta_long": "I'd love to connect and learn more about {company}'s vision.",
    },
    "executive": {
        "opener": "love what you're building at {company}.",
        "cta_short": "Would love to connect!",
        "cta_long": "I'd love to connect and learn more about {company}'s direction.",
    },
    "peer": {
        "opener": "I'm exploring my next opportunity and just applied for the {job_title} role at {company}.",
        "cta_short": "Would love to connect!",
        "cta_long": "I'd love to hear more about your experience at {company}. Happy to chat anytime.",
    },
}


def generate_connection_request(name, company, job_title, recipient_role, company_size, variant=None):
    """Generate a short connection request (under 300 chars).

    Variants for A/B testing:
        A - Applied + credibility + build experience (standard)
        B - Applied + specific skill match + enthusiasm
        C - Exploring + mission-driven + credibility
        D - Applied + quantified impact + CTA
    """
    pm = get_pm_phrase(company_size)
    cred_short = get_credibility("short")
    first_name = get_first_name()
    sign_off = get_sign_off("linkedin")

    # Load quantified impact if available
    profile = load_profile()
    impact = profile.get("quantified_impact", "significant documented impact")

    variants = {
        "A": f"Hi {name}, I just applied for the {job_title} role at {company}. I'm a {pm} with {cred_short}. Would love to connect! {sign_off}",
        "B": f"Hi {name}, I just applied for the {job_title} role at {company}. {cred_short}. Excited about this role. Would love to connect! {sign_off}",
        "C": f"Hi {name}, I'm exploring my next opportunity and applied for the {job_title} role at {company}. Love what the team is building. I'm a {pm} with {cred_short}. Would love to connect! {sign_off}",
        "D": f"Hi {name}, I applied for the {job_title} role at {company}. I'm a {pm} who has driven {impact}. Would love to connect and learn more about the team! {sign_off}",
    }

    if variant and variant.upper() in variants:
        msg = variants[variant.upper()]
    else:
        msg = variants["A"]

    # Trim if over 300 by using shorter versions
    if len(msg) > 300:
        variants_fallback = {
            "A": f"Hi {name}, I applied for the {job_title} role at {company}. I'm a {pm} with {cred_short}. Would love to connect! {sign_off}",
            "B": f"Hi {name}, I applied for the {job_title} role at {company}. {cred_short}. Would love to connect! {sign_off}",
            "C": f"Hi {name}, I applied for the {job_title} role at {company}. Love what the team is building. Would love to connect! {sign_off}",
            "D": f"Hi {name}, I applied for the {job_title} role at {company}. I'm a {pm} with {impact}. Would love to learn more! {sign_off}",
        }
        v = (variant or "A").upper()
        msg = variants_fallback.get(v, variants_fallback["A"])

    return msg


def generate_all_variants(name, company, job_title, recipient_role, company_size):
    """Generate all 4 variants for A/B testing."""
    results = {}
    for v in ["A", "B", "C", "D"]:
        msg = generate_connection_request(name, company, job_title, recipient_role, company_size, variant=v)
        results[v] = {"message": msg, "chars": len(msg)}
    return results


def generate_long_message(name, company, job_title, recipient_role, company_size, subject=False):
    """Generate a longer LinkedIn message or InMail."""
    pm = get_pm_phrase(company_size)
    cred_long = get_credibility("long")
    first_name = get_first_name()
    sign_off = get_sign_off("linkedin")
    profile = load_profile()
    title = profile.get("title", "")

    role_config = ROLE_HOOKS.get(recipient_role, ROLE_HOOKS["recruiter"])
    cta = role_config["cta_long"].format(company=company)

    # Opening
    if recipient_role in ("ceo", "executive"):
        opening = f"I'm exploring my next opportunity and {role_config['opener'].format(company=company, job_title=job_title)} I applied for the {job_title} role."
    elif recipient_role == "peer":
        opening = role_config["opener"].format(company=company, job_title=job_title)
    else:
        opening = f"I'm exploring my next opportunity and just applied for the {job_title} role at {company}."

    body = f"""Hi {name},

{opening}

A bit about me: I'm a {pm} with {cred_long}.

{cta}

{sign_off}"""

    result = body

    # Generate subject lines for InMail
    if subject:
        subjects = [
            f"{pm.upper()} with {get_credibility('short')}",
            f"Applied for the {job_title} role",
            f"Excited about {company}'s {job_title} opportunity",
            f"{title} interested in {company}",
            f"{pm.upper()} with startup and enterprise experience",
        ]
        result = {"subject_lines": subjects, "body": body}

    return result


def generate(name, company, job_title, recipient_role, msg_type):
    """Generate a message based on all parameters."""
    company_size = classify(company)

    if msg_type == "connection-request":
        msg = generate_connection_request(name, company, job_title, recipient_role, company_size)
        char_count = len(msg)
        print(f"--- Connection Request ({char_count}/300 chars) ---\n")
        print(msg)
        if char_count > 300:
            print(f"\n WARNING: {char_count} chars exceeds 300 limit!", file=sys.stderr)
    elif msg_type in ("inmail", "linkedin-message"):
        result = generate_long_message(
            name, company, job_title, recipient_role,
            company_size, subject=(msg_type == "inmail")
        )
        if isinstance(result, dict):
            print("--- Subject Line Options ---\n")
            for i, s in enumerate(result["subject_lines"], 1):
                print(f"  {i}. {s}")
            print(f"\n--- InMail Body ---\n")
            print(result["body"])
        else:
            print(f"--- LinkedIn Message ---\n")
            print(result)

    return company_size


def main():
    parser = argparse.ArgumentParser(description="Generate LinkedIn outreach messages")
    parser.add_argument("--name", required=True, help="Recipient first name")
    parser.add_argument("--company", required=True)
    parser.add_argument("--job-title", required=True, help="Role you applied for")
    parser.add_argument("--role", required=True,
                        choices=["recruiter", "hiring-manager", "executive", "peer", "ceo"],
                        help="Recipient's role type")
    parser.add_argument("--type", required=True, dest="msg_type",
                        choices=["connection-request", "inmail", "linkedin-message"])
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    generate(args.name, args.company, args.job_title, args.role, args.msg_type)


if __name__ == "__main__":
    main()
