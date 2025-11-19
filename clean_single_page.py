from pathlib import Path
import re
import fitz  # PyMuPDF

# -----------------------------
# CONFIG
# -----------------------------

# PDF file name (assumed to be on your Desktop)
PDF_NAME = "test.pdf"

# Which page to test on (0-based index)
PAGE_INDEX = 0  # start at page 0

# Output text file name (will be written to your Desktop)
OUTPUT_NAME = "Fundamental_Neuroscience_Single_Page_Test.txt"

# Header/footer margins in points (72 pt ≈ 1 inch)
HEADER_MARGIN = 70
FOOTER_MARGIN = 70

# Minimum font size (in points) to keep.
# Increase this if you still see tiny labels from figures; decrease if you lose real text.
FONT_SIZE_MIN = 9

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
    Extract text from a page using:
    - Header/footer bounding-box filters
    - Font-size filtering to remove tiny labels/graph text
    - Caption/page-number/URL removal
    """
    body_paragraphs = []
    page_height = page.rect.height

    # dict mode gives blocks with line/span/font info
    blocks = page.get_text("dict")["blocks"]

    # Sort blocks by reading order: top-to-bottom, then left-to-right
    blocks = sorted(blocks, key=lambda b: (b["bbox"][1], b["bbox"][0]))
