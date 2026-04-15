"""Scan all tracked files for personal data that should not be in a public repo.

Catches: owner's name, work identity, real email addresses, personal file paths,
large embedded data blobs in HTML, and real LinkedIn profile URLs.

Run: python -m unittest tests.test_no_pii -v
"""

import os
import re
import subprocess
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# Binary extensions to skip (can't meaningfully scan images/fonts)
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".pdf", ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".gz", ".tar", ".pyc",
}

# Known test fixture LinkedIn slugs (not real people)
ALLOWED_LINKEDIN_SLUGS = {
    "alice", "janedoe", "alexrivera", "samchen", "jordanpatel", "lauren",
}

# Max allowed single-line length in HTML files (bytes).
# Lines longer than this usually indicate hardcoded JSON data blobs.
MAX_HTML_LINE_LENGTH = 10_000


def _tracked_text_files():
    """Return paths of all git-tracked text files relative to project root."""
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    files = []
    for name in result.stdout.strip().splitlines():
        if Path(name).suffix.lower() in BINARY_EXTENSIONS:
            continue
        full = PROJECT_ROOT / name
        if full.is_file():
            files.append((name, full))
    return files


def _scan(pattern, exclude_patterns=None):
    """Scan all tracked text files for a regex pattern.

    Returns list of (filename, line_number, line_text) tuples for violations.
    """
    exclude_patterns = exclude_patterns or []
    violations = []
    for name, path in _tracked_text_files():
        try:
            text = path.read_text(errors="replace")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                if any(ep.search(line) for ep in exclude_patterns):
                    continue
                violations.append((name, i, line.strip()[:120]))
    return violations


class TestNoPII(unittest.TestCase):
    """Ensure no personal data leaks into tracked files."""

    def test_no_owner_name(self):
        """No 'viviana' in tracked files (except GitHub username references)."""
        pattern = re.compile(r"viviana", re.IGNORECASE)
        excludes = [
            re.compile(r"viviana-nieto", re.IGNORECASE),
            re.compile(r"github\.com", re.IGNORECASE),
        ]
        violations = _scan(pattern, excludes)
        if violations:
            msg = "Owner name 'viviana' found in tracked files:\n"
            for f, ln, text in violations:
                msg += f"  {f}:{ln}: {text}\n"
            self.fail(msg)

    def test_no_work_identity(self):
        """No work company references (felixvita, felix vita)."""
        pattern = re.compile(r"felix\s*vita", re.IGNORECASE)
        violations = _scan(pattern)
        if violations:
            msg = "Work identity found in tracked files:\n"
            for f, ln, text in violations:
                msg += f"  {f}:{ln}: {text}\n"
            self.fail(msg)

    def test_no_real_emails(self):
        """No real email addresses (only @example.com allowed)."""
        pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        excludes = [
            re.compile(r"@example\.com"),
            re.compile(r"noreply@"),
        ]
        violations = _scan(pattern, excludes)
        if violations:
            msg = "Real email addresses found in tracked files:\n"
            for f, ln, text in violations:
                msg += f"  {f}:{ln}: {text}\n"
            self.fail(msg)

    def test_no_personal_paths(self):
        """No hardcoded personal file paths."""
        pattern = re.compile(r"/Users/viviana/")
        violations = _scan(pattern)
        if violations:
            msg = "Personal file paths found in tracked files:\n"
            for f, ln, text in violations:
                msg += f"  {f}:{ln}: {text}\n"
            self.fail(msg)

    def test_no_embedded_data_blobs_in_html(self):
        """No HTML file has a single line > 10KB (indicates hardcoded data)."""
        violations = []
        for name, path in _tracked_text_files():
            if not name.endswith(".html"):
                continue
            try:
                lines = path.read_text(errors="replace").splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines, 1):
                if len(line) > MAX_HTML_LINE_LENGTH:
                    violations.append(
                        (name, i, f"line is {len(line):,} chars (max {MAX_HTML_LINE_LENGTH:,})")
                    )
        if violations:
            msg = "Large data blobs found in HTML files:\n"
            for f, ln, text in violations:
                msg += f"  {f}:{ln}: {text}\n"
            self.fail(msg)

    def test_no_real_linkedin_profiles(self):
        """LinkedIn profile URLs only use known test fixture names."""
        pattern = re.compile(r"linkedin\.com/in/([a-z][a-z0-9-]+)")
        violations = []
        for name, path in _tracked_text_files():
            try:
                text = path.read_text(errors="replace")
            except Exception:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                for match in pattern.finditer(line):
                    slug = match.group(1)
                    if slug not in ALLOWED_LINKEDIN_SLUGS:
                        violations.append((name, i, f"linkedin.com/in/{slug}"))
        if violations:
            msg = "Real LinkedIn profile URLs found in tracked files:\n"
            for f, ln, text in violations:
                msg += f"  {f}:{ln}: {text}\n"
            self.fail(msg)


if __name__ == "__main__":
    unittest.main()
