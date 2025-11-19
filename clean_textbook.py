from pathlib import Path
import re
import fitz  # PyMuPDF

# -----------------------------
# CONFIG
# -----------------------------
PDF_NAME = "test.pdf"  # on Desktop
BASE_OUTPUT_FOLDER = "extracts"  # top-level folder on Desktop
TITLE_FONT_SIZE = 40   # chapter titles
CONTENT_FONT_SIZE = 10 # regular content
FONT_TOLERANCE = 0.5   # tolerance for font size matching

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
# SANITIZE FILENAME
# -----------------------------
def sanitize_filename(title: str, chapter_num: int) -> str:
    """Convert chapter title to valid filename."""
    # Remove/replace invalid filename characters
    title = re.sub(r'[<>:"/\\|?*]', '', title)
    title = title.strip()
    # Limit length and add chapter number
    title = title[:100]  # Max 100 chars
    if title:
        return f"Chapter_{chapter_num:02d}_{title}.txt"
    else:
        return f"Chapter_{chapter_num:02d}.txt"

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
    
    num_pages = doc.page_count
    print(f"[DEBUG] Processing {num_pages} pages...")
    
    for page_num in range(num_pages):
        page = doc[page_num]
        width = page.rect.width
        mid_x = width / 2
        
        data = page.get_text("dict")
        blocks = data.get("blocks", [])
        
        # Collect all spans with position info
        page_spans = []
        
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
        
        # Process spans in reading order
        for span in sorted_spans:
            text = span['text']
            size = span['size']
            
            # Check if this is a title (40pt font)
            if abs(size - TITLE_FONT_SIZE) <= FONT_TOLERANCE:
                # Save previous chapter if exists
                if current_chapter is not None and current_chapter['content'].strip():
                    chapters.append(current_chapter)
                
                # Start new chapter
                current_chapter = {
                    'title': text,
                    'content': ''
                }
                print(f"[DEBUG] Found chapter title on page {page_num + 1}: {text[:50]}")
            
            # Check if this is content (10pt font)
            elif abs(size - CONTENT_FONT_SIZE) <= FONT_TOLERANCE:
                if current_chapter is not None:
                    current_chapter['content'] += text + " "
        
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
    for idx, chapter in enumerate(chapters, start=1):
        title = chapter['title']
        content = simple_clean(chapter['content'])
        
        if not content.strip():
            print(f"[DEBUG] Skipping empty chapter: {title}")
            continue
        
        filename = sanitize_filename(title, idx)
        filepath = output_folder / filename
        
        # Write chapter with title as header
        full_text = f"{title}\n\n{'=' * len(title)}\n\n{content}"
        filepath.write_text(full_text, encoding="utf-8")
        
        print(f"[DEBUG] Saved: {filename} ({len(content)} chars)")
    
    print(f"\n[DEBUG] COMPLETE: Extracted {len(chapters)} chapters to {output_folder}")
    doc.close()

if __name__ == "__main__":
    main()
