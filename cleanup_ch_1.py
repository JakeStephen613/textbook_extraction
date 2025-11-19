from pathlib import Path
import fitz  # PyMuPDF

# -----------------------------
# CONFIG
# -----------------------------

# Name of your PDF on the Desktop
PDF_NAME = "Fundamental Neuroscience.pdf"

# Output text filename
OUTPUT_NAME = "Fundamental_Neuroscience_Extract.txt"

# Page range (1-based, inclusive)
START_PAGE = 1   # <-- change this
END_PAGE   = 20  # <-- change this

# Header/footer margins in points (roughly 72 pt = 1 inch)
HEADER_MARGIN = 70
FOOTER_MARGIN = 70


def extract_body_blocks(page):
    """
    Extract text blocks from a page while removing headers and footers
    using bounding-box coordinates.
    """
    body_text_parts = []
    page_height = page.rect.height

    # get_text("blocks") returns a list of tuples:
    # (x0, y0, x1, y1, text, block_no, block_type, ...)
    for block in page.get_text("blocks"):
        x0, y0, x1, y1, text = block[:5]

        # Skip empty blocks
        if not text or not text.strip():
            continue

        # Remove header area
        if y1 < HEADER_MARGIN:
            continue

        # Remove footer area
        if y0 > page_height - FOOTER_MARGIN:
            continue

        body_text_parts.append(text.strip())

    return "\n".join(body_text_parts)


def main():
    desktop = Path.home() / "Desktop"
    pdf_path = desktop / PDF_NAME
    output_path = desktop / OUTPUT_NAME

    if not pdf_path.exists():
        raise FileNotFoundError(f"Could not find PDF at: {pdf_path}")

    doc = fitz.open(pdf_path)
    num_pages = doc.page_count

    # Sanity checks on page range
    if START_PAGE < 1 or END_PAGE < 1 or START_PAGE > END_PAGE:
        raise ValueError("Invalid page range: check START_PAGE and END_PAGE.")
    if END_PAGE > num_pages:
        raise ValueError(f"END_PAGE ({END_PAGE}) is greater than total pages ({num_pages}).")

    collected_chunks = []

    # PyMuPDF pages are 0-based, our config is 1-based
    for page_number in range(START_PAGE, END_PAGE + 1):
        page_index = page_number - 1
        page = doc[page_index]

        body_text = extract_body_blocks(page)
        if body_text:
            collected_chunks.append(body_text)

    final_text = "\n\n".join(collected_chunks)

    if not final_text.strip():
        print("Warning: No text was extracted. You may need to tweak HEADER_MARGIN/FOOTER_MARGIN.")
    else:
        output_path.write_text(final_text, encoding="utf-8")
        print(f"Extracted pages {START_PAGE}-{END_PAGE} to: {output_path}")


if __name__ == "__main__":
    main()
