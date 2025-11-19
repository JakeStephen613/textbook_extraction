from pathlib import Path
import re
import fitz  # PyMuPDF

# -----------------------------
# CONFIG
# -----------------------------

PDF_NAME = "test.pdf"  # on Desktop
PAGE_INDEX = 0                             # page to inspect (0-based)
OUTPUT_NAME = "Fundamental_Neuroscience_Font8_Test.txt"

FONT_SIZE_MIN = 10  # keep all spans with size >= 8 pt


# -----------------------------
# SIMPLE CLEANER (optional)
# -----------------------------

def simple_clean(text: str) -> str:
    """Very light cleanup: collapse whitespace, normalize newlines."""
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")  # non-breaking space -> space

    # Collapse 3+ newlines -> 2, 2 newlines -> paragraph break
    PARA_TOKEN = "§§PARA_BREAK§§"
    text = re.sub(r"\n{2,}", PARA_TOKEN, text)

    # Collapse internal whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Restore paragraph-ish breaks
    text = text.replace(PARA_TOKEN, "\n\n")
    return text


# -----------------------------
# CORE EXTRACTION
# -----------------------------
def extract_page_text_font8(page) -> str:
    """
    Two-column aware extraction:
    - Splits page down the vertical middle
    - Extracts left column text top→bottom, then right column
    - Keeps spans only if font-size >= FONT_SIZE_MIN
    """

    width = page.rect.width
    mid_x = width / 2

    data = page.get_text("dict")
    blocks = data.get("blocks", [])

    left_spans = []
    right_spans = []
    all_sizes = set()

    for b in blocks:
        lines = b.get("lines", [])
        for line in lines:
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                size = span.get("size", 0)
                (x0, y0, x1, y1) = span.get("bbox", (0, 0, 0, 0))
                cx = (x0 + x1) / 2  # horizontal center

                if not text:
                    continue

                all_sizes.add(round(size,2))

                if size < FONT_SIZE_MIN:
                    continue

                entry = (y0, cx, text)

                # (x-center decides which column it belongs in)
                if cx < mid_x:
                    left_spans.append(entry)
                else:
                    right_spans.append(entry)

    # Sort each column by y position
    left_spans.sort(key=lambda t: t[0])
    right_spans.sort(key=lambda t: t[0])

    # Combine left then right
    collected = [t[2] for t in left_spans] + [t[2] for t in right_spans]

    print("\n[DEBUG] Distinct font sizes on page:", sorted(all_sizes))
    print("[DEBUG] Kept spans:", len(collected))

    raw_text = " ".join(collected)
    return simple_clean(raw_text)


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
    print(f"[DEBUG] Opened PDF with {num_pages} pages")

    if not (0 <= PAGE_INDEX < num_pages):
        raise IndexError(
            f"PAGE_INDEX {PAGE_INDEX} out of range for document with {num_pages} pages"
        )

    page = doc[PAGE_INDEX]
    print(f"[DEBUG] Extracting from PAGE_INDEX={PAGE_INDEX}")

    text = extract_page_text_font8(page)

    if not text.strip():
        print("[DEBUG] RESULT: No text collected after font-size filtering.")
    else:
        output_path.write_text(text, encoding="utf-8")
        print(f"[DEBUG] RESULT: Wrote {len(text)} characters to {output_path}")


if __name__ == "__main__":
    main()
