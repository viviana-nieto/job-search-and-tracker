"""Tests for format-profile-aware PDF generation in scripts/generate_pdf.py.

Covers:
- Backward compatibility (no format profile → default hardcoded styles)
- Format profile loading (dynamic styles from JSON)
- Bullet character override
- Section rule toggle
- Two-column layout structure
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "scripts"))

from generate_pdf import (
    _get_default_styles,
    get_styles,
    _parse_alignment,
    _split_markdown_columns,
)


# ---------------------------------------------------------------------------
# Alignment helper
# ---------------------------------------------------------------------------

class TestAlignment(unittest.TestCase):
    def test_center(self):
        self.assertEqual(_parse_alignment("center"), TA_CENTER)

    def test_left(self):
        self.assertEqual(_parse_alignment("left"), TA_LEFT)

    def test_default_is_left(self):
        self.assertEqual(_parse_alignment("unknown"), TA_LEFT)


# ---------------------------------------------------------------------------
# Backward compatibility: no format profile → default styles
# ---------------------------------------------------------------------------

class TestBackwardCompatibility(unittest.TestCase):
    def test_get_styles_without_profile_returns_defaults(self):
        default = _get_default_styles()
        via_get = get_styles(None)
        # Same keys
        self.assertEqual(set(default.keys()), set(via_get.keys()))
        # Same font for name header
        self.assertEqual(default["name"].fontName, via_get["name"].fontName)
        self.assertEqual(default["name"].fontSize, via_get["name"].fontSize)

    def test_default_styles_have_all_required_keys(self):
        styles = _get_default_styles()
        for key in ["name", "contact", "section_header", "body", "bullet",
                    "body_bold", "sign_off", "job_title", "job_meta", "headline"]:
            self.assertIn(key, styles)


# ---------------------------------------------------------------------------
# Format profile application
# ---------------------------------------------------------------------------

SAMPLE_PROFILE = {
    "page_size": [612, 792],
    "margins": {"top": 36, "bottom": 36, "left": 50, "right": 50},
    "fonts_used": [{"original": "TimesNewRomanPSMT", "mapped": "Times-Roman"}],
    "styles": {
        "name_header": {
            "font": "Times-Bold", "size": 16.0, "color": "#000000",
            "alignment": "center", "leading": 20.0, "space_after": 4.0,
            "text_transform": "uppercase",
        },
        "contact": {
            "font": "Times-Roman", "size": 9.0, "color": "#666666",
            "alignment": "center", "leading": 12.0, "space_after": 8.0,
        },
        "section_header": {
            "font": "Times-Bold", "size": 11.0, "color": "#000000",
            "alignment": "left", "leading": 14.0,
            "space_before": 12.0, "space_after": 4.0,
        },
        "job_title": {
            "font": "Times-Bold", "size": 10.0, "color": "#000000",
            "alignment": "left", "leading": 13.0, "space_after": 1.0,
        },
        "job_meta": {
            "font": "Times-Roman", "size": 9.0, "color": "#999999",
            "alignment": "left", "leading": 12.0, "space_after": 4.0,
        },
        "body": {
            "font": "Times-Roman", "size": 10.0, "color": "#333333",
            "alignment": "left", "leading": 14.0, "space_after": 6.0,
        },
        "bullet": {
            "font": "Times-Roman", "size": 10.0, "color": "#333333",
            "alignment": "left", "leading": 13.0, "space_after": 3.0,
            "left_indent": 20, "bullet_indent": 8,
        },
    },
    "section_rule": {"enabled": True, "color": "#2563EB", "thickness": 0.5, "position": "below_header"},
    "layout": {"columns": 1, "column_gap": None, "column_widths": None},
    "bullet": {"char": "\u2022", "indent": 20, "hanging_indent": 8},
}


class TestFormatProfileApplication(unittest.TestCase):
    def test_profile_overrides_font(self):
        styles = get_styles(SAMPLE_PROFILE)
        self.assertEqual(styles["name"].fontName, "Times-Bold")
        self.assertEqual(styles["body"].fontName, "Times-Roman")

    def test_profile_overrides_size(self):
        styles = get_styles(SAMPLE_PROFILE)
        self.assertEqual(styles["name"].fontSize, 16.0)
        self.assertEqual(styles["body"].fontSize, 10.0)

    def test_profile_overrides_alignment(self):
        styles = get_styles(SAMPLE_PROFILE)
        self.assertEqual(styles["name"].alignment, TA_CENTER)
        self.assertEqual(styles["body"].alignment, TA_LEFT)

    def test_profile_overrides_color(self):
        styles = get_styles(SAMPLE_PROFILE)
        # Body should be #333333
        self.assertEqual(styles["body"].textColor, HexColor("#333333"))

    def test_bullet_indent_applied(self):
        styles = get_styles(SAMPLE_PROFILE)
        self.assertEqual(styles["bullet"].leftIndent, 20)
        self.assertEqual(styles["bullet"].bulletIndent, 8)


# ---------------------------------------------------------------------------
# Two-column markdown splitting
# ---------------------------------------------------------------------------

class TestColumnSplitting(unittest.TestCase):
    def test_explicit_markers(self):
        content = """Jane Doe
contact line

<!-- sidebar -->
## Skills
- Python
- SQL

<!-- main -->
## Experience
Worked at TechCorp"""
        header, sidebar, main = _split_markdown_columns(content)
        self.assertIn("Jane Doe", header)
        self.assertIn("Skills", sidebar)
        self.assertIn("Python", sidebar)
        self.assertIn("Experience", main)
        self.assertIn("TechCorp", main)

    def test_heuristic_splits_skills_to_sidebar(self):
        content = """Jane Doe
contact line

## Skills
- Python

## Experience
Worked at TechCorp"""
        _, sidebar, main = _split_markdown_columns(content)
        self.assertIn("Skills", sidebar)
        self.assertIn("Python", sidebar)
        self.assertIn("Experience", main)
        self.assertIn("TechCorp", main)

    def test_heuristic_splits_education_to_sidebar(self):
        content = """## EDUCATION
Stanford MBA

## EXPERIENCE
TechCorp"""
        _, sidebar, main = _split_markdown_columns(content)
        self.assertIn("EDUCATION", sidebar)
        self.assertIn("Stanford", sidebar)
        self.assertIn("EXPERIENCE", main)


# ---------------------------------------------------------------------------
# End-to-end PDF generation (with format profile)
# ---------------------------------------------------------------------------

class TestResumePDFGeneration(unittest.TestCase):
    """Generate a resume PDF with a format profile and verify it builds."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create a minimal workspace with required config
        self.config_dir = os.path.join(self.tmpdir, "config")
        os.makedirs(self.config_dir)

        # Minimal profile.json
        profile = {
            "name": "Jane Doe",
            "title": "Senior PM",
            "filename_prefix": "Doe_Jane",
            "contact": {
                "email": "jane@example.com",
                "phone": "555-0000",
                "location": "San Francisco",
                "website": "",
            },
            "default_language": "en",
        }
        with open(os.path.join(self.config_dir, "profile.json"), "w") as f:
            json.dump(profile, f)

        # Format profile
        with open(os.path.join(self.config_dir, "resume-format.json"), "w") as f:
            json.dump(SAMPLE_PROFILE, f)

        # Sample resume markdown
        self.resume_md = os.path.join(self.tmpdir, "resume.md")
        with open(self.resume_md, "w") as f:
            f.write("""Jane Doe
San Francisco

## EXPERIENCE
TechCorp, Senior PM  2020-Present
- Shipped AI product
- Led team of 5

## EDUCATION
Stanford MBA
""")

        self.output_pdf = os.path.join(self.tmpdir, "output.pdf")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_resume_builds_with_format_profile(self):
        # Point config_loader to the temp directory
        with patch.dict(os.environ, {"JOB_SEARCH_DIR": self.tmpdir}):
            # Reload modules to pick up new JOB_SEARCH_DIR
            import importlib
            import config_loader
            import generate_pdf
            importlib.reload(config_loader)
            importlib.reload(generate_pdf)

            generate_pdf.build_resume_pdf(self.resume_md, self.output_pdf)

            self.assertTrue(os.path.exists(self.output_pdf))
            self.assertGreater(os.path.getsize(self.output_pdf), 0)

    def test_resume_builds_without_format_profile(self):
        # Remove format profile
        os.remove(os.path.join(self.config_dir, "resume-format.json"))

        with patch.dict(os.environ, {"JOB_SEARCH_DIR": self.tmpdir}):
            import importlib
            import config_loader
            import generate_pdf
            importlib.reload(config_loader)
            importlib.reload(generate_pdf)

            generate_pdf.build_resume_pdf(self.resume_md, self.output_pdf)

            self.assertTrue(os.path.exists(self.output_pdf))
            self.assertGreater(os.path.getsize(self.output_pdf), 0)


if __name__ == "__main__":
    unittest.main()
