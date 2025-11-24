from pathlib import Path
import re
import fitz  # PyMuPDF

# -----------------------------
# CONFIG
# -----------------------------
PDF_NAME = "textbook.pdf"  # on Desktop
BASE_OUTPUT_FOLDER = "extracts"  # still defined but no longer used for final txt
TITLE_FONT_SIZE = 40   # chapter titles (approx)
CONTENT_FONT_SIZE = 10 # regular content (approx)
FONT_TOLERANCE = 0.2   # tolerance for TITLE detection

# Derived body-font band (to allow 9.0–11.0 pt text as "body")
BODY_FONT_MIN = CONTENT_FONT_SIZE - 1.0
BODY_FONT_MAX = CONTENT_FONT_SIZE + 1.0

# -----------------------------
# UNICODE NORMALIZATION MAP
# -----------------------------
# Normalize ligatures and curly punctuation early, so downstream logic
# sees clean ASCII-like text.
UNICODE_NORMALIZATION_MAP = str.maketrans({
    "\ufb00": "ff",   # ﬀ
    "\ufb01": "fi",   # ﬁ
    "\ufb02": "fl",   # ﬂ
    "\ufb03": "ffi",  # ﬃ
    "\ufb04": "ffl",  # ﬄ
    "\u2010": "-",    # ‐
    "\u2011": "-",    # -
    "\u2012": "-",    # ‒
    "\u2013": "-",    # –
    "\u2014": "-",    # —
    "\u2015": "-",    # ―
    "\u2018": "'",    # ‘
    "\u2019": "'",    # ’
    "\u201c": '"',    # “
    "\u201d": '"',    # ”
})

def normalize_unicode(text: str) -> str:
    if not text:
        return ""
    return text.translate(UNICODE_NORMALIZATION_MAP)

# -----------------------------
# SIMPLE CLEANER (optional)
# -----------------------------
def simple_clean(text: str) -> str:
    """Very light cleanup: normalize unicode, collapse whitespace, and fix hyphenated line-break style joins."""
    if not text:
        return ""

    # Normalize ligatures and punctuation
    text = normalize_unicode(text)

    # Normalize newlines and spaces
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")  # non-breaking space -> space

    # Fix line-break hyphenation-like patterns AFTER unicode normalization.
    # This will catch patterns like "dif- ﬁculty" -> "difficulty" or "electri- cal" -> "electrical".
    # Heuristic: word characters, hyphen, whitespace, then lowercase word.
    text = re.sub(r"(\b\w+)-\s+([a-z]{2,}\b)", r"\1\2", text)

    # Collapse 3+ newlines -> special token
    PARA_TOKEN = "§§PARA_BREAK§§"
    text = re.sub(r"\n{2,}", PARA_TOKEN, text)

    # Collapse internal whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Restore paragraph-ish breaks
    text = text.replace(PARA_TOKEN, "\n\n")
    return text

# -----------------------------
# SANITIZE FILENAME
# -----------------------------
def sanitize_filename(title: str) -> str:
    """Convert chapter title to valid filename. No chapter numbers, just title."""
    title = re.sub(r'[<>:"/\\|?*]', '', title)
    title = title.strip()
    if not title:
        return "untitled_chapter.txt"
    # Limit length
    title = title[:120]
    return f"{title}.txt"

# -----------------------------
# FONT HELPERS
# -----------------------------
def is_title_font(size: float) -> bool:
    """Heuristic: treat ~40pt as chapter titles."""
    return abs(size - TITLE_FONT_SIZE) <= FONT_TOLERANCE

def is_body_font(size: float) -> bool:
    """
    Treat fonts in a reasonable band around CONTENT_FONT_SIZE as main body text.
    This helps include bold/italic variants or slight size drift (e.g., 9.7, 10.2).
    """
    return BODY_FONT_MIN <= size <= BODY_FONT_MAX

# -----------------------------
# CORE EXTRACTION
# -----------------------------
def extract_chapters_by_font(doc) -> list:
    """
    Extract chapters based on font sizes and bounding-box ordering.
    Returns list of dicts: {'title': str, 'content': str}
    """
    chapters = []
    current_chapter = None
    current_chapter_page = None  # track where chapter started (for merging title spans)

    num_pages = doc.page_count
    print(f"[DEBUG] Processing {num_pages} pages...")

    for page_num in range(num_pages):
        page = doc[page_num]
        width = page.rect.width
        height = page.rect.height
        mid_x = width / 2.0

        data = page.get_text("dict")
        blocks = data.get("blocks", [])

        page_spans = []

        # Collect all spans with position info
        for b in blocks:
            lines = b.get("lines", [])
            for line in lines:
                for span in line.get("spans", []):
                    raw_text = span.get("text", "")
                    text = normalize_unicode(raw_text).strip()
                    size = span.get("size", 0.0)
                    (x0, y0, x1, y1) = span.get("bbox", (0, 0, 0, 0))

                    # Skip completely empty
                    if not text:
                        continue

                    # Skip typical page headers/footers: small text near very top or bottom
                    # (but NEVER skip if they are big title fonts).
                    if not is_title_font(size):
                        if (y0 < 30 or (height - y1) < 30) and len(text) <= 40:
                            # Heuristic: page number / running header/footer
                            continue

                    cx = (x0 + x1) / 2.0
                    page_spans.append({
                        'text': text,
                        'size': size,
                        'y0': y0,
                        'y1': y1,
                        'x0': x0,
                        'x1': x1,
                        'cx': cx,
                        'is_left': cx < mid_x,
                    })

        # Sort spans:
        #   1) left column top-to-bottom, left-to-right
        #   2) right column top-to-bottom, left-to-right
        # Using y0 and x0 preserves within-line order better than using center only.
        left_spans = sorted(
            [s for s in page_spans if s['is_left']],
            key=lambda s: (round(s['y0'], 1), s['x0'])
        )
        right_spans = sorted(
            [s for s in page_spans if not s['is_left']],
            key=lambda s: (round(s['y0'], 1), s['x0'])
        )
        sorted_spans = left_spans + right_spans

        prev_span = None  # resets per page

        # Process spans in reading order
        for span in sorted_spans:
            text = span['text']
            size = span['size']

            # -----------------------------
            # TITLE DETECTION (~40pt font)
            # -----------------------------
            if is_title_font(size):
                # If we already started a chapter on this page and haven't seen content,
                # treat additional title spans as part of the same title (e.g., "8 W hat ...").
                if (
                    current_chapter is not None
                    and not current_chapter.get('_has_content', False)
                    and current_chapter_page == page_num
                ):
                    current_chapter['title'] += " " + text
                    print(f"[DEBUG] Extended chapter title on page {page_num + 1}: {current_chapter['title']}")
                else:
                    # Save previous chapter if it exists and has content
                    if current_chapter is not None and current_chapter['content'].strip():
                        chapters.append(current_chapter)

                    # Start new chapter
                    current_chapter = {
                        'title': text,
                        'content': '',
                        '_has_content': False  # track if we've seen any body text
                    }
                    current_chapter_page = page_num
                    print(f"[DEBUG] Found chapter title on page {page_num + 1}: {text[:50]}")

                prev_span = span
                continue

            # -----------------------------
            # CONTENT DETECTION (body font)
            # -----------------------------
            if is_body_font(size):
                if current_chapter is not None:
                    # FIRST body-text word for this chapter:
                    # prepend the last character of the immediately previous span,
                    # regardless of that span's font, to recover a dropped first character.
                    # (This is the hack you requested earlier; kept but now we only
                    #  apply it once per chapter.)
                    if not current_chapter.get('_has_content', False):
                        current_chapter['_has_content'] = True
                        if prev_span is not None and prev_span.get('text'):
                            text = prev_span['text'][-1] + text

                    # Append span text and a space (we'll clean later)
                    current_chapter['content'] += text + " "

                prev_span = span
                continue

            # Any other font size: we don't add to content, but we keep prev_span
            # so the "first body word" hack has something to look at.
            prev_span = span

        # Progress indicator
        if (page_num + 1) % 10 == 0:
            print(f"[DEBUG] Processed {page_num + 1}/{num_pages} pages...")

    # Don't forget the last chapter
    if current_chapter is not None and current_chapter['content'].strip():
        chapters.append(current_chapter)

    return chapters

# -----------------------------
# MAIN
# -----------------------------
def main():
    desktop = Path.home() / "Desktop"
    pdf_path = desktop / PDF_NAME

    if not pdf_path.exists():
        raise FileNotFoundError(f"Could not find PDF at: {pdf_path}")

    pdf_stem = pdf_path.stem

    print(f"[DEBUG] Using Desktop as output directory")
    print(f"[DEBUG] Opened PDF: {PDF_NAME}")

    doc = fitz.open(pdf_path)

    # Extract all chapters
    chapters = extract_chapters_by_font(doc)

    print(f"\n[DEBUG] Found {len(chapters)} chapters")

    # Combine all chapter contents
    all_content_parts = []

    for chapter in chapters:
        content = simple_clean(chapter['content'])

        # Scrub trailing "Selected Readings References" phrase
        content = content.replace("Selected Readings References", "")

        if not content.strip():
            print(f"[DEBUG] Skipping empty chapter: {chapter['title']}")
            continue

        all_content_parts.append(content)

    full_text = "\n\n".join(all_content_parts)

    # ---- WRITE SINGLE FILE DIRECTLY TO DESKTOP ----
    combined_filename = f"{pdf_stem}_all_text.txt"
    combined_filepath = desktop / combined_filename
    combined_filepath.write_text(full_text, encoding="utf-8")

    print(f"[DEBUG] Saved combined text file to Desktop: {combined_filename} ({len(full_text)} chars)")
    print(f"\n[DEBUG] COMPLETE")

    doc.close()

if __name__ == "__main__":
    main()
