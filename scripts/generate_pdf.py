#!/usr/bin/env python3
"""Generate professional PDFs for cover letters and resumes from markdown files."""

import argparse
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
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, ListFlowable, ListItem
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_loader import get_contact, get_name, load_profile, get_filename_prefix

PROJECT_DIR = os.environ.get("JOB_SEARCH_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOWNLOADS_DIR = os.path.expanduser("~/Downloads")

# Colors
DARK = HexColor("#333333")
ACCENT = HexColor("#2563EB")
LIGHT_GRAY = HexColor("#999999")


def get_styles():
    """Create custom paragraph styles."""
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


def build_resume_pdf(input_file, output_file):
    """Generate a resume PDF from markdown."""
    contact = get_contact()
    name = get_name()

    styles = get_styles()

    with open(input_file) as f:
        content = f.read()

    doc = SimpleDocTemplate(
        output_file, pagesize=letter,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.5 * inch, bottomMargin=0.5 * inch,
    )

    story = []

    # Header
    story.append(Paragraph(name.upper(), styles["name"]))
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
    name_upper = name.upper().split()[0] if name else ""
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip the name/contact lines at top (already rendered)
        if i < 5 and (
            (name_upper and line.startswith(name_upper)) or
            line.startswith(contact.get("location", "SKIP")[:10]) or
            line == ""
        ):
            i += 1
            continue

        # Section headers (all caps lines or ## headers)
        if (line.isupper() and len(line) > 3 and not line.startswith("-")) or line.startswith("## "):
            header_text = line.replace("## ", "").strip()
            story.append(HRFlowable(width="100%", thickness=0.5, color=ACCENT))
            story.append(Paragraph(header_text, styles["section_header"]))
            i += 1
            continue

        # Bullet points
        if line.startswith("- ") or line.startswith("* ") or line.startswith("● "):
            bullet_text = re.sub(r'^[-*●]\s*', '', line)
            bullet_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', bullet_text)
            story.append(Paragraph(f"&bull; {bullet_text}", styles["bullet"]))
            i += 1
            continue

        # Job titles (bold lines with company and dates)
        if "," in line and any(year in line for year in ["201", "202", "Present"]):
            parts = line.rsplit("  ", 1)
            if len(parts) == 2:
                story.append(Paragraph(
                    f"{parts[0].strip()} <font color='#999999'>{parts[1].strip()}</font>",
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
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

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
