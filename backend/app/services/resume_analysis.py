import re


_WORD_RE = re.compile(r"[a-zA-Z0-9+#.]{2,}")

# Very small stopword list (enough to make keyword overlap meaningful)
_STOP = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
    "you",
    "your",
}


def _tokens(text: str) -> set[str]:
    if not text:
        return set()
    out: set[str] = set()
    for m in _WORD_RE.finditer(text.lower()):
        w = m.group(0).strip(".")
        if w and w not in _STOP:
            out.add(w)
    return out


def score_resume_against_job(*, job_title: str | None, job_description: str | None, resume_text: str | None) -> tuple[float, str]:
    """
    Lightweight, deterministic scorer (no external AI provider required).

    Returns:
      - match_score: float in [0, 1]
      - ai_explanation: human-friendly explanation string
    """
    job_text = f"{job_title or ''}\n{job_description or ''}".strip()
    jt = _tokens(job_text)
    rt = _tokens(resume_text or "")

    if not jt:
        return 0.0, "No job description available to score against."

    if not rt:
        return 0.0, "Could not extract readable text from the uploaded resume, so a match score cannot be computed."

    overlap = jt.intersection(rt)
    # Recall-style score: how much of the job keyword set appears in the resume
    score = len(overlap) / max(1, len(jt))
    score = max(0.0, min(1.0, score))

    top = sorted(overlap)[:12]
    missing = sorted(jt.difference(rt))[:8]

    explanation_parts = [
        f"Matched {len(overlap)} / {len(jt)} job keywords from your resume text.",
    ]
    if top:
        explanation_parts.append("Matched keywords: " + ", ".join(top))
    if missing:
        explanation_parts.append("Consider adding evidence for: " + ", ".join(missing))

    return score, " ".join(explanation_parts)


def extract_text_from_file(*, file_path: str, ext: str | None) -> str:
    """
    Best-effort text extraction.
    - PDF: uses pypdf if available
    - DOCX: uses python-docx if available
    - Fallback: decode raw bytes as UTF-8 (lossy)
    """
    ext_norm = (ext or "").lower()

    if ext_norm == ".pdf":
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(file_path)
            parts = []
            for page in reader.pages:
                try:
                    parts.append(page.extract_text() or "")
                except Exception:
                    continue
            return "\n".join(parts).strip()
        except Exception:
            pass

    if ext_norm == ".docx":
        try:
            import docx  # type: ignore

            d = docx.Document(file_path)
            return "\n".join(p.text for p in d.paragraphs if p.text).strip()
        except Exception:
            pass

    try:
        with open(file_path, "rb") as f:
            raw = f.read()
        return raw.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


# ------------------------- Module 6: Extraction + Cleaning -------------------------

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_MULTISPACE_RE = re.compile(r"[ \t]{2,}")
_MULTINEWLINE_RE = re.compile(r"\n{3,}")
_BULLET_RE = re.compile(r"^[\s\u2022\u00b7\u25cf\u25e6\u25aa\u25ab\u2219\u2043\u2023]+", re.MULTILINE)
_PAGE_MARKER_RE = re.compile(
    r"^\s*(page\s*\d+(\s*of\s*\d+)?)\s*$|^\s*\d+\s*/\s*\d+\s*$|^\s*[-–—]{0,3}\s*\d+\s*[-–—]{0,3}\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_HYPHEN_LINEBREAK_RE = re.compile(r"([A-Za-z])-\n([A-Za-z])")
_MIN_NONWS_CHARS = 30


def extract_text_from_pdf_pages(*, file_path: str) -> list[str]:
    """
    Extract per-page text from a PDF using pypdf.
    Returns a list of page texts (may contain empty strings).
    """
    from pypdf import PdfReader  # type: ignore

    reader = PdfReader(file_path)
    out: list[str] = []
    for page in reader.pages:
        try:
            out.append(page.extract_text() or "")
        except Exception:
            out.append("")
    return out


def extract_text_from_docx(*, file_path: str) -> str:
    """
    Extract plain text from a DOCX using python-docx.
    """
    import docx  # type: ignore

    d = docx.Document(file_path)
    return "\n".join(p.text for p in d.paragraphs if p.text).strip()


def _ocr_pdf_with_tesseract(*, file_path: str) -> tuple[str, list[str]]:
    """
    OCR a PDF by rasterizing pages to images and running pytesseract.\n+\n+    Notes:\n+    - Requires Poppler (for pdf2image) and Tesseract installed on the system.\n+    - We keep this best-effort and return warnings on failure.\n+    """
    warnings: list[str] = []
    try:
        from pdf2image import convert_from_path  # type: ignore
    except Exception:
        return "", ["OCR unavailable: missing python dependency pdf2image."]

    try:
        import pytesseract  # type: ignore
    except Exception:
        return "", ["OCR unavailable: missing python dependency pytesseract."]

    # Optional runtime configuration (esp. on Windows)
    try:
        from ..config import POPPLER_PATH, TESSERACT_CMD  # type: ignore

        if TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    except Exception:
        POPPLER_PATH = None  # type: ignore

    try:
        images = convert_from_path(
            file_path,
            dpi=300,
            fmt="png",
            poppler_path=(POPPLER_PATH or None),  # type: ignore[arg-type]
        )
    except Exception:
        return "", ["OCR failed: could not rasterize PDF pages (Poppler may be missing)."]

    parts: list[str] = []
    for img in images[:12]:  # safety cap
        try:
            parts.append(pytesseract.image_to_string(img) or "")
        except Exception:
            warnings.append("OCR warning: failed to OCR a page.")
            continue

    return "\n\n".join(parts).strip(), warnings


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _strip_control_chars(text: str) -> str:
    return _CONTROL_CHARS_RE.sub("", text)


def _normalize_whitespace(text: str) -> str:
    text = _MULTISPACE_RE.sub(" ", text)
    text = _MULTINEWLINE_RE.sub("\n\n", text)
    return text.strip()


def _fix_hyphenation(text: str) -> str:
    # Join words broken across lines: "devel-\nopment" -> "development"
    return _HYPHEN_LINEBREAK_RE.sub(r"\1\2", text)


def _normalize_bullets(text: str) -> str:
    # Replace leading bullet glyphs with "- "
    return _BULLET_RE.sub("- ", text)


def _remove_page_markers(text: str) -> str:
    return _PAGE_MARKER_RE.sub("", text)


def _repeated_header_footer_lines(page_texts: list[str]) -> set[str]:
    """
    Heuristic: find lines that repeat across >=2 pages in the top/bottom regions.
    These are likely headers/footers (e.g. name/email repeated, page numbers, etc).

    Returns a set of lines to remove (exact match after normalization).
    """
    if len(page_texts) < 2:
        return set()

    def norm_line(line: str) -> str:
        line = _normalize_newlines(line)
        line = _strip_control_chars(line)
        line = _MULTISPACE_RE.sub(" ", line).strip()
        return line

    counts: dict[str, int] = {}
    for p in page_texts:
        lines = [norm_line(l) for l in _normalize_newlines(p).split("\n") if norm_line(l)]
        if not lines:
            continue
        head = lines[:4]
        tail = lines[-4:] if len(lines) >= 4 else lines
        for l in set(head + tail):
            # Ignore tiny or purely numeric lines (handled by page marker remover too)
            if len(l) < 6:
                continue
            if l.isdigit():
                continue
            counts[l] = counts.get(l, 0) + 1

    # Remove lines that appear on at least 2 pages
    return {l for (l, c) in counts.items() if c >= 2}


def clean_extracted_text(*, raw_text: str, page_texts: list[str] | None = None) -> str:
    """
    Clean extracted resume text while preserving context:
    - keep paragraph breaks and headings
    - normalize bullets/whitespace
    - remove headers/footers and page markers
    - fix hyphenation artifacts
    """
    text = raw_text or ""
    text = _normalize_newlines(text)
    text = _strip_control_chars(text)

    # Remove repeated header/footer lines (PDF only; uses per-page texts)
    if page_texts:
        remove = _repeated_header_footer_lines(page_texts)
        if remove:
            cleaned_lines = []
            for l in text.split("\n"):
                nl = _MULTISPACE_RE.sub(" ", l).strip()
                if nl and nl in remove:
                    continue
                cleaned_lines.append(l)
            text = "\n".join(cleaned_lines)

    text = _remove_page_markers(text)
    text = _fix_hyphenation(text)
    text = _normalize_bullets(text)

    # Collapse whitespace but preserve paragraph boundaries
    text = _normalize_whitespace(text)
    return text


def extract_and_clean_resume_text(*, file_path: str, ext: str | None) -> dict:
    """
    Best-effort extraction + cleaning.\n+\n+    Returns a dict:\n+      - clean_text\n+      - raw_len, clean_len\n+      - is_probably_scanned_or_empty\n+      - warnings\n+    """
    warnings: list[str] = []
    ext_norm = (ext or "").lower()

    raw_text = ""
    page_texts: list[str] | None = None

    try:
        if ext_norm == ".pdf":
            try:
                page_texts = extract_text_from_pdf_pages(file_path=file_path)
                raw_text = "\n\n".join(page_texts).strip()
            except Exception:
                warnings.append("Failed to parse PDF text with pypdf.")
                raw_text = ""

        elif ext_norm == ".docx":
            try:
                raw_text = extract_text_from_docx(file_path=file_path)
            except Exception:
                warnings.append("Failed to parse DOCX text with python-docx.")
                raw_text = ""

        else:
            # Unknown extension: fall back to old behavior
            raw_text = extract_text_from_file(file_path=file_path, ext=ext_norm)
    except Exception:
        warnings.append("Unexpected error during extraction.")
        raw_text = ""

    # Fallback: if extraction yields nothing, try decoding bytes (handles some malformed files)
    if not raw_text:
        try:
            with open(file_path, "rb") as f:
                raw = f.read()
            decoded = raw.decode("utf-8", errors="ignore").strip()
            if decoded:
                warnings.append("Used UTF-8 fallback decode due to empty extraction.")
                raw_text = decoded
        except Exception:
            # nothing else we can do
            pass

    clean = clean_extracted_text(raw_text=raw_text, page_texts=page_texts)

    # Detect scanned/empty PDFs: very low signal after cleaning
    non_ws = re.sub(r"\s+", "", clean)
    is_emptyish = len(non_ws) < _MIN_NONWS_CHARS
    if is_emptyish:
        if ext_norm == ".pdf":
            # OCR fallback for scanned PDFs
            ocr_text, ocr_warnings = _ocr_pdf_with_tesseract(file_path=file_path)
            warnings.extend(ocr_warnings)
            if ocr_text:
                clean = clean_extracted_text(raw_text=ocr_text, page_texts=None)
                non_ws2 = re.sub(r"\s+", "", clean)
                is_emptyish = len(non_ws2) < _MIN_NONWS_CHARS
            if is_emptyish:
                warnings.append("PDF appears scanned or has no extractable text (OCR did not yield usable text).")
        elif ext_norm == ".docx":
            warnings.append("DOCX appears empty or has no extractable text.")
        else:
            warnings.append("File has no extractable text.")
        if is_emptyish:
            clean = ""

    return {
        "clean_text": clean,
        "raw_len": len(raw_text or ""),
        "clean_len": len(clean or ""),
        "is_probably_scanned_or_empty": bool(is_emptyish),
        "warnings": warnings,
    }

