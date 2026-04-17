#!/usr/bin/env python3
"""Load user configuration from config/ directory. All scripts import this module."""

import json
import os
import re
from pathlib import Path

PROJECT_DIR = Path(os.environ.get("JOB_SEARCH_DIR", Path(__file__).parent.parent))
CONFIG_DIR = PROJECT_DIR / "config"


def _load_json(filename):
    filepath = CONFIG_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(
            f"Config file not found: {filepath}\n"
            f"Run 'python setup.py' to create your configuration."
        )
    with open(filepath) as f:
        return json.load(f)


def load_profile():
    """Load user profile (name, contact, career, skills, education)."""
    return _load_json("profile.json")


def load_search_criteria():
    """Load job search criteria (roles, companies, industries, locations)."""
    return _load_json("search-criteria.json")


def load_talking_points():
    """Load talking points organized by industry/context."""
    return _load_json("talking-points.json")


def load_writing_style():
    """Load writing style rules and preferences."""
    return _load_json("writing-style.json")


def get_contact():
    """Return contact info dict from profile."""
    profile = load_profile()
    return profile.get("contact", {})


def get_name():
    """Return the user's full name."""
    profile = load_profile()
    return profile.get("name", "")


def get_first_name():
    """Return the user's first name."""
    return get_name().split()[0] if get_name() else ""


def get_languages():
    """Return list of supported languages from profile."""
    profile = load_profile()
    return profile.get("languages", ["en"])


def get_default_language():
    """Return default language."""
    profile = load_profile()
    return profile.get("default_language", "en")


def get_resume_path():
    """Return the path to the user's base resume."""
    profile = load_profile()
    return profile.get("resume_path", "")


def get_sign_off(context="linkedin", language=None):
    """Return the appropriate sign-off for a given context.

    Supports both flat and nested sign_offs structures:
      Flat:   {"linkedin": "~Jane", "email": "Best,"}
      Nested: {"en": {"linkedin": "~Jane"}, "es": {"linkedin": "~Jane"}}
    """
    style = load_writing_style()
    sign_offs = style.get("sign_offs", {})

    # Detect nested structure: if any top-level value is a dict, it's nested
    is_nested = any(isinstance(v, dict) for v in sign_offs.values())

    if is_nested:
        if language is None:
            language = get_default_language()
        lang_sign_offs = sign_offs.get(language, sign_offs.get("en", {}))
        return lang_sign_offs.get(context, lang_sign_offs.get("default", f"~{get_first_name()}"))

    # Flat structure (backwards-compatible)
    return sign_offs.get(context, sign_offs.get("default", f"~{get_first_name()}"))


def load_template(template_name, language=None):
    """Load a template file for the given language.

    Falls back to default_language, then to 'en'.
    """
    if language is None:
        language = get_default_language()
    template_dir = PROJECT_DIR / "templates" / language
    if not template_dir.exists():
        template_dir = PROJECT_DIR / "templates" / "en"
    filepath = template_dir / f"{template_name}.md"
    with open(filepath) as f:
        return f.read()


def get_credibility(length="short"):
    """Return a credibility snippet (short, medium, or long)."""
    profile = load_profile()
    creds = profile.get("credibility", {})
    return creds.get(length, creds.get("short", ""))


def get_filename_prefix():
    """Return the filename prefix for PDFs (e.g., 'LastFirst_Name')."""
    profile = load_profile()
    return profile.get("filename_prefix", "")


def get_pm_phrase(company_size):
    """Return the PM phrasing for a given company size."""
    style = load_writing_style()
    phrases = style.get("pm_phrases", {"startup": "PM", "large": "PM", "unknown": "PM"})
    return phrases.get(company_size, phrases.get("unknown", "PM"))


def get_default_keywords():
    """Return default search keywords from search criteria."""
    criteria = load_search_criteria()
    queries = criteria.get("search_queries", {})
    return queries.get("high_priority", []) + queries.get("medium_priority", [])


def get_default_locations():
    """Return default search locations from search criteria."""
    criteria = load_search_criteria()
    locations = criteria.get("locations", {})
    preferred = locations.get("preferred", [])
    acceptable = locations.get("acceptable", [])
    # Return first preferred + "Remote" if acceptable
    result = preferred[:2] if preferred else ["San Francisco Bay Area"]
    if any("remote" in loc.lower() for loc in acceptable):
        result.append("Remote")
    return result


def render_template(template_str, extra_vars=None, language=None):
    """Replace {{placeholder}} patterns in a template string with config values.

    Built-in variables:
        {{name}}, {{first_name}}, {{title}}, {{email}}, {{phone}}, {{website}},
        {{location}}, {{sign_off_linkedin}}, {{sign_off_email}},
        {{cred_short}}, {{cred_medium}}, {{cred_long}}

    Extra variables can be passed as a dict.
    Language can be specified for language-aware sign-offs.
    """
    profile = load_profile()
    contact = profile.get("contact", {})

    variables = {
        "name": profile.get("name", ""),
        "first_name": get_first_name(),
        "title": profile.get("title", ""),
        "email": contact.get("email", ""),
        "phone": contact.get("phone", ""),
        "website": contact.get("website", ""),
        "location": contact.get("location", ""),
        "sign_off_linkedin": get_sign_off("linkedin", language=language),
        "sign_off_email": get_sign_off("email", language=language),
        "sign_off_formal": get_sign_off("formal", language=language),
        "cred_short": get_credibility("short"),
        "cred_medium": get_credibility("medium"),
        "cred_long": get_credibility("long"),
    }

    if extra_vars:
        variables.update(extra_vars)

    def replacer(match):
        key = match.group(1).strip()
        return variables.get(key, match.group(0))

    return re.sub(r'\{\{(.+?)\}\}', replacer, template_str)


def load_resume_format():
    """Load resume format profile, or None if not extracted yet."""
    path = CONFIG_DIR / "resume-format.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def is_configured():
    """Check if the project has been configured (profile.json exists)."""
    return (CONFIG_DIR / "profile.json").exists()
