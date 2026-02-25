from typing import List, Dict
import pandas as pd
from docx import Document


def _safe(s: str) -> str:
    # 强制变成 UTF-8 可写字符串（自动去掉GBK不认识的符号）
    return s.encode("utf-8", errors="ignore").decode("utf-8")


def export_txt(rows: List[Dict], out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(f'{_safe(r["file"])} | Page {_safe(str(r["page"]))} | {_safe(r["keyword"])}\n')
            f.write(_safe(r["sentence"].strip()) + "\n\n")


def export_word(rows: List[Dict], out_path: str) -> None:
    doc = Document()
    doc.add_heading("PDF Evidence Sentences", level=1)
    for r in rows:
        doc.add_paragraph(
            f'{_safe(r["file"])} | Page {_safe(str(r["page"]))} | {_safe(r["keyword"])}'
        )
        doc.add_paragraph(_safe(r["sentence"].strip()))
        doc.add_paragraph("")
    doc.save(out_path)


def export_excel(rows: List[Dict], out_path: str) -> None:
    clean_rows = []
    for r in rows:
        clean_rows.append({
            "file": _safe(str(r["file"])),
            "page": _safe(str(r["page"])),
            "keyword": _safe(str(r["keyword"])),
            "sentence": _safe(str(r["sentence"])),
            "path": _safe(str(r.get("path", "")))
        })

    df = pd.DataFrame(clean_rows)
    df.to_excel(out_path, index=False, engine="openpyxl")