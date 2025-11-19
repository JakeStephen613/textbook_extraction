from pathlib import Path
import fitz  # PyMuPDF

# -----------------------------
# CONFIG
# -----------------------------

# Name of your PDF on the Desktop
PDF_NAME = "Fundamental Neuroscience.pdf"

# Output text filename
OUTPUT_NAME = "Fundamental_Neuroscience_Chapter_01.txt"

# Header/footer margins in points (roughly 72 pt = 1 inch)
HEADER_MARGIN = 70
FOOTER_MARGIN = 70

# Text patterns that likely mark chapter boundaries
CH1_MARKERS = ["chapter 1", "chapter one"]
CH2_MARKERS = ["chapter 2", "chapter two"]


def page_contains_any(text: str, markers):
    """Return True if any of the markers appears in the text (case-insensitive)."""
    text_lower = text.lower()
    return any(m in text_lower for m in markers)


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

    in_chapter_1 = False
    collected_chunks = []

    for page_index, page in enumerate(doc):
        # Get full raw text for marker detection
        full_text = page.get_text()
        full_text_lower = full_text.lower()

        # If we haven't entered chapter 1 yet, check for its marker
        if not in_chapter_1:
            if page_contains_any(full_text_lower, CH1_MARKERS):
                in_chapter_1 = True
            else:
                # Not yet in chapter 1, skip this page entirely
                continue

        # If we're in chapter 1, check if this page already has the start of chapter 2
        # If so, we stop BEFORE chapter 2 begins.
        if page_contains_any(full_text_lower, CH2_MARKERS):
            # We *might* have some chapter 1 text before the Chapter 2 heading
            # For simplicity, we stop collecting as soon as we see Chapter 2.
            break

        # Extract only body text for this page
        body_text = extract_body_blocks(page)
        if body_text:
            collected_chunks.append(body_text)

    # Join and write out
    chapter_text = "\n\n".join(collected_chunks)

    if not chapter_text.strip():
        print("Warning: No text was extracted for Chapter 1. "
              "You may need to adjust CH1_MARKERS or margins.")
    else:
        output_path.write_text(chapter_text, encoding="utf-8")
        print(f"Chapter 1 text written to: {output_path}")


if __name__ == "__main__":
    main()
