from pathlib import Path
import re
import fitz  # PyMuPDF

# -----------------------------
# CONFIG
# -----------------------------

PDF_NAME = "Fundamental Neuroscience.pdf"
OUTPUT_NAME = "Fundamental_Neuroscience_Chapter_01.txt"

# Header/footer margins in points (72 pt ≈ 1 inch)
HEADER_MARGIN = 70
FOOTER_MARGIN = 70

# Chapter title patterns (regex, case-insensitive)
# We allow an optional leading "Chapter"
START_RE = re.compile(
    r"(?:chapter\s+)?1\s+The\s+Brain\s+and\s+Behavior",
    re.IGNORECASE,
)

END_RE = re.compile(
    r"(?:chapter\s+)?2\s+Nerve\s+Cells,\s+Neural\s+Circuitry,\s+and\s+Behavior",
    re.IGNORECASE,
)


# -----------------------------
# HELPERS
# -----------------------------

def clean_block_text(text: str) -> str:
    """
    Flatten hard-wrapped lines inside a block into spaces,
    but preserve paragraph breaks (blank lines).
    """
    if not text:
        return ""

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

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


def extract_body_blocks(page):
    """
    Extract text blocks from a page while removing headers and footers
    using bounding-box coordinates, and clean up intra-block line breaks.
    """
    body_paragraphs = []
    page_height = page.rect.height

    # get_text("blocks") returns tuples:
    # (x0, y0, x1, y1, text, block_no, block_type, ...)
    for block in page.get_text("blocks"):
        x0, y0, x1, y1, text = block[:5]

        if not text or not text.strip():
            continue

        # Remove header area
        if y1 < HEADER_MARGIN:
            continue

        # Remove footer area
        if y0 > page_height - FOOTER_MARGIN:
            continue

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

    # First pass: extract cleaned text per page,
    # and detect which pages contain the 2nd occurrence
    # of each chapter heading.
    pages_text = []
    start_count = 0
    end_count = 0
    start_page_idx = None
    end_page_idx = None

    for idx in range(num_pages):
        page = doc[idx]
        body_text = extract_body_blocks(page)
        pages_text.append(body_text)

        # Normalize whitespace for matching chapter titles
        search_text = re.sub(r"\s+", " ", body_text).strip()

        # Count occurrences of the start chapter title
        start_matches = START_RE.findall(search_text)
        if start_matches:
            start_count += len(start_matches)
            if start_count >= 2 and start_page_idx is None:
                start_page_idx = idx

        # Count occurrences of the end chapter title
        end_matches = END_RE.findall(search_text)
        if end_matches:
            end_count += len(end_matches)
            if end_count >= 2 and end_page_idx is None:
                end_page_idx = idx

    print(f"Detected 2nd '1 The Brain and Behavior' on page index: {start_page_idx}")
    print(f"Detected 2nd '2 Nerve Cells, Neural Circuitry, and Behavior' on page index: {end_page_idx}")

    if start_page_idx is None:
        raise RuntimeError(
            "Could not find the 2nd occurrence of '1 The Brain and Behavior' "
            "- check the exact chapter title or loosen the regex."
        )
    if end_page_idx is None:
        raise RuntimeError(
            "Could not find the 2nd occurrence of "
            "'2 Nerve Cells, Neural Circuitry, and Behavior' "
            "- check the exact chapter title or loosen the regex."
        )
    if end_page_idx <= start_page_idx:
        raise RuntimeError(
            f"End chapter page ({end_page_idx}) is not after start chapter page ({start_page_idx}). "
            "The PDF may have an unusual layout."
        )

    # Second pass: collect all pages from start_page_idx up to (but not including) end_page_idx
    collected_chunks = []
    for idx in range(start_page_idx, end_page_idx):
        text = pages_text[idx]
        if text and text.strip():
            collected_chunks.append(text)

    final_text = "\n\n".join(collected_chunks)

    if not final_text.strip():
        print("Warning: No text was collected between chapter boundaries.")
    else:
        output_path.write_text(final_text, encoding="utf-8")
        print(f"Chapter 1 text written to: {output_path}")
        print(f"Pages included (0-based indices): {list(range(start_page_idx, end_page_idx))}")


if __name__ == "__main__":
    main()
