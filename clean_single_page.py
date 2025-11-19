from pathlib import Path
import re
import fitz  # PyMuPDF

# -----------------------------
# CONFIG
# -----------------------------

PDF_NAME = "Fundamental Neuroscience.pdf"

# Which page to test on (0-based index)
PAGE_INDEX = 10  # change this to whatever page you want

OUTPUT_NAME = "Fundamental_Neuroscience_Single_Page_Test.txt"

# Header/footer margins in points (72 pt ≈ 1 inch)
HEADER_MARGIN = 70
FOOTER_MARGIN = 70

# Regexes for filtering / cleaning
URL_RE = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
PAGE_NUM_RE = re.compile(r"^\s*\d+\s*$")
FIGURE_RE = re.compile(r"^\s*(?:figure|fig\.?|table|box)\s+\d", re.IGNORECASE)


# -----------------------------
# HELPERS
# -----------------------------

def clean_block_text(text: str) -> str:
    """
    Clean a single text block:
    - Normalize whitespace/newlines
    - Remove inline URLs/emails
    - Fix hyphenation across line breaks
    - Flatten hard-wrapped lines into spaces, but preserve paragraph breaks.
    """
    if not text:
        return ""

    # Normalize line endings and non-breaking spaces
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")  # non-breaking space → normal space

    # Basic ligature fixes (can add more if needed)
    ligatures = {
        "ﬁ": "fi",
        "ﬂ": "fl",
    }
    for bad, good in ligatures.items():
        text = text.replace(bad, good)

    # Remove inline URLs and emails
    text = URL_RE.sub("", text)
    text = EMAIL_RE.sub("", text)

    # Fix hyphenation across line breaks: "some-\nthing" -> "something"
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)

    # Mark paragraph breaks: sequences of 2+ newlines
    PARA_TOKEN = "§§PARA_BREAK§§"
    text = re.sub(r"\n{2,}", PARA_TOKEN, text)

    # Remaining single newlines are just line wraps -> spaces
    text = text.replace("\n", " ")

    # Collapse multiple spaces/tabs
    text = re.sub(r"\s+", " ", text).strip()

    # Restore paragraph breaks as double newlines
    text = text.replace(PARA_TOKEN, "\n\n")

    return text


def extract_body_blocks(page) -> str:
    """
    Extract text blocks from a page while:
    - Removing headers and footers via bounding-box coordinates
    - Dropping obvious non-body blocks (page numbers, pure URLs, captions)
    - Cleaning intra-block line breaks and inline URLs/emails.
    """
    body_paragraphs = []
    page_height = page.rect.height

    # get_text("blocks") returns tuples:
    # (x0, y0, x1, y1, text, block_no, block_type, ...)
    blocks = page.get_text("blocks")

    # Sort blocks in reading order: top-to-bottom, then left-to-right
    blocks = sorted(blocks, key=lambda b: (b[1], b[0]))

    for block in blocks:
        x0, y0, x1, y1, text = block[:5]

        if not text:
            continue
        raw = text.strip()
        if not raw:
            continue

        # Remove header area
        if y1 < HEADER_MARGIN:
            continue

        # Remove footer area
        if y0 > page_height - FOOTER_MARGIN:
            continue

        # --- Content-based filters for whole blocks ---

        # Pure page number (e.g., "23")
        if PAGE_NUM_RE.match(raw):
            continue

        # Pure URL/email block (after stripping surrounding whitespace)
        if URL_RE.search(raw) and not URL_RE.sub("", raw).strip():
            continue
        if EMAIL_RE.search(raw) and not EMAIL_RE.sub("", raw).strip():
            continue

        # Obvious figure/table/box captions at start of block
        if FIGURE_RE.match(raw):
            continue

        # Now do finer-grained cleaning inside the block
        cleaned = clean_block_text(text)
        if cleaned:
            body_paragraphs.append(cleaned)

    # Separate blocks with blank lines so paragraphs stay distinct
    return "\n\n".join(body_paragraphs)


# -----------------------------
# MAIN
# -----------------------------

def main():
    desktop = Path.home() / "Desktop"
    pdf_path = desktop / PDF_NAME
    output_path = desktop / OUTPUT_NAME

    if not pdf_path.exists():
        raise FileNotFoundError(f"Could not find PDF at: {pdf_path}")

    doc = fitz.open(pdf_path)
    num_pages = doc.page_count

    if not (0 <= PAGE_INDEX < num_pages):
        raise IndexError(
            f"PAGE_INDEX {PAGE_INDEX} out of range for document with {num_pages} pages"
        )

    page = doc[PAGE_INDEX]
    cleaned_text = extract_body_blocks(page)

    if not cleaned_text.strip():
        print(f"Warning: No relevant text extracted from page index {PAGE_INDEX}.")
    else:
        output_path.write_text(cleaned_text, encoding="utf-8")
        print(f"Cleaned text for page {PAGE_INDEX} written to: {output_path}")


if __name__ == "__main__":
    main()
