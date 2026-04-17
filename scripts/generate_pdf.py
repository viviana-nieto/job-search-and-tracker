#!/usr/bin/env python3
"""Generate professional PDFs for cover letters and resumes from markdown files.

When a format profile exists (config/resume-format.json), resume PDFs will
replicate the visual style of the user's original resume.  Without a profile
the hardcoded default styles are used (backward compatible).
"""

import argparse
import json
import os
import re
import sys
from datetime import date

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, ListFlowable, ListItem,
    BaseDocTemplate, Frame, PageTemplate,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_loader import get_contact, get_name, load_profile, get_filename_prefix, load_resume_format

PROJECT_DIR = os.environ.get("JOB_SEARCH_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOWNLOADS_DIR = os.path.expanduser("~/Downloads")

# Colors
DARK = HexColor("#333333")
ACCENT = HexColor("#2563EB")
LIGHT_GRAY = HexColor("#999999")


# ---------------------------------------------------------------------------
# Alignment helper
# ---------------------------------------------------------------------------

_ALIGNMENT_MAP = {"left": TA_LEFT, "center": TA_CENTER}


def _parse_alignment(value):
    return _ALIGNMENT_MAP.get(value, TA_LEFT)


# ---------------------------------------------------------------------------
# Default (hardcoded) styles — original behaviour
# ---------------------------------------------------------------------------

def _get_default_styles():
    """Create the original hardcoded paragraph styles."""
    styles = {}

    styles["name"] = ParagraphStyle(
        "Name", fontName="Helvetica-Bold", fontSize=18,
        leading=22, textColor=DARK, alignment=TA_CENTER,
        spaceAfter=4,
    )
    styles["contact"] = ParagraphStyle(
        "Contact", fontName="Helvetica", fontSize=9,
        leading=12, textColor=LIGHT_GRAY, alignment=TA_CENTER,
        spaceAfter=8,
    )
    styles["headline"] = ParagraphStyle(
        "Headline", fontName="Helvetica", fontSize=9,
        leading=12, textColor=DARK, alignment=TA_CENTER,
        spaceAfter=12,
    )
    styles["section_header"] = ParagraphStyle(
        "SectionHeader", fontName="Helvetica-Bold", fontSize=11,
        leading=14, textColor=DARK, spaceBefore=12, spaceAfter=4,
    )
    styles["body"] = ParagraphStyle(
        "Body", fontName="Helvetica", fontSize=10,
        leading=14, textColor=DARK, spaceAfter=6,
    )
    styles["body_bold"] = ParagraphStyle(
        "BodyBold", fontName="Helvetica-Bold", fontSize=10,
        leading=14, textColor=DARK, spaceAfter=2,
    )
    styles["bullet"] = ParagraphStyle(
        "Bullet", fontName="Helvetica", fontSize=10,
        leading=13, textColor=DARK, leftIndent=20,
        spaceAfter=3, bulletIndent=8,
    )
    styles["sign_off"] = ParagraphStyle(
        "SignOff", fontName="Helvetica", fontSize=10,
        leading=14, textColor=DARK, spaceBefore=16, spaceAfter=2,
    )
    styles["job_title"] = ParagraphStyle(
        "JobTitle", fontName="Helvetica-Bold", fontSize=10,
        leading=13, textColor=DARK, spaceAfter=1,
    )
    styles["job_meta"] = ParagraphStyle(
        "JobMeta", fontName="Helvetica", fontSize=9,
        leading=12, textColor=LIGHT_GRAY, spaceAfter=4,
    )
    return styles


# ---------------------------------------------------------------------------
# Format-profile-aware styles
# ---------------------------------------------------------------------------

def get_styles(format_profile=None):
    """Return paragraph styles, optionally driven by a format profile."""
    if format_profile is None:
        return _get_default_styles()

    fp_styles = format_profile.get("styles", {})
    styles = _get_default_styles()  # start from defaults

    # Map format profile keys → internal style keys
    key_map = {
        "name_header": "name",
        "contact": "contact",
        "section_header": "section_header",
        "job_title": "job_title",
        "job_meta": "job_meta",
        "body": "body",
        "bullet": "bullet",
    }

    for fp_key, style_key in key_map.items():
        fp = fp_styles.get(fp_key)
        if not fp:
            continue
        styles[style_key] = ParagraphStyle(
            style_key,
            fontName=fp.get("font", "Helvetica"),
            fontSize=fp.get("size", 10),
            leading=fp.get("leading", fp.get("size", 10) * 1.25),
            textColor=HexColor(fp.get("color", "#333333")),
            alignment=_parse_alignment(fp.get("alignment", "left")),
            spaceBefore=fp.get("space_before", 0),
            spaceAfter=fp.get("space_after", 0),
            leftIndent=fp.get("left_indent", 0),
            bulletIndent=fp.get("bullet_indent", 0),
        )

    # Derive body_bold from body
    body_fp = fp_styles.get("body", {})
    body_font = body_fp.get("font", "Helvetica")
    bold_font = body_font.replace("-Roman", "-Bold").replace("Helvetica", "Helvetica-Bold")
    if "Bold" not in bold_font:
        bold_font = body_font + "-Bold" if not body_font.endswith("-Bold") else body_font
    # Ensure it's a valid ReportLab name
    try:
        ParagraphStyle("_test", fontName=bold_font)
    except Exception:
        bold_font = "Helvetica-Bold"
    styles["body_bold"] = ParagraphStyle(
        "BodyBold", fontName=bold_font,
        fontSize=body_fp.get("size", 10),
        leading=body_fp.get("leading", 14),
        textColor=HexColor(body_fp.get("color", "#333333")),
        spaceAfter=2,
    )

    # Keep sign_off and headline — derive from body style
    styles["sign_off"] = ParagraphStyle(
        "SignOff", fontName=body_fp.get("font", "Helvetica"),
        fontSize=body_fp.get("size", 10),
        leading=body_fp.get("leading", 14),
        textColor=HexColor(body_fp.get("color", "#333333")),
        spaceBefore=16, spaceAfter=2,
    )
    styles["headline"] = ParagraphStyle(
        "Headline", fontName=body_fp.get("font", "Helvetica"),
        fontSize=fp_styles.get("contact", {}).get("size", 9),
        leading=fp_styles.get("contact", {}).get("leading", 12),
        textColor=HexColor(body_fp.get("color", "#333333")),
        alignment=TA_CENTER, spaceAfter=12,
    )

    return styles


def parse_markdown(filepath):
    """Parse a markdown file into sections and paragraphs."""
    with open(filepath) as f:
        content = f.read()

    lines = content.split("\n")
    body_lines = []
    in_header = True
    for line in lines:
        if in_header:
            if line.startswith("# ") or line.startswith("**Date") or line.startswith("**Status") or line.startswith("---"):
                continue
            if line.strip() == "":
                continue
            in_header = False
        body_lines.append(line)

    return "\n".join(body_lines)


def build_cover_letter_pdf(input_file, output_file):
    """Generate a cover letter PDF."""
    contact = get_contact()
    name = get_name()
    profile = load_profile()
    title = profile.get("title", "")

    styles = get_styles()
    content = parse_markdown(input_file)

    doc = SimpleDocTemplate(
        output_file, pagesize=letter,
        leftMargin=1 * inch, rightMargin=1 * inch,
        topMargin=0.8 * inch, bottomMargin=0.8 * inch,
    )

    story = []

    # Header
    story.append(Paragraph(name, styles["name"]))
    contact_line = f"{contact.get('location', '')} &bull; {contact.get('phone', '')} &bull; {contact.get('email', '')}"
    story.append(Paragraph(contact_line, styles["contact"]))
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 16))

    # Body paragraphs - separate signature from body
    paragraphs = content.split("\n\n")
    signature_lines = [
        "Regards,", "Warm regards,", "Best,", name,
        title, f"M. {contact.get('phone', '')[:5]}",
        f"E. {contact.get('email', '')[:8]}",
        f"W. {contact.get('website', '')[:8]}",
    ]

    body_paras = []
    hit_signature = False
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if any(para.startswith(s) for s in signature_lines if s):
            hit_signature = True
            continue
        if hit_signature:
            continue
        body_paras.append(para)

    for para in body_paras:
        para = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', para)
        para = para.replace("\n", " ")
        story.append(Paragraph(para, styles["body"]))

    # Signature block
    story.append(Spacer(1, 16))
    story.append(Paragraph("Regards,", styles["sign_off"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<b>{name}</b>", styles["body"]))
    if title:
        story.append(Paragraph(title, styles["body"]))
    if contact.get("phone"):
        story.append(Paragraph(f"M. {contact['phone']}", styles["body"]))
    if contact.get("email"):
        story.append(Paragraph(f"E. {contact['email']}", styles["body"]))
    if contact.get("website"):
        story.append(Paragraph(f"W. {contact['website']}", styles["body"]))

    doc.build(story)
    print(f"Cover letter PDF saved: {output_file}")


# ---------------------------------------------------------------------------
# Two-column sidebar helpers
# ---------------------------------------------------------------------------

_SIDEBAR_SECTIONS = {"skills", "education", "certifications", "languages", "tools", "technologies", "technical skills"}


def _split_markdown_columns(content):
    """Split markdown content into sidebar and main sections.

    Uses explicit <!-- sidebar --> / <!-- main --> markers if present.
    Otherwise, heuristically assigns Skills/Education/Certifications to the
    sidebar and everything else to the main column.
    """
    if "<!-- sidebar -->" in content and "<!-- main -->" in content:
        parts = re.split(r"<!--\s*sidebar\s*-->|<!--\s*main\s*-->", content)
        # parts[0] = before sidebar (header), parts[1] = sidebar, parts[2] = main
        header = parts[0].strip() if len(parts) > 0 else ""
        sidebar = parts[1].strip() if len(parts) > 1 else ""
        main = parts[2].strip() if len(parts) > 2 else ""
        return header, sidebar, main

    # Heuristic: split by sections
    lines = content.split("\n")
    header_lines = []
    sidebar_lines = []
    main_lines = []
    current_target = header_lines
    in_header = True

    for line in lines:
        stripped = line.strip()
        # Detect section headers
        is_section = (stripped.isupper() and len(stripped) > 3 and not stripped.startswith("-")) or stripped.startswith("## ")
        if is_section:
            in_header = False
            section_name = stripped.replace("## ", "").strip().lower()
            if section_name in _SIDEBAR_SECTIONS:
                current_target = sidebar_lines
            else:
                current_target = main_lines
            current_target.append(line)
        elif in_header:
            header_lines.append(line)
        else:
            current_target.append(line)

    return "\n".join(header_lines), "\n".join(sidebar_lines), "\n".join(main_lines)


def _parse_lines_to_story(lines_text, styles, format_profile):
    """Parse markdown lines into a list of ReportLab flowables."""
    story = []
    section_rule = format_profile.get("section_rule", {}) if format_profile else {}
    rule_enabled = section_rule.get("enabled", True)
    rule_color = HexColor(section_rule.get("color", "#2563EB")) if section_rule else ACCENT
    rule_thickness = section_rule.get("thickness", 0.5) if section_rule else 0.5

    bullet_char = "&bull;"
    if format_profile:
        bc = format_profile.get("bullet", {}).get("char", "\u2022")
        bullet_char = bc if bc != "\u2022" else "&bull;"

    lines = lines_text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Section headers
        if (line.isupper() and len(line) > 3 and not line.startswith("-")) or line.startswith("## "):
            header_text = line.replace("## ", "").strip()
            if rule_enabled:
                story.append(HRFlowable(width="100%", thickness=rule_thickness, color=rule_color))
            story.append(Paragraph(header_text, styles["section_header"]))
            continue

        # Bullet points
        if line.startswith("- ") or line.startswith("* ") or line.startswith("\u25cf "):
            bullet_text = re.sub(r'^[-*\u25cf]\s*', '', line)
            bullet_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', bullet_text)
            story.append(Paragraph(f"{bullet_char} {bullet_text}", styles["bullet"]))
            continue

        # Job titles (bold lines with company and dates)
        if "," in line and any(year in line for year in ["201", "202", "Present"]):
            parts = line.rsplit("  ", 1)
            meta_color = styles["job_meta"].textColor if "job_meta" in styles else LIGHT_GRAY
            meta_hex = meta_color.hexval() if hasattr(meta_color, 'hexval') else "#999999"
            if len(parts) == 2:
                story.append(Paragraph(
                    f"{parts[0].strip()} <font color='{meta_hex}'>{parts[1].strip()}</font>",
                    styles["job_title"]
                ))
            else:
                story.append(Paragraph(line, styles["job_title"]))
            continue

        # Regular text
        line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
        story.append(Paragraph(line, styles["body"]))

    return story


# ---------------------------------------------------------------------------
# Resume PDF builder
# ---------------------------------------------------------------------------

def build_resume_pdf(input_file, output_file):
    """Generate a resume PDF from markdown.

    If a format profile exists, uses its styles, margins, section rules,
    bullet characters, and column layout.  Otherwise falls back to defaults.
    """
    contact = get_contact()
    name = get_name()
    format_profile = load_resume_format()

    styles = get_styles(format_profile)

    with open(input_file) as f:
        content = f.read()

    # Determine page geometry
    if format_profile:
        fp_margins = format_profile.get("margins", {})
        left_m = fp_margins.get("left", 50.4)
        right_m = fp_margins.get("right", 50.4)
        top_m = fp_margins.get("top", 36)
        bottom_m = fp_margins.get("bottom", 36)
        page_w, page_h = format_profile.get("page_size", [612, 792])
    else:
        left_m = 0.7 * 72  # inch → points
        right_m = 0.7 * 72
        top_m = 0.5 * 72
        bottom_m = 0.5 * 72
        page_w, page_h = letter

    # Section rule settings
    if format_profile:
        sr = format_profile.get("section_rule", {})
        rule_enabled = sr.get("enabled", True)
        rule_color = HexColor(sr.get("color", "#2563EB"))
        rule_thickness = sr.get("thickness", 0.5)
    else:
        rule_enabled = True
        rule_color = ACCENT
        rule_thickness = 0.5

    # Bullet character
    if format_profile:
        bc = format_profile.get("bullet", {}).get("char", "\u2022")
        bullet_char = bc if bc != "\u2022" else "&bull;"
    else:
        bullet_char = "&bull;"

    # Name text transform
    name_text = name
    if format_profile:
        transform = format_profile.get("styles", {}).get("name_header", {}).get("text_transform")
        if transform == "uppercase":
            name_text = name.upper()
    else:
        name_text = name.upper()

    # Detect two-column layout
    is_two_col = format_profile and format_profile.get("layout", {}).get("columns", 1) == 2

    if is_two_col:
        _build_two_column_resume(
            content, output_file, name_text, contact, styles, format_profile,
            page_w, page_h, left_m, right_m, top_m, bottom_m,
            rule_enabled, rule_color, rule_thickness, bullet_char,
        )
    else:
        _build_single_column_resume(
            content, output_file, name_text, contact, styles, format_profile,
            page_w, page_h, left_m, right_m, top_m, bottom_m,
            rule_enabled, rule_color, rule_thickness, bullet_char,
        )


def _build_single_column_resume(
    content, output_file, name_text, contact, styles, format_profile,
    page_w, page_h, left_m, right_m, top_m, bottom_m,
    rule_enabled, rule_color, rule_thickness, bullet_char,
):
    """Build a single-column resume PDF."""
    doc = SimpleDocTemplate(
        output_file, pagesize=(page_w, page_h),
        leftMargin=left_m, rightMargin=right_m,
        topMargin=top_m, bottomMargin=bottom_m,
    )

    story = []

    # Header
    story.append(Paragraph(name_text, styles["name"]))
    contact_parts = []
    if contact.get("location"):
        contact_parts.append(contact["location"])
    if contact.get("phone"):
        contact_parts.append(contact["phone"])
    if contact.get("website"):
        contact_parts.append(contact["website"])
    if contact.get("email"):
        contact_parts.append(contact["email"])
    contact_line = " &bull; ".join(contact_parts)
    story.append(Paragraph(contact_line, styles["contact"]))

    lines = content.split("\n")
    name_upper = name_text.upper().split()[0] if name_text else ""
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip the name/contact lines at top (already rendered)
        if i < 5 and (
            (name_upper and line.upper().startswith(name_upper)) or
            line.startswith(contact.get("location", "SKIP")[:10]) or
            line == ""
        ):
            i += 1
            continue

        # Section headers (all caps lines or ## headers)
        if (line.isupper() and len(line) > 3 and not line.startswith("-")) or line.startswith("## "):
            header_text = line.replace("## ", "").strip()
            if rule_enabled:
                story.append(HRFlowable(width="100%", thickness=rule_thickness, color=rule_color))
            story.append(Paragraph(header_text, styles["section_header"]))
            i += 1
            continue

        # Bullet points
        if line.startswith("- ") or line.startswith("* ") or line.startswith("\u25cf "):
            bullet_text = re.sub(r'^[-*\u25cf]\s*', '', line)
            bullet_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', bullet_text)
            story.append(Paragraph(f"{bullet_char} {bullet_text}", styles["bullet"]))
            i += 1
            continue

        # Job titles (bold lines with company and dates)
        if "," in line and any(year in line for year in ["201", "202", "Present"]):
            parts = line.rsplit("  ", 1)
            meta_color = styles.get("job_meta", styles["body"]).textColor
            meta_hex = meta_color.hexval() if hasattr(meta_color, 'hexval') else "#999999"
            if len(parts) == 2:
                story.append(Paragraph(
                    f"{parts[0].strip()} <font color='{meta_hex}'>{parts[1].strip()}</font>",
                    styles["job_title"]
                ))
            else:
                story.append(Paragraph(line, styles["job_title"]))
            i += 1
            continue

        # Regular text
        if line:
            line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
            story.append(Paragraph(line, styles["body"]))

        i += 1

    doc.build(story)
    print(f"Resume PDF saved: {output_file}")


def _build_two_column_resume(
    content, output_file, name_text, contact, styles, format_profile,
    page_w, page_h, left_m, right_m, top_m, bottom_m,
    rule_enabled, rule_color, rule_thickness, bullet_char,
):
    """Build a two-column resume PDF with a sidebar and main content area."""
    layout = format_profile.get("layout", {})
    col_widths = layout.get("column_widths", [0.3, 0.7])
    col_gap = layout.get("column_gap", 20) or 20

    usable_w = page_w - left_m - right_m
    left_w = usable_w * col_widths[0] - col_gap / 2
    right_w = usable_w * col_widths[1] - col_gap / 2

    # Split content into header, sidebar, and main
    header_text, sidebar_text, main_text = _split_markdown_columns(content)

    # Build header story (spans full width)
    header_story = []
    header_story.append(Paragraph(name_text, styles["name"]))
    contact_parts = []
    if contact.get("location"):
        contact_parts.append(contact["location"])
    if contact.get("phone"):
        contact_parts.append(contact["phone"])
    if contact.get("website"):
        contact_parts.append(contact["website"])
    if contact.get("email"):
        contact_parts.append(contact["email"])
    contact_line = " &bull; ".join(contact_parts)
    header_story.append(Paragraph(contact_line, styles["contact"]))
    header_story.append(Spacer(1, 8))

    # Build sidebar and main stories
    sidebar_story = _parse_lines_to_story(sidebar_text, styles, format_profile) if sidebar_text else []
    main_story = _parse_lines_to_story(main_text, styles, format_profile) if main_text else []

    # If no sidebar content, fall back to putting everything in main
    if not sidebar_story and main_text:
        sidebar_story = []
    elif not sidebar_story and not main_text:
        # No column markers and heuristic found nothing for sidebar
        main_story = _parse_lines_to_story(content, styles, format_profile)

    # Calculate header height (approximate)
    header_height = 60  # name + contact + spacer

    # Create frames
    header_frame = Frame(
        left_m, page_h - top_m - header_height,
        usable_w, header_height,
        id="header",
    )
    left_frame = Frame(
        left_m, bottom_m,
        left_w, page_h - top_m - bottom_m - header_height,
        id="sidebar",
    )
    right_frame = Frame(
        left_m + left_w + col_gap, bottom_m,
        right_w, page_h - top_m - bottom_m - header_height,
        id="main",
    )

    # Page template for first page (header + two columns)
    first_page = PageTemplate(
        id="FirstPage",
        frames=[header_frame, left_frame, right_frame],
    )
    # Continuation pages (two columns only, no header)
    left_frame_cont = Frame(
        left_m, bottom_m,
        left_w, page_h - top_m - bottom_m,
        id="sidebar_cont",
    )
    right_frame_cont = Frame(
        left_m + left_w + col_gap, bottom_m,
        right_w, page_h - top_m - bottom_m,
        id="main_cont",
    )
    continuation = PageTemplate(
        id="Later",
        frames=[left_frame_cont, right_frame_cont],
    )

    doc = BaseDocTemplate(
        output_file, pagesize=(page_w, page_h),
        leftMargin=left_m, rightMargin=right_m,
        topMargin=top_m, bottomMargin=bottom_m,
    )
    doc.addPageTemplates([first_page, continuation])

    # Combine: header fills first frame, sidebar fills second, main fills third
    # FrameBreak signals ReportLab to move to the next frame
    from reportlab.platypus import FrameBreak
    story = header_story + [FrameBreak()] + sidebar_story + [FrameBreak()] + main_story

    doc.build(story)
    print(f"Resume PDF saved (2-column): {output_file}")


def make_filename(doc_type, company=None):
    """Generate output filename following naming convention."""
    prefix = get_filename_prefix()
    today = date.today().isoformat()
    if doc_type == "cover-letter" and company:
        return f"{prefix}_CoverLetter_{company}_{today}.pdf"
    elif doc_type == "resume":
        return f"{prefix}_Resume_{today}.pdf"
    return f"{prefix}_{doc_type}_{today}.pdf"


def main():
    parser = argparse.ArgumentParser(description="Generate PDF from markdown")
    parser.add_argument("--type", required=True, choices=["cover-letter", "resume"],
                        help="Document type")
    parser.add_argument("--input", required=True, help="Input markdown file")
    parser.add_argument("--company", default=None, help="Company name (for cover letter filename)")
    parser.add_argument("--output-dir", default=DOWNLOADS_DIR,
                        help=f"Output directory (default: {DOWNLOADS_DIR})")
    parser.add_argument("--output", default=None, help="Override output filename")
    parser.add_argument("--reextract", default=None,
                        help="Re-extract format from this PDF before generating")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Re-extract format if requested
    if args.reextract:
        from extract_resume_format import extract_and_save
        extract_and_save(args.reextract)

    if args.output:
        output_file = args.output
    else:
        filename = make_filename(args.type, args.company)
        output_file = os.path.join(args.output_dir, filename)

    if args.type == "cover-letter":
        build_cover_letter_pdf(args.input, output_file)
    elif args.type == "resume":
        build_resume_pdf(args.input, output_file)


if __name__ == "__main__":
    main()
