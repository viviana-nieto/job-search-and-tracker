#!/usr/bin/env python3
"""Extract visual format from a PDF resume and save as a reusable format profile.

The format profile captures fonts, sizes, colors, margins, spacing, bullet style,
section dividers, and column layout so that generate_pdf.py can reproduce the
original resume's visual design with different content.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

import pdfplumber

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_loader import CONFIG_DIR

PROJECT_DIR = os.environ.get(
    "JOB_SEARCH_DIR",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)

# ---------------------------------------------------------------------------
# Font mapping: PDF internal names → ReportLab built-in names
# ---------------------------------------------------------------------------

_FONT_MAP = {
    # Times family
    "timesnewromanpsmt": "Times-Roman",
    "timesnewromanps-boldmt": "Times-Bold",
    "timesnewromanps-italicmt": "Times-Italic",
    "timesnewromanps-bolditalicmt": "Times-BoldItalic",
    "times-roman": "Times-Roman",
    "times-bold": "Times-Bold",
    "times-italic": "Times-Italic",
    "times-bolditalic": "Times-BoldItalic",
    "garamond": "Times-Roman",
    "garamond-bold": "Times-Bold",
    "garamond-italic": "Times-Italic",
    "georgia": "Times-Roman",
    "georgia-bold": "Times-Bold",
    "georgia-italic": "Times-Italic",
    "cambria": "Times-Roman",
    "cambria-bold": "Times-Bold",
    # Helvetica / sans-serif family
    "arialmt": "Helvetica",
    "arial-boldmt": "Helvetica-Bold",
    "arial-italicmt": "Helvetica-Oblique",
    "arial-bolditalicmt": "Helvetica-BoldOblique",
    "arial": "Helvetica",
    "arial-bold": "Helvetica-Bold",
    "arial-italic": "Helvetica-Oblique",
    "helvetica": "Helvetica",
    "helvetica-bold": "Helvetica-Bold",
    "helvetica-oblique": "Helvetica-Oblique",
    "helvetica-boldoblique": "Helvetica-BoldOblique",
    "helveticaneue": "Helvetica",
    "helveticaneue-bold": "Helvetica-Bold",
    "helveticaneue-italic": "Helvetica-Oblique",
    "calibri": "Helvetica",
    "calibri-bold": "Helvetica-Bold",
    "calibri-italic": "Helvetica-Oblique",
    "calibri-light": "Helvetica",
    "verdana": "Helvetica",
    "verdana-bold": "Helvetica-Bold",
    "segoeui": "Helvetica",
    "segoeui-bold": "Helvetica-Bold",
    "segoeui-italic": "Helvetica-Oblique",
    "opensans": "Helvetica",
    "opensans-bold": "Helvetica-Bold",
    "opensans-italic": "Helvetica-Oblique",
    "lato": "Helvetica",
    "lato-bold": "Helvetica-Bold",
    "lato-italic": "Helvetica-Oblique",
    "roboto": "Helvetica",
    "roboto-bold": "Helvetica-Bold",
    "roboto-italic": "Helvetica-Oblique",
    # Courier / monospace family
    "couriernewpsmt": "Courier",
    "couriernewps-boldmt": "Courier-Bold",
    "couriernewps-italicmt": "Courier-Oblique",
    "courier": "Courier",
    "courier-bold": "Courier-Bold",
    "courier-oblique": "Courier-Oblique",
    "consolas": "Courier",
    "consolas-bold": "Courier-Bold",
}


def map_font(pdf_font_name):
    """Map a PDF font name to the closest ReportLab built-in font.

    Strips the random subset prefix (e.g. 'ABCDEF+') and normalises casing
    before looking up in the substitution table.
    """
    original = pdf_font_name
    # Strip subset prefix
    if "+" in pdf_font_name:
        pdf_font_name = pdf_font_name.split("+", 1)[1]

    key = pdf_font_name.lower().replace(" ", "").replace("-", "")

    # Direct lookup (exact after normalisation)
    if key in _FONT_MAP:
        return _FONT_MAP[key], original

    # Try with hyphenated form
    key_hyphen = pdf_font_name.lower().replace(" ", "-")
    if key_hyphen in _FONT_MAP:
        return _FONT_MAP[key_hyphen], original

    # Partial match: check if any map key is a prefix
    for map_key, mapped in _FONT_MAP.items():
        if key.startswith(map_key):
            return mapped, original

    # Heuristic: bold/italic detection in unknown fonts
    lower = pdf_font_name.lower()
    if "bold" in lower and "italic" in lower:
        return "Helvetica-BoldOblique", original
    if "bold" in lower:
        return "Helvetica-Bold", original
    if "italic" in lower or "oblique" in lower:
        return "Helvetica-Oblique", original

    # Default fallback
    return "Helvetica", original


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def _color_to_hex(color):
    """Convert a pdfplumber color value to a hex string."""
    if color is None:
        return "#000000"
    if isinstance(color, (list, tuple)):
        if len(color) == 1:
            # Grayscale
            v = int(color[0] * 255) if isinstance(color[0], float) and color[0] <= 1.0 else int(color[0])
            return f"#{v:02x}{v:02x}{v:02x}"
        if len(color) == 3:
            # RGB
            rgb = []
            for c in color:
                v = int(c * 255) if isinstance(c, float) and c <= 1.0 else int(c)
                rgb.append(max(0, min(255, v)))
            return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        if len(color) == 4:
            # CMYK → approximate RGB
            c_, m_, y_, k_ = color
            r = int(255 * (1 - c_) * (1 - k_))
            g = int(255 * (1 - m_) * (1 - k_))
            b = int(255 * (1 - y_) * (1 - k_))
            return f"#{r:02x}{g:02x}{b:02x}"
    return "#000000"


# ---------------------------------------------------------------------------
# Text run grouping
# ---------------------------------------------------------------------------

def _group_chars_into_runs(chars, y_tolerance=1.5):
    """Group characters into text runs sharing the same line, font, size, and color."""
    if not chars:
        return []

    runs = []
    current = {
        "text": chars[0]["text"],
        "fontname": chars[0]["fontname"],
        "size": round(chars[0]["size"], 1),
        "color": chars[0].get("non_stroking_color"),
        "x0": chars[0]["x0"],
        "x1": chars[0]["x1"],
        "y0": chars[0]["top"],
        "y1": chars[0]["bottom"],
    }

    for ch in chars[1:]:
        same_line = abs(ch["top"] - current["y0"]) < y_tolerance
        same_font = ch["fontname"] == current["fontname"]
        same_size = abs(ch["size"] - current["size"]) < 0.3
        same_color = ch.get("non_stroking_color") == current["color"]

        if same_line and same_font and same_size and same_color:
            current["text"] += ch["text"]
            current["x1"] = max(current["x1"], ch["x1"])
        else:
            runs.append(current)
            current = {
                "text": ch["text"],
                "fontname": ch["fontname"],
                "size": round(ch["size"], 1),
                "color": ch.get("non_stroking_color"),
                "x0": ch["x0"],
                "x1": ch["x1"],
                "y0": ch["top"],
                "y1": ch["bottom"],
            }

    runs.append(current)
    return runs


# ---------------------------------------------------------------------------
# Style classification
# ---------------------------------------------------------------------------

_DATE_PATTERN = re.compile(
    r"(20[12]\d|19\d\d|Present|Current|Ongoing)", re.IGNORECASE
)
_BULLET_CHARS = set("\u2022\u25cf\u25cb\u25aa\u25a0\u2013\u2014-\u2023\u25b8")


def _classify_runs(runs, page_width):
    """Classify text runs into style categories and collect representative properties."""
    categories = defaultdict(list)

    for run in runs:
        text = run["text"].strip()
        if not text:
            continue

        size = run["size"]
        fontname = run["fontname"].lower()
        is_bold = "bold" in fontname
        x_center = (run["x0"] + run["x1"]) / 2
        is_centered = abs(x_center - page_width / 2) < page_width * 0.15
        span_width = run["x1"] - run["x0"]
        is_wide = span_width > page_width * 0.5

        # Classify
        if size >= 14 and is_centered and run["y0"] < 80:
            categories["name_header"].append(run)
        elif size <= 10 and is_centered and run["y0"] < 120:
            categories["contact"].append(run)
        elif (text.isupper() and len(text) > 3 and is_wide) or (is_bold and size >= 11 and is_wide):
            categories["section_header"].append(run)
        elif is_bold and _DATE_PATTERN.search(text):
            categories["job_title"].append(run)
        elif not is_bold and _DATE_PATTERN.search(text) and size <= 10:
            categories["job_meta"].append(run)
        elif text[0] in _BULLET_CHARS:
            categories["bullet"].append(run)
        else:
            categories["body"].append(run)

    return categories


def _average_style(runs, page_width):
    """Compute average style properties from a list of runs."""
    if not runs:
        return None

    sizes = [r["size"] for r in runs]
    avg_size = round(sum(sizes) / len(sizes), 1)

    # Most common font
    font_counter = Counter(r["fontname"] for r in runs)
    most_common_font = font_counter.most_common(1)[0][0]
    mapped_font, _ = map_font(most_common_font)

    # Most common color
    color_counter = Counter(
        _color_to_hex(r["color"]) for r in runs
    )
    most_common_color = color_counter.most_common(1)[0][0]

    # Alignment detection
    centers = [(r["x0"] + r["x1"]) / 2 for r in runs]
    avg_center = sum(centers) / len(centers)
    is_centered = abs(avg_center - page_width / 2) < page_width * 0.1

    lefts = [r["x0"] for r in runs]
    avg_left = sum(lefts) / len(lefts)

    # Leading (approximate from average size)
    leading = round(avg_size * 1.25, 1)

    # Space detection from y-gaps
    space_after = round(avg_size * 0.4, 1)

    # Text transform
    texts = [r["text"].strip() for r in runs if r["text"].strip()]
    all_upper = all(t.isupper() for t in texts) if texts else False

    style = {
        "font": mapped_font,
        "size": avg_size,
        "color": most_common_color,
        "alignment": "center" if is_centered else "left",
        "leading": leading,
        "space_after": space_after,
    }

    if all_upper:
        style["text_transform"] = "uppercase"

    if avg_left > 30:
        style["left_indent"] = round(avg_left - min(lefts), 1) if len(set(int(l) for l in lefts)) > 1 else 0

    return style


# ---------------------------------------------------------------------------
# Column detection
# ---------------------------------------------------------------------------

def _detect_columns(runs, page_width):
    """Detect whether the layout is single or multi-column.

    Returns a layout dict with columns, column_gap, and column_widths.
    """
    if not runs:
        return {"columns": 1, "column_gap": None, "column_widths": None}

    # Collect x-centers of all runs (excluding very short runs like bullets)
    x_centers = []
    for r in runs:
        if len(r["text"].strip()) > 2:
            x_centers.append((r["x0"] + r["x1"]) / 2)

    if len(x_centers) < 10:
        return {"columns": 1, "column_gap": None, "column_widths": None}

    # Look for a gap in x0 positions that suggests a column boundary
    x_starts = sorted(set(round(r["x0"]) for r in runs if len(r["text"].strip()) > 2))

    # Find the largest gap between consecutive x-start positions
    max_gap = 0
    gap_position = 0
    for i in range(1, len(x_starts)):
        gap = x_starts[i] - x_starts[i - 1]
        if gap > max_gap:
            max_gap = gap
            gap_position = (x_starts[i - 1] + x_starts[i]) / 2

    # If the gap is significant (>15% of page width) and the boundary is
    # away from the edges, it's likely a 2-column layout
    if max_gap > page_width * 0.08 and page_width * 0.15 < gap_position < page_width * 0.85:
        # Count runs on each side
        left_count = sum(1 for r in runs if (r["x0"] + r["x1"]) / 2 < gap_position)
        right_count = sum(1 for r in runs if (r["x0"] + r["x1"]) / 2 >= gap_position)

        if left_count > 5 and right_count > 5:
            left_width = round(gap_position / page_width, 2)
            right_width = round(1 - left_width, 2)
            return {
                "columns": 2,
                "column_gap": round(max_gap, 1),
                "column_widths": [left_width, right_width],
            }

    return {"columns": 1, "column_gap": None, "column_widths": None}


# ---------------------------------------------------------------------------
# Line / rule detection
# ---------------------------------------------------------------------------

def _detect_section_rules(page):
    """Detect horizontal lines used as section dividers."""
    lines = page.lines or []
    rects = page.rects or []

    # Horizontal lines (y0 ≈ y1)
    h_lines = [l for l in lines if abs(l["top"] - l["bottom"]) < 2]
    # Thin horizontal rects
    h_rects = [r for r in rects if abs(r["top"] - r["bottom"]) < 3 and (r["x1"] - r["x0"]) > 100]

    all_rules = h_lines + h_rects
    if not all_rules:
        return {"enabled": False, "color": "#000000", "thickness": 0.5, "position": "below_header"}

    # Get the most common color from rules
    colors = []
    for rule in all_rules:
        color = rule.get("stroking_color") or rule.get("non_stroking_color")
        colors.append(_color_to_hex(color))

    color_counter = Counter(colors)
    most_common_color = color_counter.most_common(1)[0][0]

    # Average thickness
    thicknesses = []
    for rule in all_rules:
        if "linewidth" in rule:
            thicknesses.append(rule["linewidth"])
        elif abs(rule.get("top", 0) - rule.get("bottom", 0)) > 0:
            thicknesses.append(abs(rule["top"] - rule["bottom"]))
        else:
            thicknesses.append(0.5)
    avg_thickness = round(sum(thicknesses) / len(thicknesses), 1) if thicknesses else 0.5

    return {
        "enabled": True,
        "color": most_common_color,
        "thickness": max(0.5, min(avg_thickness, 3.0)),
        "position": "below_header",
    }


# ---------------------------------------------------------------------------
# Bullet detection
# ---------------------------------------------------------------------------

def _detect_bullet_style(runs):
    """Detect the bullet character and indentation used."""
    bullet_runs = [r for r in runs if r["text"].strip() and r["text"].strip()[0] in _BULLET_CHARS]
    if not bullet_runs:
        return {"char": "\u2022", "indent": 20, "hanging_indent": 8}

    # Most common bullet character
    chars = Counter(r["text"].strip()[0] for r in bullet_runs)
    bullet_char = chars.most_common(1)[0][0]

    # Average indent
    indents = [r["x0"] for r in bullet_runs]
    avg_indent = round(sum(indents) / len(indents), 1)

    return {
        "char": bullet_char,
        "indent": round(avg_indent),
        "hanging_indent": 8,
    }


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def extract_format(pdf_path):
    """Extract the visual format profile from a PDF resume.

    Returns a dict suitable for JSON serialisation.
    """
    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            raise ValueError(f"PDF has no pages: {pdf_path}")

        first_page = pdf.pages[0]
        page_width = first_page.width
        page_height = first_page.height

        # Collect all characters and runs across pages
        all_runs = []
        section_rule = {"enabled": False, "color": "#000000", "thickness": 0.5, "position": "below_header"}

        for page in pdf.pages:
            chars = page.chars
            if not chars:
                continue
            runs = _group_chars_into_runs(chars)
            all_runs.extend(runs)

            # Detect section rules from first page only
            if page == first_page:
                section_rule = _detect_section_rules(page)

    if not all_runs:
        raise ValueError(f"No text content found in PDF: {pdf_path}")

    # Compute margins
    all_x0 = [r["x0"] for r in all_runs]
    all_x1 = [r["x1"] for r in all_runs]
    all_y0 = [r["y0"] for r in all_runs]
    all_y1 = [r["y1"] for r in all_runs]

    margins = {
        "top": round(min(all_y0)),
        "bottom": round(page_height - max(all_y1)),
        "left": round(min(all_x0)),
        "right": round(page_width - max(all_x1)),
    }

    # Classify runs into style categories
    categories = _classify_runs(all_runs, page_width)

    # Build styles from each category
    styles = {}
    style_defaults = {
        "name_header": {"font": "Helvetica-Bold", "size": 16.0, "color": "#000000", "alignment": "center", "leading": 20.0, "space_after": 4.0},
        "contact": {"font": "Helvetica", "size": 9.0, "color": "#999999", "alignment": "center", "leading": 12.0, "space_after": 8.0},
        "section_header": {"font": "Helvetica-Bold", "size": 11.0, "color": "#000000", "alignment": "left", "leading": 14.0, "space_before": 12.0, "space_after": 4.0},
        "job_title": {"font": "Helvetica-Bold", "size": 10.0, "color": "#000000", "alignment": "left", "leading": 13.0, "space_after": 1.0},
        "job_meta": {"font": "Helvetica", "size": 9.0, "color": "#999999", "alignment": "left", "leading": 12.0, "space_after": 4.0},
        "body": {"font": "Helvetica", "size": 10.0, "color": "#333333", "alignment": "left", "leading": 14.0, "space_after": 6.0},
        "bullet": {"font": "Helvetica", "size": 10.0, "color": "#333333", "alignment": "left", "leading": 13.0, "space_after": 3.0, "left_indent": 20, "bullet_indent": 8},
    }

    for cat_name, default in style_defaults.items():
        computed = _average_style(categories.get(cat_name, []), page_width)
        if computed:
            # Merge computed values over defaults
            merged = {**default, **computed}
            styles[cat_name] = merged
        else:
            styles[cat_name] = default

    # Detect fonts used
    font_counter = Counter(r["fontname"] for r in all_runs)
    fonts_used = []
    seen = set()
    for fontname, _ in font_counter.most_common():
        mapped, original = map_font(fontname)
        if original not in seen:
            fonts_used.append({"original": original, "mapped": mapped})
            seen.add(original)

    # Detect column layout
    layout = _detect_columns(all_runs, page_width)

    # Detect bullet style
    bullet = _detect_bullet_style(all_runs)

    profile = {
        "page_size": [round(page_width, 1), round(page_height, 1)],
        "margins": margins,
        "fonts_used": fonts_used,
        "styles": styles,
        "section_rule": section_rule,
        "layout": layout,
        "bullet": bullet,
    }

    return profile


def extract_and_save(pdf_path, output_path=None):
    """Extract format profile and save to JSON."""
    if output_path is None:
        output_path = os.path.join(str(CONFIG_DIR), "resume-format.json")

    profile = extract_format(pdf_path)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

    # Print summary
    body_font = profile["styles"]["body"]["font"]
    body_size = profile["styles"]["body"]["size"]
    cols = profile["layout"]["columns"]
    rule = "with" if profile["section_rule"]["enabled"] else "without"
    print(f"Format extracted: {body_font} {body_size}pt, {cols}-column layout, {rule} section dividers")
    print(f"Saved to: {output_path}")

    return profile


def main():
    parser = argparse.ArgumentParser(
        description="Extract visual format from a PDF resume"
    )
    parser.add_argument(
        "--input", required=True, help="Path to the PDF resume"
    )
    parser.add_argument(
        "--output", default=None,
        help="Output path for format profile JSON (default: config/resume-format.json)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    extract_and_save(args.input, args.output)


if __name__ == "__main__":
    main()
