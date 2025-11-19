from pathlib import Path
import re
import fitz  # PyMuPDF

# -----------------------------
# CONFIG
# -----------------------------

# Name of your PDF on the Desktop
PDF_NAME = "Fundamental Neuroscience.pdf"

# Output text filename
OUTPUT_NAME = "Fundamental_Neuroscience_Extract.txt"

# Page range using the *printed* numbers you see at the bottom of the page
PRINTED_START_PAGE = 1   # <-- change this
PRINTED_END_PAGE   = 20  # <-- change this

# Margins in points (72 pt ≈ 1 inch)
HEADER_MARGIN = 70            # used when extracting body text
FOOTER_MARGIN = 70            # used when extracting body text
FOOTER_SCAN_HEIGHT = 120      # used when detecting printed page number


# -----------------------------
# HELPERS
# -----------------------------

def normalize_paragraph(text: str) -> str:
    """
    Flatten internal newlines inside a block into single spaces,
    and normalize repeated whitespace. This turns hard-wrapped
    lines into smooth paragraphs.
    """
    # Replace newlines and tabs with spaces, then collapse runs of whitespace
    return re.sub(r"\s+", " ", text).strip()


def extract_body_blocks(page):
    """
    Extract text blocks from a page while removing headers and footers
    using bounding-box coordinates, and clean up intra-block line breaks.
    """
    body_paragraphs = []
    page_height = page.rect.height

    # get_text("blocks") returns a list of tuples:
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

        para = normalize_paragraph(text)
        if para:
            body_paragraphs.append(para)

    # Separate blocks with blank lines so paragraphs stay distinct
    return "\n\n".join(body_paragraphs)


def detect_printed_page_number(page):
    """
    Try to detect the printed page number on this page by looking
    in the bottom FOOTER_SCAN_HEIGHT region for a line that is
    just digits (e.g., '23').
    Returns an int or None if not found.
    """
    page_height = page.rect.height
    footer_top = page_height - FOOTER_SCAN_HEIGHT

    candidate_numbers = []

    for block in page.get_text("blocks"):
        x0, y0, x1, y1, text = block[:5]
        if not text or not text.strip():
            continue

        # Only look in the bottom region
        if y0 < footer_top:
            continue

        for line in text.splitlines():
            line_stripped = line.strip()
            if re.fullmatch(r"\d+", line_stripped):
                try:
                    candidate_numbers.append(int(line_stripped))
                except ValueError:
                    continue

    # If multiple candidates (rare), pick the last one
    if candidate_numbers:
        return candidate_numbers[-1]
    return None


def build_printed_to_index_map(doc):
    """
    Build a mapping {printed_page_number: pdf_index}
    by scanning each page's footer.
    """
    mapping = {}
    for idx, page in enumerate(doc):
        num = detect_printed_page_number(page)
        if num is not None:
            # Only keep the first occurrence of each printed number
            mapping.setdefault(num, idx)
    return mapping


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

    # Build mapping from printed page number -> internal index
    printed_to_index = build_printed_to_index_map(doc)

    if not printed_to_index:
        print("Warning: Could not detect any printed page numbers in the footer.")
        print("The script will fall back to using raw PDF indices (1-based).")
        # Fallback: assume printed numbers == PDF index + 1
        for i in range(num_pages):
            printed_to_index[i + 1] = i

    # Resolve the desired range
    if PRINTED_START_PAGE > PRINTED_END_PAGE:
        raise ValueError("PRINTED_START_PAGE must be <= PRINTED_END_PAGE.")

    # Collect all indices that correspond to printed numbers in the range
    selected_indices = []
    for printed_num in range(PRINTED_START_PAGE, PRINTED_END_PAGE + 1):
        if printed_num in printed_to_index:
            selected_indices.append(printed_to_index[printed_num])
        else:
            print(f"Warning: Printed page {printed_num} not found in PDF; skipping.")

    if not selected_indices:
        raise ValueError("No pages matched the given printed page range. "
                         "You may need to adjust PRINTED_START_PAGE/END_PAGE or footer detection.")

    # Make sure we process in order
    selected_indices = sorted(set(selected_indices))

    print("Extracting PDF pages (0-based indices):", selected_indices)

    collected_chunks = []
    for page_index in selected_indices:
        if page_index < 0 or page_index >= num_pages:
            print(f"Skipping out-of-range index: {page_index}")
            continue

        page = doc[page_index]
        body_text = extract_body_blocks(page)
        if body_text:
            collected_chunks.append(body_text)

    final_text = "\n\n".join(collected_chunks)

    if not final_text.strip():
        print("Warning: No text was extracted. You may need to tweak HEADER_MARGIN/FOOTER_MARGIN.")
    else:
        output_path.write_text(final_text, encoding="utf-8")
        print(f"Extracted printed pages {PRINTED_START_PAGE}-{PRINTED_END_PAGE} to: {output_path}")


if __name__ == "__main__":
    main()
