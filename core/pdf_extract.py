import os
import re
import unicodedata
from typing import List, Dict, Tuple
import fitz  # pymupdf

SENT_SPLIT_RE = re.compile(r'(?<=[。！？!?\.])\s+|(?<=[。！？!?\.])(?=[^\s])')

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()

def split_sentences_multilang(text: str) -> List[str]:
    text = normalize_text(text)
    if not text:
        return []
    parts = SENT_SPLIT_RE.split(text)
    return [p.strip() for p in parts if p and len(p.strip()) >= 4]

def compile_keyword_patterns(
    keywords: List[str],
    use_regex: bool = False,
    english_word_boundary: bool = False
) -> List[Tuple[str, re.Pattern]]:
    patterns = []
    for kw in keywords:
        kw = kw.strip()
        if not kw:
            continue
        if use_regex:
            pat = re.compile(kw, re.IGNORECASE)
        else:
            if english_word_boundary and re.fullmatch(r"[A-Za-z0-9 \-]+", kw):
                escaped = re.escape(kw).replace(r"\ ", r"\s+")
                pat = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
            else:
                pat = re.compile(re.escape(kw), re.IGNORECASE)
        patterns.append((kw, pat))
    return patterns

def list_pdfs(folder: str) -> List[str]:
    pdfs = []
    for root, _, files in os.walk(folder):
        for fn in files:
            if fn.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, fn))
    return pdfs

def extract_pdf_hits(
    pdf_path: str,
    patterns: List[Tuple[str, re.Pattern]],
    dedup: bool = True
) -> List[Dict]:
    results: List[Dict] = []
    seen = set()
    fname = os.path.basename(pdf_path)

    doc = fitz.open(pdf_path)
    for page_idx, page in enumerate(doc, start=1):
        text = page.get_text("text") or ""
        sentences = split_sentences_multilang(text)
        for s in sentences:
            for kw, pat in patterns:
                if pat.search(s):
                    row = {
                        "file": fname,
                        "path": pdf_path,
                        "page": page_idx,
                        "keyword": kw,
                        "sentence": s
                    }
                    if dedup:
                        key = (fname, page_idx, kw, s)
                        if key in seen:
                            continue
                        seen.add(key)
                    results.append(row)
    doc.close()
    return results

def extract_folder_hits(
    folder: str,
    keywords: List[str],
    use_regex: bool,
    english_word_boundary: bool,
    dedup: bool
) -> List[Dict]:
    patterns = compile_keyword_patterns(keywords, use_regex, english_word_boundary)
    all_rows: List[Dict] = []
    for pdf in list_pdfs(folder):
        all_rows.extend(extract_pdf_hits(pdf, patterns, dedup=dedup))
    return all_rows