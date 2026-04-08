#!/usr/bin/env python3
"""
Job Search Agent - Interactive Setup

Run this script after cloning the project to configure it for your job search.

Usage:
    python setup.py                  # Interactive setup
    python setup.py --from-config    # Regenerate CLAUDE.md and skill file from existing config
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).parent.resolve()
CONFIG_DIR = PROJECT_DIR / "config"
COMMANDS_DIR = PROJECT_DIR / "commands"
CLAUDE_MD_PATH = PROJECT_DIR / "CLAUDE.md"
CLAUDE_MD_TEMPLATE = COMMANDS_DIR / "CLAUDE.md.template"
SKILL_DIR = Path.home() / ".claude" / "commands"
SKILL_FILE = SKILL_DIR / "job-search-agent.md"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ask(prompt, default=None, required=True):
    """Prompt the user for input. Show default in brackets. Return stripped string."""
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"  {prompt}{suffix}: ").strip()
        if not value and default is not None:
            return default
        if value:
            return value
        if not required:
            return ""
        print("    (required -- please enter a value)")


def ask_list(prompt, default=None, required=True):
    """Prompt for a comma-separated list. Returns a list of stripped strings."""
    raw = ask(prompt, default=default, required=required)
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def ask_yes_no(prompt, default="y"):
    """Ask a yes/no question. Returns True for yes."""
    suffix = " [Y/n]" if default.lower() == "y" else " [y/N]"
    value = input(f"  {prompt}{suffix}: ").strip().lower()
    if not value:
        return default.lower() == "y"
    return value in ("y", "yes")


def heading(title):
    """Print a section heading."""
    width = 60
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)
    print()


def subheading(title):
    """Print a sub-section heading."""
    print()
    print(f"  --- {title} ---")
    print()


def make_filename_prefix(full_name):
    """Generate LastFirst filename prefix from a full name."""
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return parts[-1] + parts[0]
    return parts[0] if parts else "User"


def write_json(filepath, data):
    """Write a dict to a JSON file with pretty formatting."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Created: {filepath}")


def load_json(filepath):
    """Load a JSON file and return its contents."""
    with open(filepath) as f:
        return json.load(f)

# ---------------------------------------------------------------------------
# Section: Personal Info
# ---------------------------------------------------------------------------

def collect_personal_info():
    """Collect name, title, contact info."""
    heading("1. Personal Information")
    print("  We'll start with your basic info. Press Enter to accept defaults.\n")

    name = ask("Full name")
    title = ask("Professional headline (e.g. 'Product and AI Leader')")
    email = ask("Email address")
    phone = ask("Phone number (e.g. 415-555-1234)")
    website = ask("Website or LinkedIn URL", required=False)
    location = ask("Location (e.g. 'San Francisco Bay Area')", default="San Francisco Bay Area")

    # Languages
    print("\n  Which languages do you want to generate outreach in?")
    languages = ask_list("Languages", default="en, es")
    default_language = ask("Default language", default=languages[0] if languages else "en")

    return {
        "name": name,
        "title": title,
        "contact": {
            "email": email,
            "phone": phone,
            "website": website,
            "location": location,
        },
        "languages": languages,
        "default_language": default_language,
    }


# ---------------------------------------------------------------------------
# Section: Career Context
# ---------------------------------------------------------------------------

def collect_career_context():
    """Collect years of experience, key roles, skills, education."""
    heading("2. Career Context")

    years = ask("Years of professional experience", default="10")

    subheading("Key Roles (enter 2-4 of your most impressive roles)")
    print("  For each role, provide: company, title, and one achievement line.\n")

    roles = []
    for i in range(1, 5):
        if i > 2:
            if not ask_yes_no(f"Add role #{i}?", default="n"):
                break
        company = ask(f"  Role #{i} - Company")
        role_title = ask(f"  Role #{i} - Title")
        achievement = ask(f"  Role #{i} - Key achievement (1 line)")
        roles.append({
            "company": company,
            "title": role_title,
            "achievement": achievement,
        })
        print()

    subheading("Skills & Education")
    skills = ask_list("Top skills (comma-separated)", default="Product Management, Data Science, AI/ML, Strategy")
    education = ask("Education highlights (e.g. 'MBA Stanford, BS Computer Science MIT')")

    return {
        "years_of_experience": years,
        "key_roles": roles,
        "skills": skills,
        "education": education,
    }


# ---------------------------------------------------------------------------
# Section: Credibility Snippets
# ---------------------------------------------------------------------------

def collect_credibility(personal_info, career):
    """Collect short, medium, long credibility blurbs and quantified impact."""
    heading("3. Credibility Snippets")
    print("  These are reused across outreach messages, cover letters, and templates.")
    print("  Tailor them to be punchy and specific.\n")

    first_name = personal_info["name"].split()[0]
    title = personal_info["title"]
    years = career["years_of_experience"]

    default_short = f"{years}+ years in product and technology"
    default_medium = f"{title} with {years}+ years of experience building data and AI products."
    if career["key_roles"]:
        latest = career["key_roles"][0]
        default_medium += f" Most recently {latest['title']} at {latest['company']}."
    default_long = default_medium
    if len(career["key_roles"]) > 1:
        companies = ", ".join(r["company"] for r in career["key_roles"][:3])
        default_long += f" Track record across {companies}."

    short = ask(
        "Short credibility (under 50 chars)",
        default=default_short,
    )
    medium = ask(
        "Medium credibility (1-2 sentences)",
        default=default_medium,
    )
    long_cred = ask(
        "Long credibility (2-3 sentences, full career arc)",
        default=default_long,
    )
    impact = ask(
        "Quantified impact line (e.g. '$100M+ in documented impact')",
        default="significant documented business impact",
    )

    return {
        "short": short,
        "medium": medium,
        "long": long_cred,
    }, impact


# ---------------------------------------------------------------------------
# Section: Search Preferences
# ---------------------------------------------------------------------------

def collect_search_preferences():
    """Collect target roles, industries, companies, locations, keywords."""
    heading("4. Job Search Preferences")

    subheading("Target Roles")
    target_roles = ask_list(
        "Target role titles (comma-separated)",
        default="Product Manager, Senior Product Manager, Director of Product",
    )

    subheading("Industries & Companies")
    target_industries = ask_list(
        "Target industries (comma-separated)",
        default="AI/ML, SaaS, Fintech, Health Tech",
    )
    target_companies = ask_list(
        "Target companies (comma-separated, optional -- press Enter to skip)",
        required=False,
    )

    subheading("Locations")
    preferred_locations = ask_list(
        "Preferred locations (comma-separated)",
        default="San Francisco Bay Area, Remote",
    )
    acceptable_locations = ask_list(
        "Also acceptable locations (comma-separated, optional)",
        required=False,
    )

    subheading("Exclusions")
    exclude_titles = ask_list(
        "Titles to exclude (comma-separated)",
        default="Junior, Associate, Intern, Entry Level",
    )
    exclude_companies = ask_list(
        "Companies to exclude (comma-separated, optional)",
        required=False,
    )

    subheading("Search Keywords")
    high_priority = ask_list(
        "High-priority search keywords (comma-separated)",
        default=", ".join(target_roles[:3]) if target_roles else "Product Manager",
    )
    medium_priority = ask_list(
        "Medium-priority search keywords (comma-separated)",
        default="AI Product Manager, Data Product Manager, Strategy",
    )

    subheading("Scoring")
    print("  How important are these factors when ranking jobs? (1-10)\n")
    title_weight = ask("Title match weight", default="10")
    industry_weight = ask("Industry match weight", default="8")
    company_weight = ask("Company match weight", default="7")
    location_weight = ask("Location match weight", default="6")
    seniority_weight = ask("Seniority match weight", default="9")

    return {
        "roles": {
            "target": target_roles,
            "exclude_titles": exclude_titles,
        },
        "companies": {
            "target": target_companies,
            "exclude": exclude_companies,
        },
        "industries": {
            "target": target_industries,
        },
        "locations": {
            "preferred": preferred_locations,
            "acceptable": acceptable_locations,
        },
        "search_queries": {
            "high_priority": high_priority,
            "medium_priority": medium_priority,
        },
        "scoring_weights": {
            "title_match": int(title_weight),
            "industry_match": int(industry_weight),
            "company_match": int(company_weight),
            "location_match": int(location_weight),
            "seniority_match": int(seniority_weight),
        },
    }


# ---------------------------------------------------------------------------
# Section: Writing Style
# ---------------------------------------------------------------------------

def collect_writing_style(first_name, languages=None):
    """Collect sign-offs, PM phrases, and writing rules."""
    if languages is None:
        languages = ["en"]
    heading("5. Writing Style Preferences")

    print("\n  Sign-offs (per language):")
    sign_offs = {}
    for lang in languages:
        print(f"\n  [{lang.upper()}]:")
        if lang == "es":
            linkedin_default = f"~{first_name}"
            email_default = "Saludos,"
            formal_default = "Atentamente,"
        else:
            linkedin_default = f"~{first_name}"
            email_default = "Best,"
            formal_default = "Regards,"

        sign_offs[lang] = {
            "linkedin": ask(f"LinkedIn sign-off ({lang})", default=linkedin_default),
            "email": ask(f"Email sign-off ({lang})", default=email_default),
            "formal": ask(f"Formal sign-off ({lang})", default=formal_default),
            "default": f"~{first_name}",
        }

    subheading("PM Phrasing")
    print("  How should you be described when reaching out to different company types?\n")
    pm_startup = ask("PM phrase for startups (e.g. 'PM', 'product leader')", default="PM")
    pm_large = ask("PM phrase for large companies (e.g. 'PM', 'product manager')", default="PM")

    subheading("Writing Rules")
    print("  These rules are included in CLAUDE.md so the AI follows your voice.\n")

    default_rules = [
        "No em dashes",
        "Short sentences preferred",
        "No fluff or filler phrases",
        "Warm but professional tone",
        "Quantify impact with real numbers whenever possible",
        "Use active voice",
        "Keep paragraphs to 2-3 sentences max",
    ]

    print("  Default rules:")
    for i, rule in enumerate(default_rules, 1):
        print(f"    {i}. {rule}")
    print()

    if ask_yes_no("Use these defaults?"):
        rules = default_rules
    else:
        rules_raw = ask("Enter your rules (comma-separated)")
        rules = [r.strip() for r in rules_raw.split(",") if r.strip()]

    extra_rules = ask(
        "Any additional rules to add? (comma-separated, or Enter to skip)",
        required=False,
    )
    if extra_rules:
        rules.extend([r.strip() for r in extra_rules.split(",") if r.strip()])

    print("\n  Humanizer (removes AI-sounding patterns from generated content):")
    humanizer_enabled = ask("Enable humanizer?", default="yes").lower() in ("yes", "y", "true", "1")

    return {
        "sign_offs": sign_offs,
        "pm_phrases": {
            "startup": pm_startup,
            "large": pm_large,
            "unknown": "PM",
        },
        "writing_rules": rules,
        "humanizer": {
            "enabled": humanizer_enabled,
            "rules_file": "config/humanizer-rules.json",
            "self_check": True,
        },
    }


# ---------------------------------------------------------------------------
# Section: Talking Points
# ---------------------------------------------------------------------------

def collect_talking_points():
    """Collect industry-specific talking points."""
    heading("6. Talking Points by Industry / Context")
    print("  When reaching out to companies in specific industries, what should")
    print("  be emphasized? Add at least 2 industry contexts.\n")

    talking_points = {}
    count = 0
    while True:
        count += 1
        if count > 2:
            if not ask_yes_no("Add another industry context?", default="n"):
                break

        industry = ask(f"Industry/context name (e.g. 'AI/ML', 'Fintech', 'Health Tech')")
        print(f"  Enter 2-3 bullet points for {industry}:")
        bullets = []
        for j in range(1, 4):
            bullet = ask(f"    Point #{j}", required=(j <= 2))
            if bullet:
                bullets.append(bullet)
            else:
                break

        talking_points[industry] = bullets
        print()

    return talking_points


# ---------------------------------------------------------------------------
# Generate CLAUDE.md
# ---------------------------------------------------------------------------

def generate_claude_md(profile, search_criteria, talking_points, writing_style):
    """Generate the project CLAUDE.md file from config data."""
    # Check for template
    if CLAUDE_MD_TEMPLATE.exists():
        with open(CLAUDE_MD_TEMPLATE) as f:
            template = f.read()
        # Replace placeholders
        replacements = {
            "{{name}}": profile["name"],
            "{{first_name}}": profile["name"].split()[0],
            "{{title}}": profile["title"],
            "{{email}}": profile["contact"]["email"],
            "{{phone}}": profile["contact"]["phone"],
            "{{website}}": profile["contact"].get("website", ""),
            "{{location}}": profile["contact"]["location"],
            "{{cred_short}}": profile["credibility"]["short"],
            "{{cred_medium}}": profile["credibility"]["medium"],
            "{{cred_long}}": profile["credibility"]["long"],
            "{{sign_off_linkedin}}": writing_style["sign_offs"].get("en", next(iter(writing_style["sign_offs"].values()), {})).get("linkedin", ""),
            "{{sign_off_email}}": writing_style["sign_offs"].get("en", next(iter(writing_style["sign_offs"].values()), {})).get("email", ""),
            "{{sign_off_formal}}": writing_style["sign_offs"].get("en", next(iter(writing_style["sign_offs"].values()), {})).get("formal", ""),
            "{{filename_prefix}}": profile.get("filename_prefix", ""),
        }
        for key, value in replacements.items():
            template = template.replace(key, value)
        return template

    # Generate from scratch
    first_name = profile["name"].split()[0]
    lines = []
    lines.append(f"# Job Search Agent - {profile['name']}")
    lines.append("")
    lines.append(f"This project powers {first_name}'s job search with automated outreach,")
    lines.append("cover letter generation, job tracking, and messaging templates.")
    lines.append("")

    # Identity
    lines.append("## Identity")
    lines.append("")
    lines.append(f"- **Name**: {profile['name']}")
    lines.append(f"- **Title**: {profile['title']}")
    lines.append(f"- **Email**: {profile['contact']['email']}")
    lines.append(f"- **Phone**: {profile['contact']['phone']}")
    if profile["contact"].get("website"):
        lines.append(f"- **Website**: {profile['contact']['website']}")
    lines.append(f"- **Location**: {profile['contact']['location']}")
    lines.append(f"- **Filename prefix**: {profile.get('filename_prefix', '')}")
    lines.append("")

    # Credibility
    lines.append("## Credibility Snippets")
    lines.append("")
    lines.append(f"- **Short** (under 50 chars): {profile['credibility']['short']}")
    lines.append(f"- **Medium** (1-2 sentences): {profile['credibility']['medium']}")
    lines.append(f"- **Long** (2-3 sentences): {profile['credibility']['long']}")
    if profile.get("quantified_impact"):
        lines.append(f"- **Quantified impact**: {profile['quantified_impact']}")
    lines.append("")

    # Career
    lines.append("## Career Context")
    lines.append("")
    lines.append(f"- **Years of experience**: {profile['career']['years_of_experience']}")
    lines.append(f"- **Skills**: {', '.join(profile['career']['skills'])}")
    lines.append(f"- **Education**: {profile['career']['education']}")
    lines.append("")
    lines.append("### Key Roles")
    lines.append("")
    for role in profile["career"]["key_roles"]:
        lines.append(f"- **{role['title']}** at {role['company']}: {role['achievement']}")
    lines.append("")

    # Search criteria
    lines.append("## Search Criteria")
    lines.append("")
    lines.append(f"- **Target roles**: {', '.join(search_criteria['roles']['target'])}")
    lines.append(f"- **Target industries**: {', '.join(search_criteria['industries']['target'])}")
    if search_criteria["companies"]["target"]:
        lines.append(f"- **Target companies**: {', '.join(search_criteria['companies']['target'])}")
    lines.append(f"- **Preferred locations**: {', '.join(search_criteria['locations']['preferred'])}")
    if search_criteria["roles"]["exclude_titles"]:
        lines.append(f"- **Exclude titles containing**: {', '.join(search_criteria['roles']['exclude_titles'])}")
    lines.append("")

    # Talking points
    lines.append("## Talking Points")
    lines.append("")
    for industry, points in talking_points.items():
        lines.append(f"### {industry}")
        for point in points:
            lines.append(f"- {point}")
        lines.append("")

    # Writing style
    lines.append("## Writing Style")
    lines.append("")
    lines.append("### Sign-offs")
    for lang, offs in writing_style["sign_offs"].items():
        lines.append(f"#### [{lang.upper()}]")
        lines.append(f"- LinkedIn: `{offs['linkedin']}`")
        lines.append(f"- Email: `{offs['email']}`")
        lines.append(f"- Formal: `{offs['formal']}`")
        lines.append("")
    lines.append("### PM Phrasing")
    lines.append(f"- Startups: \"{writing_style['pm_phrases']['startup']}\"")
    lines.append(f"- Large companies: \"{writing_style['pm_phrases']['large']}\"")
    lines.append("")
    lines.append("### Writing Rules")
    lines.append("")
    for rule in writing_style["writing_rules"]:
        lines.append(f"- {rule}")
    lines.append("")

    # Humanizer
    humanizer = writing_style.get("humanizer", {})
    if humanizer.get("enabled"):
        lines.append("### Humanizer")
        lines.append("")
        lines.append("Humanizer is **enabled**. All generated outreach content is post-processed")
        lines.append(f"using rules from `{humanizer.get('rules_file', 'config/humanizer-rules.json')}`")
        lines.append("to remove AI-sounding patterns and ensure natural, human-written tone.")
        if humanizer.get("self_check"):
            lines.append("Self-check mode is on: the agent will review its own output for AI patterns.")
        lines.append("")

    # Project structure
    lines.append("## Project Structure")
    lines.append("")
    lines.append("```")
    lines.append("config/              Config files (generated by setup.py)")
    lines.append("  profile.json       Personal info, career, credibility")
    lines.append("  search-criteria.json  Roles, companies, industries, locations")
    lines.append("  talking-points.json   Industry-specific talking points")
    lines.append("  writing-style.json    Sign-offs, PM phrases, writing rules")
    lines.append("scripts/             Automation scripts")
    lines.append("  config_loader.py   Shared config loader (all scripts import this)")
    lines.append("  fetch_jobs.py      Multi-source job fetcher (JSearch, Apify)")
    lines.append("  save_job.py        Save and track job postings")
    lines.append("  smart_template.py  Generate LinkedIn outreach messages")
    lines.append("  company_classifier.py  Classify companies as startup/large")
    lines.append("  update_outreach.py Log and track outreach outcomes")
    lines.append("  score_messages.py  Analyze message performance")
    lines.append("  generate_pdf.py    Generate cover letter and resume PDFs")
    lines.append("templates/           Message and document templates")
    lines.append("data/                Job data, outreach history")
    lines.append("outputs/             Generated cover letters and resumes")
    lines.append("```")
    lines.append("")

    # Usage instructions
    lines.append("## Key Commands")
    lines.append("")
    lines.append(f"All scripts are in `{PROJECT_DIR / 'scripts'}`.")
    lines.append("")
    lines.append("```bash")
    lines.append("# Fetch jobs")
    lines.append(f"python {PROJECT_DIR / 'scripts' / 'fetch_jobs.py'}")
    lines.append("")
    lines.append("# Save a job you applied to")
    lines.append(f"python {PROJECT_DIR / 'scripts' / 'save_job.py'} save --company Acme --role 'Product Manager'")
    lines.append("")
    lines.append("# Generate outreach message")
    lines.append(f"python {PROJECT_DIR / 'scripts' / 'smart_template.py'} --name Alex --company Acme --job-title 'PM' --role recruiter --type connection-request")
    lines.append("")
    lines.append("# Log outreach")
    lines.append(f"python {PROJECT_DIR / 'scripts' / 'update_outreach.py'} log --name Alex --company Acme --role recruiter --type connection-request --message 'Hi...'")
    lines.append("")
    lines.append("# View outreach stats")
    lines.append(f"python {PROJECT_DIR / 'scripts' / 'update_outreach.py'} stats")
    lines.append("")
    lines.append("# Generate cover letter PDF")
    lines.append(f"python {PROJECT_DIR / 'scripts' / 'generate_pdf.py'} --type cover-letter --input path/to/letter.md --company Acme")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generate Skill File
# ---------------------------------------------------------------------------

def generate_skill_file(profile):
    """Generate the ~/.claude/commands/job-search-agent.md skill file."""
    first_name = profile["name"].split()[0]
    scripts = PROJECT_DIR / "scripts"

    lines = []
    lines.append("# /job-search-agent")
    lines.append("")
    lines.append(f"{first_name}'s job search automation agent. Manages outreach, cover letters,")
    lines.append("job tracking, and messaging from the command line using Claude Code.")
    lines.append("")
    lines.append("## Usage")
    lines.append("")
    lines.append("```")
    lines.append("/job-search-agent")
    lines.append("```")
    lines.append("")
    lines.append("Then describe what you need: draft a cover letter, generate outreach,")
    lines.append("save a job, check stats, etc.")
    lines.append("")
    lines.append("## Project Location")
    lines.append("")
    lines.append(f"- **Project root**: `{PROJECT_DIR}`")
    lines.append(f"- **Config**: `{CONFIG_DIR}`")
    lines.append(f"- **Scripts**: `{scripts}`")
    lines.append(f"- **Templates**: `{PROJECT_DIR / 'templates'}`")
    lines.append(f"- **Data**: `{PROJECT_DIR / 'data'}`")
    lines.append(f"- **Outputs**: `{PROJECT_DIR / 'outputs'}`")
    lines.append("")
    lines.append("## Available Scripts")
    lines.append("")
    lines.append(f"### Fetch Jobs")
    lines.append(f"```bash")
    lines.append(f"python {scripts / 'fetch_jobs.py'} --keywords 'Product Manager' --locations 'San Francisco'")
    lines.append(f"```")
    lines.append("")
    lines.append(f"### Save a Job")
    lines.append(f"```bash")
    lines.append(f"python {scripts / 'save_job.py'} save --company Acme --role 'Product Manager' --url 'https://...'")
    lines.append(f"```")
    lines.append("")
    lines.append(f"### Generate Outreach Message")
    lines.append(f"```bash")
    lines.append(f"python {scripts / 'smart_template.py'} --name Alex --company Acme --job-title 'PM' --role recruiter --type connection-request")
    lines.append(f"```")
    lines.append("")
    lines.append(f"### Log Outreach")
    lines.append(f"```bash")
    lines.append(f"python {scripts / 'update_outreach.py'} log --name Alex --company Acme --role recruiter --type connection-request --message 'Hi...'")
    lines.append(f"```")
    lines.append("")
    lines.append(f"### View Stats")
    lines.append(f"```bash")
    lines.append(f"python {scripts / 'update_outreach.py'} stats")
    lines.append(f"```")
    lines.append("")
    lines.append(f"### Analyze Message Performance")
    lines.append(f"```bash")
    lines.append(f"python {scripts / 'score_messages.py'}")
    lines.append(f"```")
    lines.append("")
    lines.append(f"### Generate PDF")
    lines.append(f"```bash")
    lines.append(f"python {scripts / 'generate_pdf.py'} --type cover-letter --input path/to/letter.md --company Acme")
    lines.append(f"```")
    lines.append("")
    lines.append(f"### Classify Company")
    lines.append(f"```bash")
    lines.append(f"python {scripts / 'company_classifier.py'} 'Google'")
    lines.append(f"```")
    lines.append("")
    lines.append("## Config Files")
    lines.append("")
    lines.append(f"- `{CONFIG_DIR / 'profile.json'}` - Personal info, career, credibility")
    lines.append(f"- `{CONFIG_DIR / 'search-criteria.json'}` - Roles, companies, industries, locations")
    lines.append(f"- `{CONFIG_DIR / 'talking-points.json'}` - Industry-specific talking points")
    lines.append(f"- `{CONFIG_DIR / 'writing-style.json'}` - Sign-offs, PM phrases, writing rules")
    lines.append("")
    lines.append("## Instructions")
    lines.append("")
    lines.append(f"1. Read the project CLAUDE.md at `{CLAUDE_MD_PATH}` for full context.")
    lines.append(f"2. Load config using `scripts/config_loader.py` functions.")
    lines.append(f"3. Use the templates in `{PROJECT_DIR / 'templates'}` for message structure.")
    lines.append(f"4. Save all generated outputs to `{PROJECT_DIR / 'outputs'}`.")
    lines.append(f"5. Follow writing rules from `{CONFIG_DIR / 'writing-style.json'}`.")
    lines.append(f"6. If humanizer is enabled in writing-style.json, apply humanizer rules")
    lines.append(f"   from `{CONFIG_DIR / 'humanizer-rules.json'}` to all generated content")
    lines.append(f"   to remove AI-sounding patterns before finalizing output.")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main: Interactive Setup
# ---------------------------------------------------------------------------

def run_interactive_setup():
    """Run the full interactive setup flow."""
    print()
    print("=" * 60)
    print("   Job Search Agent - Setup")
    print("=" * 60)
    print()
    print("  Welcome! This script will configure the job search agent")
    print("  for your personal use. It takes about 5-10 minutes.")
    print()
    print("  We'll collect:")
    print("    1. Personal information")
    print("    2. Career context")
    print("    3. Credibility snippets (for outreach messages)")
    print("    4. Job search preferences")
    print("    5. Writing style preferences")
    print("    6. Industry-specific talking points")
    print()
    print("  Then we'll generate config files, CLAUDE.md, and a")
    print("  Claude Code skill file so everything works together.")
    print()

    if not ask_yes_no("Ready to begin?"):
        print("\n  No problem. Run this script again when you're ready.\n")
        sys.exit(0)

    # ---- 1. Personal Info ----
    personal = collect_personal_info()

    # ---- 2. Career ----
    career = collect_career_context()

    # ---- 3. Credibility ----
    credibility, quantified_impact = collect_credibility(personal, career)

    # ---- 4. Search Preferences ----
    search_criteria = collect_search_preferences()

    # ---- 5. Writing Style ----
    first_name = personal["name"].split()[0]
    languages = personal.get("languages", ["en"])
    writing_style = collect_writing_style(first_name, languages=languages)

    # ---- 6. Talking Points ----
    talking_points = collect_talking_points()

    # ---- Build profile.json ----
    profile = {
        "name": personal["name"],
        "title": personal["title"],
        "contact": personal["contact"],
        "filename_prefix": make_filename_prefix(personal["name"]),
        "career": {
            "years_of_experience": career["years_of_experience"],
            "key_roles": career["key_roles"],
            "skills": career["skills"],
            "education": career["education"],
        },
        "credibility": credibility,
        "quantified_impact": quantified_impact,
        "languages": personal.get("languages", ["en"]),
        "default_language": personal.get("default_language", "en"),
    }

    # ---- Write config files ----
    heading("Generating Config Files")

    write_json(CONFIG_DIR / "profile.json", profile)
    write_json(CONFIG_DIR / "search-criteria.json", search_criteria)
    write_json(CONFIG_DIR / "talking-points.json", talking_points)
    write_json(CONFIG_DIR / "writing-style.json", writing_style)

    # ---- Generate CLAUDE.md ----
    claude_md_content = generate_claude_md(profile, search_criteria, talking_points, writing_style)
    with open(CLAUDE_MD_PATH, "w") as f:
        f.write(claude_md_content)
    print(f"  Created: {CLAUDE_MD_PATH}")

    # ---- Generate skill file ----
    SKILL_DIR.mkdir(parents=True, exist_ok=True)
    skill_content = generate_skill_file(profile)
    with open(SKILL_FILE, "w") as f:
        f.write(skill_content)
    print(f"  Created: {SKILL_FILE}")

    # ---- Initialize data files if they don't exist ----
    data_dir = PROJECT_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "jobs").mkdir(parents=True, exist_ok=True)

    history_file = data_dir / "outreach-history.json"
    if not history_file.exists():
        history = {
            "metadata": {
                "created": __import__("datetime").date.today().isoformat(),
                "last_updated": __import__("datetime").date.today().isoformat(),
            },
            "connections": [],
            "applications": [],
            "stats": {
                "total_connections_sent": 0,
                "responses_received": 0,
                "interviews_scheduled": 0,
            },
        }
        write_json(history_file, history)

    sizes_file = data_dir / "company-sizes.json"
    if not sizes_file.exists():
        write_json(sizes_file, {"large": [], "startup": []})

    # ---- Done ----
    heading("Setup Complete!")
    print("  Generated files:")
    print(f"    - {CONFIG_DIR / 'profile.json'}")
    print(f"    - {CONFIG_DIR / 'search-criteria.json'}")
    print(f"    - {CONFIG_DIR / 'talking-points.json'}")
    print(f"    - {CONFIG_DIR / 'writing-style.json'}")
    print(f"    - {CLAUDE_MD_PATH}")
    print(f"    - {SKILL_FILE}")
    print()
    print("  Next steps:")
    print(f"    1. Review your config files in {CONFIG_DIR}")
    print(f"    2. Set API keys: export RAPIDAPI_KEY=... (for job fetching)")
    print(f"    3. Install dependencies: pip install -r {PROJECT_DIR / 'requirements.txt'}")
    print(f"    4. Try: /job-search-agent in Claude Code")
    print()


# ---------------------------------------------------------------------------
# Main: --from-config (regenerate CLAUDE.md + skill file)
# ---------------------------------------------------------------------------

def run_from_config():
    """Regenerate CLAUDE.md and skill file from existing config."""
    print()
    print("  Regenerating from existing config...")
    print()

    required_files = [
        ("profile.json", CONFIG_DIR / "profile.json"),
        ("search-criteria.json", CONFIG_DIR / "search-criteria.json"),
        ("talking-points.json", CONFIG_DIR / "talking-points.json"),
        ("writing-style.json", CONFIG_DIR / "writing-style.json"),
    ]

    for name, path in required_files:
        if not path.exists():
            print(f"  Error: Missing config file: {path}")
            print(f"  Run 'python setup.py' (without --from-config) to create it.")
            sys.exit(1)

    profile = load_json(CONFIG_DIR / "profile.json")
    search_criteria = load_json(CONFIG_DIR / "search-criteria.json")
    talking_points = load_json(CONFIG_DIR / "talking-points.json")
    writing_style = load_json(CONFIG_DIR / "writing-style.json")

    # Generate CLAUDE.md
    claude_md_content = generate_claude_md(profile, search_criteria, talking_points, writing_style)
    with open(CLAUDE_MD_PATH, "w") as f:
        f.write(claude_md_content)
    print(f"  Updated: {CLAUDE_MD_PATH}")

    # Generate skill file
    SKILL_DIR.mkdir(parents=True, exist_ok=True)
    skill_content = generate_skill_file(profile)
    with open(SKILL_FILE, "w") as f:
        f.write(skill_content)
    print(f"  Updated: {SKILL_FILE}")

    print()
    print("  Done! CLAUDE.md and skill file regenerated from config.")
    print()


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Job Search Agent - Interactive Setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup.py                  Interactive setup (first time)
  python setup.py --from-config    Regenerate CLAUDE.md from existing config
        """,
    )
    parser.add_argument(
        "--from-config",
        action="store_true",
        help="Regenerate CLAUDE.md and skill file from existing config files",
    )

    args = parser.parse_args()

    if args.from_config:
        run_from_config()
    else:
        run_interactive_setup()


if __name__ == "__main__":
    main()
