"""Tests for scripts/extract_resume_format.py.

Uses ReportLab to generate known-style PDFs as test fixtures, then verifies
that the extractor correctly recovers fonts, sizes, margins, and layout.
"""

import os
import sys
import tempfile
import unittest

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    BaseDocTemplate, Frame, PageTemplate,
)

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "scripts"))

from extract_resume_format import (
    map_font,
    extract_format,
    _color_to_hex,
    _group_chars_into_runs,
    _classify_runs,
    _detect_columns,
)


# ---------------------------------------------------------------------------
# Font mapping tests
# ---------------------------------------------------------------------------

class TestFontMapping(unittest.TestCase):
    def test_strips_subset_prefix(self):
        mapped, original = map_font("ABCDEF+TimesNewRomanPSMT")
        self.assertEqual(mapped, "Times-Roman")
        self.assertEqual(original, "ABCDEF+TimesNewRomanPSMT")

    def test_arial_maps_to_helvetica(self):
        mapped, _ = map_font("ArialMT")
        self.assertEqual(mapped, "Helvetica")

    def test_arial_bold_maps_to_helvetica_bold(self):
        mapped, _ = map_font("Arial-BoldMT")
        self.assertEqual(mapped, "Helvetica-Bold")

    def test_calibri_maps_to_helvetica(self):
        mapped, _ = map_font("Calibri")
        self.assertEqual(mapped, "Helvetica")

    def test_garamond_maps_to_times(self):
        mapped, _ = map_font("Garamond")
        self.assertEqual(mapped, "Times-Roman")

    def test_georgia_bold_maps_to_times_bold(self):
        mapped, _ = map_font("Georgia-Bold")
        self.assertEqual(mapped, "Times-Bold")

    def test_unknown_bold_heuristic(self):
        mapped, _ = map_font("SomeUnknownFont-Bold")
        self.assertEqual(mapped, "Helvetica-Bold")

    def test_unknown_italic_heuristic(self):
        mapped, _ = map_font("SomeUnknownFont-Italic")
        self.assertEqual(mapped, "Helvetica-Oblique")

    def test_unknown_defaults_to_helvetica(self):
        mapped, _ = map_font("CompletelyUnknownFont")
        self.assertEqual(mapped, "Helvetica")

    def test_helvetica_passthrough(self):
        mapped, _ = map_font("Helvetica-Bold")
        self.assertEqual(mapped, "Helvetica-Bold")


# ---------------------------------------------------------------------------
# Color conversion tests
# ---------------------------------------------------------------------------

class TestColorConversion(unittest.TestCase):
    def test_none_returns_black(self):
        self.assertEqual(_color_to_hex(None), "#000000")

    def test_rgb_tuple(self):
        # Full red (1.0, 0, 0) should be #ff0000
        self.assertEqual(_color_to_hex((1.0, 0, 0)), "#ff0000")

    def test_rgb_gray(self):
        self.assertEqual(_color_to_hex((0.5, 0.5, 0.5)), "#7f7f7f")

    def test_grayscale_single(self):
        # Single-value grayscale 0.5 → mid gray
        result = _color_to_hex([0.5])
        self.assertEqual(result, "#7f7f7f")


# ---------------------------------------------------------------------------
# Character grouping tests
# ---------------------------------------------------------------------------

class TestCharGrouping(unittest.TestCase):
    def _make_char(self, text, x0, top, fontname="Helvetica", size=10.0, color=(0, 0, 0)):
        return {
            "text": text,
            "fontname": fontname,
            "size": size,
            "non_stroking_color": color,
            "x0": x0,
            "x1": x0 + 5,
            "top": top,
            "bottom": top + size,
        }

    def test_groups_consecutive_same_style(self):
        chars = [
            self._make_char("H", 0, 0),
            self._make_char("i", 5, 0),
        ]
        runs = _group_chars_into_runs(chars)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["text"], "Hi")

    def test_splits_on_different_font(self):
        chars = [
            self._make_char("H", 0, 0, fontname="Helvetica"),
            self._make_char("i", 5, 0, fontname="Helvetica-Bold"),
        ]
        runs = _group_chars_into_runs(chars)
        self.assertEqual(len(runs), 2)

    def test_splits_on_different_line(self):
        chars = [
            self._make_char("H", 0, 0),
            self._make_char("i", 0, 20),  # different y
        ]
        runs = _group_chars_into_runs(chars)
        self.assertEqual(len(runs), 2)

    def test_handles_empty_input(self):
        self.assertEqual(_group_chars_into_runs([]), [])


# ---------------------------------------------------------------------------
# Style classification tests
# ---------------------------------------------------------------------------

class TestStyleClassification(unittest.TestCase):
    def _run(self, text, fontname="Helvetica", size=10.0, x0=50, x1=150, y0=50, color=(0, 0, 0)):
        return {
            "text": text, "fontname": fontname, "size": size,
            "x0": x0, "x1": x1, "y0": y0, "y1": y0 + size,
            "color": color,
        }

    def test_large_centered_text_is_name_header(self):
        # Page width 612, large font, centered, top of page
        runs = [self._run("Jane Doe", size=18, x0=250, x1=362, y0=40)]
        categories = _classify_runs(runs, page_width=612)
        self.assertIn("name_header", categories)

    def test_all_caps_wide_is_section_header(self):
        runs = [self._run("EXPERIENCE", size=11, x0=50, x1=500, y0=200)]
        categories = _classify_runs(runs, page_width=612)
        self.assertIn("section_header", categories)

    def test_bold_with_date_is_job_title(self):
        runs = [self._run(
            "TechCorp, 2020-Present", fontname="Helvetica-Bold",
            size=10, x0=50, x1=300, y0=250,
        )]
        categories = _classify_runs(runs, page_width=612)
        self.assertIn("job_title", categories)

    def test_bullet_detected(self):
        runs = [self._run("\u2022 Shipped product", x0=50, x1=200, y0=300)]
        categories = _classify_runs(runs, page_width=612)
        self.assertIn("bullet", categories)


# ---------------------------------------------------------------------------
# Column detection tests
# ---------------------------------------------------------------------------

class TestColumnDetection(unittest.TestCase):
    def _run(self, text, x0, x1, y0=100):
        return {
            "text": text, "fontname": "Helvetica", "size": 10.0,
            "x0": x0, "x1": x1, "y0": y0, "y1": y0 + 10,
            "color": (0, 0, 0),
        }

    def test_single_column(self):
        # All runs span similar x-range
        runs = [self._run(f"line {i}", 50, 500, 100 + i * 15) for i in range(20)]
        layout = _detect_columns(runs, page_width=612)
        self.assertEqual(layout["columns"], 1)

    def test_two_column_bimodal(self):
        # Left column around x=50-180, right column around x=250-550
        runs = []
        for i in range(10):
            runs.append(self._run(f"left {i}", 50, 180, 100 + i * 15))
            runs.append(self._run(f"right {i}", 250, 550, 100 + i * 15))
        layout = _detect_columns(runs, page_width=612)
        self.assertEqual(layout["columns"], 2)
        self.assertIsNotNone(layout["column_widths"])


# ---------------------------------------------------------------------------
# Round-trip extraction tests
# ---------------------------------------------------------------------------

def _create_test_pdf(path, font_name="Helvetica-Bold", font_size=16):
    """Create a minimal resume-like PDF for testing extraction."""
    doc = SimpleDocTemplate(
        path, pagesize=letter,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.5 * inch, bottomMargin=0.5 * inch,
    )

    styles = {
        "name": ParagraphStyle(
            "Name", fontName=font_name, fontSize=font_size,
            leading=20, textColor=HexColor("#000000"),
            alignment=TA_CENTER, spaceAfter=4,
        ),
        "contact": ParagraphStyle(
            "Contact", fontName="Helvetica", fontSize=9,
            leading=12, textColor=HexColor("#666666"),
            alignment=TA_CENTER, spaceAfter=8,
        ),
        "section": ParagraphStyle(
            "Section", fontName="Helvetica-Bold", fontSize=11,
            leading=14, textColor=HexColor("#000000"),
            spaceBefore=12, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "Body", fontName="Helvetica", fontSize=10,
            leading=14, textColor=HexColor("#333333"),
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "Bullet", fontName="Helvetica", fontSize=10,
            leading=13, textColor=HexColor("#333333"),
            leftIndent=20, spaceAfter=3,
        ),
    }

    story = [
        Paragraph("JANE DOE", styles["name"]),
        Paragraph("San Francisco &bull; jane@example.com", styles["contact"]),
        Spacer(1, 12),
        HRFlowable(width="100%", thickness=0.5, color=HexColor("#2563EB")),
        Paragraph("EXPERIENCE", styles["section"]),
        Paragraph("TechCorp, Senior PM  2020-Present", styles["body"]),
        Paragraph("\u2022 Shipped AI product reaching 1M users", styles["bullet"]),
        Paragraph("\u2022 Led team of 5 engineers", styles["bullet"]),
        Paragraph("EDUCATION", styles["section"]),
        Paragraph("Stanford University, MBA", styles["body"]),
    ]
    doc.build(story)


class TestRoundTripExtraction(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.pdf_path = os.path.join(self.tmpdir, "test-resume.pdf")
        _create_test_pdf(self.pdf_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_extraction_returns_profile(self):
        profile = extract_format(self.pdf_path)
        self.assertIn("page_size", profile)
        self.assertIn("margins", profile)
        self.assertIn("styles", profile)
        self.assertIn("layout", profile)
        self.assertIn("fonts_used", profile)
        self.assertIn("bullet", profile)

    def test_page_size_is_letter(self):
        profile = extract_format(self.pdf_path)
        # US Letter = 612 x 792
        self.assertAlmostEqual(profile["page_size"][0], 612, delta=1)
        self.assertAlmostEqual(profile["page_size"][1], 792, delta=1)

    def test_detects_single_column(self):
        profile = extract_format(self.pdf_path)
        self.assertEqual(profile["layout"]["columns"], 1)

    def test_detects_helvetica_family(self):
        profile = extract_format(self.pdf_path)
        fonts = [f["mapped"] for f in profile["fonts_used"]]
        # At least one variant of Helvetica should be detected
        self.assertTrue(any("Helvetica" in f for f in fonts))

    def test_section_rule_detected(self):
        profile = extract_format(self.pdf_path)
        # The test PDF has an HRFlowable
        self.assertTrue(profile["section_rule"]["enabled"])

    def test_bullet_character_detected(self):
        profile = extract_format(self.pdf_path)
        # We used \u2022 in the test PDF
        self.assertEqual(profile["bullet"]["char"], "\u2022")

    def test_has_all_style_categories(self):
        profile = extract_format(self.pdf_path)
        for key in ["name_header", "contact", "section_header", "body", "bullet"]:
            self.assertIn(key, profile["styles"])


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases(unittest.TestCase):
    def test_nonexistent_file_raises(self):
        with self.assertRaises(Exception):
            extract_format("/nonexistent/path/file.pdf")

    def test_empty_pdf_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = os.path.join(tmp, "empty.pdf")
            # Create an empty PDF (ReportLab allows this)
            doc = SimpleDocTemplate(pdf_path, pagesize=letter)
            try:
                doc.build([Spacer(1, 1)])
            except Exception:
                # If ReportLab can't build empty, just skip
                self.skipTest("Can't build empty PDF")
            with self.assertRaises(ValueError):
                extract_format(pdf_path)


if __name__ == "__main__":
    unittest.main()
