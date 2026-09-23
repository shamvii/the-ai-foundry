"""
Extracts a lightweight style profile (fonts, sizes) from a sample resume
(.docx or .pdf) you upload, so exports can match your preferred look
instead of the built-in default styling.

Honest limitation up front: this reads font choices and sizes via
heuristics (largest/topmost early text = name, bold/all-caps or larger-
than-body text = section headings, the most common font/size = body
text). It does NOT replicate columns, tables, borders, colors, or logos —
templates with those layouts won't be cloned, just the font/size choices
lifted from them. If your sample resume uses a fairly standard single-
column layout, this gets you most of the way; if it's a heavily designed
template, expect to still do manual formatting touch-ups after export.

PDF-specific limitation: this only works on PDFs with real selectable
text (i.e. exported from Word/Google Docs/etc., not a scanned image or a
photo of a resume saved as PDF). If your PDF's text can't be selected/
highlighted in a normal PDF viewer, there's no font metadata to extract
and this will fall back to the default profile.
"""

from pathlib import Path
from collections import Counter

DEFAULT_PROFILE = {
    "name_font": "Calibri",
    "name_size": 18,
    "heading_font": "Calibri",
    "heading_size": 13,
    "body_font": "Calibri",
    "body_size": 11,
}


def extract_style_profile(template_path: str) -> dict:
    """Dispatches to the right extractor based on file extension."""
    ext = Path(template_path).suffix.lower()
    if ext == ".pdf":
        return _extract_from_pdf(template_path)
    elif ext == ".docx":
        return _extract_from_docx(template_path)
    else:
        raise ValueError(f"Unsupported template format '{ext}'. Use a .docx or .pdf file.")


def _extract_from_docx(template_path: str) -> dict:
    from docx import Document

    doc = Document(template_path)
    profile = dict(DEFAULT_PROFILE)

    paragraphs = [p for p in doc.paragraphs if p.text.strip()]
    if not paragraphs:
        return profile

    # Heuristic: first non-empty paragraph is usually the name — grab its font/size
    first = paragraphs[0]
    if first.runs:
        run = first.runs[0]
        if run.font.name:
            profile["name_font"] = run.font.name
        if run.font.size:
            profile["name_size"] = round(run.font.size.pt)

    # Heuristic: find something that looks like a section heading
    # (Word's built-in Heading style, or bold + all-caps text)
    for p in paragraphs[1:]:
        text = p.text.strip()
        is_heading_style = p.style.name.lower().startswith("heading")
        run = p.runs[0] if p.runs else None
        looks_like_heading = run is not None and run.bold and text.isupper()
        if is_heading_style or looks_like_heading:
            if run:
                if run.font.name:
                    profile["heading_font"] = run.font.name
                if run.font.size:
                    profile["heading_size"] = round(run.font.size.pt)
            break

    # Body font/size from the document's Normal style
    normal_style = doc.styles["Normal"]
    if normal_style.font.name:
        profile["body_font"] = normal_style.font.name
    if normal_style.font.size:
        profile["body_size"] = round(normal_style.font.size.pt)

    return profile


def _clean_pdf_font_name(fontname: str) -> str:
    # Subsetted PDF fonts are often prefixed like "ABCDEF+ArialMT" — strip that prefix
    if "+" in fontname:
        fontname = fontname.split("+", 1)[1]
    return fontname


def _extract_from_pdf(template_path: str) -> dict:
    import pdfplumber

    profile = dict(DEFAULT_PROFILE)

    with pdfplumber.open(template_path) as pdf:
        if not pdf.pages:
            return profile
        page = pdf.pages[0]
        chars = [c for c in page.chars if c["text"].strip()]
        if not chars:
            # No extractable text — likely a scanned/image-based PDF. Nothing to lift.
            return profile

        # Group characters into lines by their vertical position on the page
        lines: dict = {}
        for c in chars:
            key = round(c["top"])
            lines.setdefault(key, []).append(c)
        sorted_line_keys = sorted(lines.keys())

        # Name = topmost line on the page
        first_line_chars = lines[sorted_line_keys[0]]
        name_sizes = [round(c["size"]) for c in first_line_chars]
        name_fonts = [_clean_pdf_font_name(c["fontname"]) for c in first_line_chars]
        if name_sizes:
            profile["name_size"] = Counter(name_sizes).most_common(1)[0][0]
        if name_fonts:
            profile["name_font"] = Counter(name_fonts).most_common(1)[0][0]

        # Body font/size = the most common font/size across everything else on the page
        rest_chars = [c for k in sorted_line_keys[1:] for c in lines[k]]
        if rest_chars:
            sizes = [round(c["size"]) for c in rest_chars]
            fonts = [_clean_pdf_font_name(c["fontname"]) for c in rest_chars]
            body_size = Counter(sizes).most_common(1)[0][0]
            profile["body_size"] = body_size
            profile["body_font"] = Counter(fonts).most_common(1)[0][0]

            # Heading candidates: text noticeably bigger than body size, or a
            # font name that itself says "Bold" (common in PDF font naming)
            heading_chars = [
                c for c in rest_chars
                if round(c["size"]) > body_size or "bold" in c["fontname"].lower()
            ]
            if heading_chars:
                h_sizes = [round(c["size"]) for c in heading_chars]
                h_fonts = [_clean_pdf_font_name(c["fontname"]) for c in heading_chars]
                profile["heading_size"] = Counter(h_sizes).most_common(1)[0][0]
                profile["heading_font"] = Counter(h_fonts).most_common(1)[0][0]

    return profile


# reportlab only ships the base 14 PDF fonts out of the box (Helvetica,
# Times-Roman, Courier, plus bold/italic variants) — anything else needs
# a TTF registered manually, which we're not doing here for simplicity.
# So for PDF export specifically, map common Word fonts to the closest
# built-in equivalent rather than failing outright.
_SERIF_HINTS = ["times", "georgia", "garamond", "cambria", "book"]
_MONO_HINTS = ["courier", "consolas", "mono"]


def map_font_to_reportlab(font_name: str) -> str:
    if not font_name:
        return "Helvetica"
    lower = font_name.lower()
    if any(hint in lower for hint in _MONO_HINTS):
        return "Courier"
    if any(hint in lower for hint in _SERIF_HINTS):
        return "Times-Roman"
    return "Helvetica"  # covers Calibri, Arial, Segoe, and most sans-serif fonts
