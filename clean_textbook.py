from pathlib import Path
import re
import fitz  # PyMuPDF

# -----------------------------
# CONFIG
# -----------------------------
PDF_NAME = "textbook.pdf"  # on Desktop
BASE_OUTPUT_FOLDER = "extracts"  # top-level folder on Desktop
TITLE_FONT_SIZE = 40   # chapter titles
CONTENT_FONT_SIZE = 10 # regular content
FONT_TOLERANCE = 0.1   # tolerance for font size matching

# -----------------------------
# SIMPLE CLEANER (optional)
# -----------------------------
def simple_clean(text: str) -> str:
    """Very light cleanup: collapse whitespace, normalize newlines, and fix hyphenated line breaks."""
    if not text:
        return ""
    
    # Normalize newlines and spaces
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")  # non-breaking space -> space

    # Fix line-break hyphenation: "electri- cal" -> "electrical"
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
# CORE EXTRACTION
# -----------------------------
def extract_chapters_by_font(doc) -> list:
    """
    Extract chapters based on font sizes.
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
        mid_x = width / 2

        data = page.get_text("dict")
        blocks = data.get("blocks", [])

        page_spans = []

        # Collect all spans with position info
        for b in blocks:
            lines = b.get("lines", [])
            for line in lines:
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    size = span.get("size", 0)
                    (x0, y0, x1, y1) = span.get("bbox", (0, 0, 0, 0))
                    cx = (x0 + x1) / 2

                    if not text:
                        continue

                    page_spans.append({
                        'text': text,
                        'size': size,
                        'y': y0,
                        'x': cx,
                        'is_left': cx < mid_x
                    })

        # Sort spans: first by column (left then right), then by y position
        left_spans = sorted([s for s in page_spans if s['is_left']], key=lambda s: s['y'])
        right_spans = sorted([s for s in page_spans if not s['is_left']], key=lambda s: s['y'])
        sorted_spans = left_spans + right_spans

        prev_span = None  # resets per page

        # Process spans in reading order
        for span in sorted_spans:
            text = span['text']
            size = span['size']

            # -----------------------------
            # TITLE DETECTION (40pt font)
            # -----------------------------
            if abs(size - TITLE_FONT_SIZE) <= FONT_TOLERANCE:
                # If we already started a chapter on this page and haven't seen content,
                # treat additional 40pt spans as part of the same title (e.g., "8 W ...").
                if (
                    current_chapter is not None
                    and not current_chapter.get('_has_content', False)
                    and current_chapter_page == page_num
                ):
                    current_chapter['title'] += " " + text
                    print(f"[DEBUG] Extended chapter title on page {page_num + 1}: {current_chapter['title']}")
                else:
                    # Save previous chapter if exists and has content
                    if current_chapter is not None and current_chapter['content'].strip():
                        chapters.append(current_chapter)

                    # Start new chapter
                    current_chapter = {
                        'title': text,
                        'content': '',
                        '_has_content': False  # track if we've seen any 10pt text
                    }
                    current_chapter_page = page_num
                    print(f"[DEBUG] Found chapter title on page {page_num + 1}: {text[:50]}")

                prev_span = span
                continue

            # -----------------------------
            # CONTENT DETECTION (10pt font)
            # -----------------------------
            if abs(size - CONTENT_FONT_SIZE) <= FONT_TOLERANCE:
                if current_chapter is not None:
                    # FIRST 10-pt word for this chapter:
                    # prepend the last character of the immediately previous span,
                    # regardless of that span's font.
                    if not current_chapter.get('_has_content', False):
                        current_chapter['_has_content'] = True
                        if prev_span is not None and prev_span['text']:
                            text = prev_span['text'][-1] + text

                    current_chapter['content'] += text + " "

                prev_span = span
                continue

            # Any other font size: just advance prev_span
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

    # Create base 'extracts' folder on Desktop
    base_output = desktop / BASE_OUTPUT_FOLDER
    base_output.mkdir(exist_ok=True)

    # Create a subfolder named after the PDF (without extension)
    pdf_stem = pdf_path.stem
    output_folder = base_output / pdf_stem
    output_folder.mkdir(exist_ok=True)

    print(f"[DEBUG] Output folder: {output_folder}")

    doc = fitz.open(pdf_path)
    print(f"[DEBUG] Opened PDF: {PDF_NAME}")

    # Extract all chapters
    chapters = extract_chapters_by_font(doc)

    print(f"\n[DEBUG] Found {len(chapters)} chapters")

    # Save each chapter to a separate file inside the output_folder
    for chapter in chapters:
        title = chapter['title']
        content = simple_clean(chapter['content'])

        if not content.strip():
            print(f"[DEBUG] Skipping empty chapter: {title}")
            continue

        filename = sanitize_filename(title)
        filepath = output_folder / filename

        # Write ONLY the cleaned content (no title header, no "=====")
        filepath.write_text(content, encoding="utf-8")

        print(f"[DEBUG] Saved: {filename} ({len(content)} chars)")

    print(f"\n[DEBUG] COMPLETE: Extracted {len(chapters)} chapters to {output_folder}")
    doc.close()

if __name__ == "__main__":
    main()
