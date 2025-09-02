from typing import List, Dict, Tuple
import re

try:
    import fitz  # PyMuPDF
    HAVE_FITZ = hasattr(fitz, "open")
except Exception:
    fitz = None
    HAVE_FITZ = False

def section_text_best(pdf_path: str, raw_text: str | None = None):
    if HAVE_FITZ:
        return section_text_bold_aware(pdf_path)
    else:
        # fall back to text-only (no bold info)
        if raw_text is None:
            from pdfminer.high_level import extract_text
            raw_text = extract_text(pdf_path) or ""
        return section_text_with_pages([(1, raw_text)])

def section_text_with_pages(paged_text: List[Tuple[int, str]], max_title_len: int = 160) -> List[Dict[str, object]]:
    """
    Input: paged_text = [(page_no (1-based), page_text), ...]
    Output: list of sections:
    { "title": str, "text": str, "page_start": int, "page_end": int }
    """

    def is_all_caps(line: str) -> bool:
        s = line.strip()
        if len(s) < 3 or len(s) > 160:
            return False
        ok = all(ch.isupper() or ch.isdigit() or ch in " -_/&(),.'’'\":;." for ch in s)
        return ok and any(c.isalpha() for c in s)

    RE_NUMERIC = re.compile(r"^(?:\d+(?:\.\d+)*[.)]?)\s+[A-Z]")
    RE_SECTION = re.compile(r"^(?:Section|Article)\s+\d+(?:\.\d+)*\b", re.IGNORECASE)
    RE_LETTERED = re.compile(r"^[A-Z][.)]\s+[A-Z]")
    RE_TITLE_CASE = re.compile(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,7}$")
    RE_DEF_NUM = re.compile(r"^\s*(\d+\.\d+)\s*[\"']?([A-Za-z][^\"'\n]+)[\"']?\s*", re.UNICODE)
    RE_DEF_SPLIT_INLINE = re.compile(r"\s(?=(\d+\.\d+)[\"'\s])")
    PREAMBLE = {"WHEREAS", "NOW, THEREFORE"}

    def looks_like_header(line: str) -> bool:
        s = line.strip().replace("—", "-")
        if RE_DEF_NUM.match(s):
            return True
        return bool(RE_SECTION.match(s) or RE_NUMERIC.match(s) or RE_LETTERED.match(s) or RE_TITLE_CASE.match(s))

    def merge_soft_wraps(lines: List[str]) -> List[str]:
        merged, buf = [], ""
        for ln in lines:
            ln = ln.rstrip()
            if not ln.strip():
                if buf:
                    merged.append(buf.strip())
                    buf = ""
                merged.append("")
                continue
            if buf:
                if buf.endswith("-") and ln and ln.islower():
                    buf = buf[:-1] + ln.strip()
                    continue
                if (not buf.endswith((".", "!", "?", ":", ";"))) and not looks_like_header(ln):
                    buf += " " + ln.strip()
                    continue
                merged.append(buf.strip())
                buf = ln.strip()
            else:
                buf = ln.strip()
        if buf:
            merged.append(buf.strip())
        return merged

    def first_sentence(text: str, limit: int) -> str:
        s = text.strip()
        for sep in [". ", "! ", "? ", "\n", "\r"]:
            idx = s.find(sep)
            if idx != -1:
                s = s[: idx + 1]
                break
        s = " ".join(s.split())
        if len(s) > limit:
            s = s[:limit].rstrip(" ,;:.-") + "…"
        return s or "Untitled"

    # Build a flat list of (page_no, line_text), preserving order
    lines_with_pages: List[Tuple[int, str]] = []
    for pno, ptxt in paged_text:
        for ln in ptxt.splitlines():
            lines_with_pages.append((pno, ln))

    sections: List[Dict[str, object]] = []
    cur_title: str | None = None
    cur_body: List[str] = []
    cur_min_page: int | None = None
    cur_max_page: int | None = None

    def flush():
        nonlocal cur_title, cur_body, cur_min_page, cur_max_page
        if not cur_body and not cur_title:
            return
        body_text = "\n".join(merge_soft_wraps(cur_body)).strip()
        title = (cur_title or first_sentence(body_text, max_title_len)).strip()
        page_start = cur_min_page or 1
        page_end = cur_max_page or page_start
        sections.append({
            "title": title,
            "text": body_text,
            "page_start": int(page_start),
            "page_end": int(page_end)
        })
        cur_title, cur_body, cur_min_page, cur_max_page = None, [], None, None

    i = 0
    while i < len(lines_with_pages):
        pno, ln = lines_with_pages[i]
        ln_stripped = ln.strip()
        # 1) If multiple definitions were OCR-glued into the same line, split inline
        if RE_DEF_NUM.search(ln) and (" 1." in ln or RE_DEF_SPLIT_INLINE.search(ln)):
            parts = []
            tokens = list(RE_DEF_NUM.finditer(ln))
            idxs = [m.start() for m in tokens]
            if idxs and idxs[0] != 0:
                idxs = [0] + idxs
            idxs.append(len(ln))
            for a, b in zip(idxs, idxs[1:]):
                seg = ln[a:b].strip()
                if seg:
                    parts.append(seg)
            for seg in parts:
                hdr = None
                m = RE_DEF_NUM.match(seg)
                if m:
                    num = m.group(1)
                    term = m.group(2).strip().strip(" .:;,-—")
                    title = f"{num} {term}"
                    rest = seg[m.end():].lstrip()
                    hdr = (title, rest)
                if hdr:
                    if cur_title is not None or cur_body:
                        flush()
                    title, after = hdr
                    cur_title = title
                    if after:
                        cur_body.append(after)
                else:
                    cur_body.append(seg)
            i += 1
            continue
        # 2) Regular definition header on a single line
        hdr = None
        m = RE_DEF_NUM.match(ln)
        if m:
            num = m.group(1)
            term = m.group(2).strip().strip(" .:;,-—")
            title = f"{num} {term}"
            rest = ln[m.end():].lstrip()
            hdr = (title, rest)
        if hdr:
            if cur_title is not None or cur_body:
                flush()
            title, after = hdr
            cur_title = title
            if after:
                cur_body.append(after)
            i += 1
            continue
        # 3) Other headers (Section/Article/A./3.)
        is_next_header = False
        j = i + 1
        while j < len(lines_with_pages) and not lines_with_pages[j][1].strip():
            j += 1
        next_line = lines_with_pages[j][1].strip() if j < len(lines_with_pages) else ""
        is_next_header = next_line and (is_all_caps(next_line) or looks_like_header(next_line))
        if ln_stripped and (is_all_caps(ln_stripped) or looks_like_header(ln_stripped) or ln_stripped in PREAMBLE) and (len(ln_stripped) <= 160 or not is_next_header):
            if cur_title is not None or cur_body:
                flush()
            cur_title = " ".join(ln_stripped.split())
            cur_min_page = pno if cur_min_page is None else min(cur_min_page, pno)
            cur_max_page = pno if cur_max_page is None else max(cur_max_page, pno)
            i += 1
            continue
        # accumulate body + track pages
        cur_body.append(ln)
        cur_min_page = pno if cur_min_page is None else min(cur_min_page, pno)
        cur_max_page = pno if cur_max_page is None else max(cur_max_page, pno)
        i += 1

    flush()
    # drop empty
    return [s for s in sections if s["title"] or s["text"]]


# New font-style aware sectioning functions

RE_DEF = re.compile(r"^\s*(\d+\.\d+)\s*[\"']?([A-Za-z][^\"'\n]+)[\"']?\s")
RE_LETTERED = re.compile(r"^\s*[A-Z][.)]\s+[A-Z]")
RE_SECTION = re.compile(r"^\s*(Section|Article)\s+\d+(?:\.\d+)*\b", re.IGNORECASE)
RE_INLINE_SPLIT = re.compile(r"\s(?=(\d+\.\d+)[\"'\s])")

def is_bold_span(span: dict) -> bool:
    font = (span.get("font") or "").lower()
    flags = int(span.get("flags") or 0)
    return ("bold" in font) or ((flags & 2) != 0)

def extract_lines_with_style(pdf_path: str) -> List[Tuple[int, str, bool]]:
    """
    Returns [(page_no, line_text, first_span_bold)]
    """
    out: List[Tuple[int, str, bool]] = []
    doc = fitz.open(pdf_path)
    for pno, page in enumerate(doc, start=1):
        pd = page.get_text("dict")
        for block in pd.get("blocks", []):
            if block.get("type") != 0:  # text only
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                txt = "".join(s.get("text", "") for s in spans).strip()
                if not txt:
                    continue
                first_bold = is_bold_span(spans[0]) if spans else False
                out.append((pno, txt, first_bold))
    return out

def is_title(line: str, first_bold: bool) -> Tuple[bool, str, str]:
    # Returns (is_title, normalized_title, remainder_after_title)
    if not first_bold:
        return (False, "", "")
    s = line.strip()
    m = RE_DEF.match(s)
    if m:
        num, term = m.group(1), m.group(2).strip().strip(" .:;,-—[]()")
        rest = s[m.end():].lstrip()
        return (True, f"{num} {term}", rest)
    if RE_LETTERED.match(s):
        # First token is bold lettered subclause; use whole line as title, remainder empty
        return (True, " ".join(s.split()), "")
    if RE_SECTION.match(s):
        return (True, " ".join(s.split()), "")
    return (False, "", "")

def section_text_bold_aware(pdf_path: str, max_title_len: int = 160) -> List[Dict[str, object]]:
    lines = extract_lines_with_style(pdf_path)
    sections: List[Dict[str, object]] = []
    cur_title = None
    cur_body: List[str] = []
    cur_ps, cur_pe = None, None

    def flush():
        nonlocal cur_title, cur_body, cur_ps, cur_pe
        if cur_title is None and not cur_body:
            return
        body = "\n".join(cur_body).strip()
        title = (cur_title or (body[:max_title_len].rstrip(" ,;:.-") + "…" if body else "Untitled")).strip()
        sections.append({"title": title, "text": body, "page_start": cur_ps, "page_end": cur_pe})
        cur_title, cur_body, cur_ps, cur_pe = None, [], None, None

    i = 0
    while i < len(lines):
        pno, raw, first_bold = lines[i]
        # Split inline glued definitions
        segs = [raw]
        if RE_DEF.search(raw) and RE_INLINE_SPLIT.search(raw):
            parts = []
            tokens = list(RE_DEF.finditer(raw))
            idxs = [m.start() for m in tokens]
            if idxs and idxs != 0:
                idxs = [0] + idxs
            idxs.append(len(raw))
            for a, b in zip(idxs, idxs[1:]):
                seg = raw[a:b].strip()
                if seg:
                    parts.append(seg)
            segs = parts

        for seg in segs:
            is_hdr, title, rest = is_title(seg, first_bold)
            if is_hdr:
                if cur_title is not None or cur_body:
                    flush()
                cur_title = title[:max_title_len]
                cur_ps = cur_pe = pno
                if rest:
                    cur_body.append(rest)
            else:
                cur_body.append(seg)
                cur_ps = pno if cur_ps is None else min(cur_ps, pno)
                cur_pe = pno if cur_pe is None else max(cur_pe, pno)
        i += 1

    flush()
    # Post-fix: demote overly long titles into body if body empty
    fixed = []
    for s in sections:
        t, b = s["title"].strip(), (s["text"] or "").strip()
        if not b and len(t) > 140:
            fixed.append({"title": t[:120].rstrip(" ,;:.-") + "…", "text": t, "page_start": s["page_start"], "page_end": s["page_end"]})
        else:
            fixed.append(s)
    return fixed
