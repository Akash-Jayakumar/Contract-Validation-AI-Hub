from typing import List, Dict, Tuple
import re

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
    PREAMBLE = {"WHEREAS", "NOW, THEREFORE"}

    def looks_like_header(line: str) -> bool:
        s = line.strip().replace("—", "-")
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
        # Peek next non-empty line
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
