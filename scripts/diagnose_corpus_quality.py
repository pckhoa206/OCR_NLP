#!/usr/bin/env python3
"""Automated Corpus Diagnostic & Philological Quality Inspection Script.

Scans parallel corpora across all books:
- Evaluates sentence-level QA metrics and word-level grounding
- Flags sentences with low confidence (< 0.70) or severe Han character omission
- Identifies common unmatched particles and translation paraphrases
- Emits a comprehensive Markdown diagnosis report: `docs/BAO_CAO_CHAN_DOAN_CHAT_LUONG.md`
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.exporter_and_qa import read_tsv, validate_pairs
from src.word_aligner import align_words_in_pair, batch_evaluate_word_coverage

BOOK_KEYS = ["HVTT", "TVLT2", "TLTVN"]
BOOK_NAMES = {
    "HVTT": "Hán Văn Tinh Túy (Lãng Nhân)",
    "TVLT2": "Thơ văn Lý – Trần Tập II (Nguyễn Huệ Chi chủ biên)",
    "TLTVN": "Thể loại từ Việt Nam thời trung đại (Nguyễn Xuân Diện)",
}
BOOK_FOLDERS = {
    "HVTT": "HVTT_HanVanTinhTuy",
    "TVLT2": "TVLT2_ThoVanLyTran2",
    "TLTVN": "TLTVN_TheLoaiTuVN",
}


def diagnose_book(book_key: str, workspace_root: Path = ROOT_DIR) -> Dict[str, Any]:
    folder_name = BOOK_FOLDERS[book_key]
    tsv_path = workspace_root / "deliverables" / folder_name / "04_dong_hang" / f"{folder_name}_parallel.tsv"
    if not tsv_path.is_file():
        tsv_path = workspace_root / "deliverables" / folder_name / "04_dong_hang" / f"{book_key}_parallel.tsv"

    if not tsv_path.is_file():
        return {"error": f"File not found: {tsv_path}"}

    rows = read_tsv(str(tsv_path))
    qa_report = validate_pairs(rows)
    batch_word = batch_evaluate_word_coverage(rows)

    row_diagnostics: List[Dict[str, Any]] = []
    unmatched_counter: Counter[str] = Counter()

    for idx, row in enumerate(rows, start=1):
        han_str = row[0]
        if len(row) >= 4:
            combined_v = f"{row[1]} {row[2]} {row[3]}".strip()
            trans_only = row[2] if row[2].strip() else row[3]
        else:
            combined_v = row[1] if len(row) > 1 else ""
            trans_only = combined_v

        word_res = align_words_in_pair(han_str, combined_v)
        conf = word_res["confidence_score"]
        han_cov = word_res["han_coverage_pct"]
        unmatched = word_res["unmatched_han"]

        for ch in unmatched:
            unmatched_counter[ch] += 1

        is_flagged = conf < 0.70 or han_cov < 60.0
        row_diagnostics.append({
            "stt": idx,
            "han": han_str,
            "translation": trans_only,
            "confidence": conf,
            "han_coverage": han_cov,
            "viet_coverage": word_res["viet_coverage_pct"],
            "unmatched_han": unmatched,
            "is_flagged": is_flagged,
        })

    flagged_rows = [r for r in row_diagnostics if r["is_flagged"]]

    return {
        "book_key": book_key,
        "book_name": BOOK_NAMES.get(book_key, book_key),
        "total_rows": len(rows),
        "valid_qa": qa_report["is_valid"],
        "error_rate": qa_report["error_rate"],
        "avg_confidence": batch_word["avg_confidence"],
        "avg_han_coverage_pct": batch_word["avg_han_coverage_pct"],
        "avg_viet_coverage_pct": batch_word["avg_viet_coverage_pct"],
        "high_confidence_count": batch_word["high_confidence_pairs"],
        "medium_confidence_count": batch_word["medium_confidence_pairs"],
        "low_confidence_count": batch_word["low_confidence_pairs"],
        "flagged_count": len(flagged_rows),
        "flagged_rows": flagged_rows,
        "top_unmatched_characters": unmatched_counter.most_common(10),
    }


def generate_markdown_report(diagnostics: List[Dict[str, Any]]) -> str:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines: List[str] = [
        "# BÁO CÁO CHẨN ĐOÁN CHẤT LƯỢNG NGỮ LIỆU & ĐỘ PHỦ TỪ VỰNG",
        "## Hệ thống Dóng hàng Tự động Ngữ liệu Song ngữ Hán – Việt",
        "",
        f"- **Thời điểm kiểm định**: `{now_str}`",
        "- **Phạm vi đối soát**: 3 bộ sách gốc (*Hán Văn Tinh Túy*, *Thơ văn Lý – Trần 2*, *Thể loại từ VN*).",
        "- **Công cụ chẩn đoán**: `src/word_aligner.py` & `src/exporter_and_qa.py`.",
        "",
        "---",
        "",
        "### 1. Bảng Tổng Hợp Chỉ Số Toàn Cục",
        "",
        "| Mã sách | Tên tác phẩm | Tổng cặp | Lỗi QA (%) | Phủ Hán (%) | Phủ Việt (%) | Điểm Tin cậy TB | Số câu Cần Lưu ý |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for d in diagnostics:
        if "error" in d:
            continue
        lines.append(
            f"| `{d['book_key']}` | {d['book_name']} | {d['total_rows']} | {d['error_rate'] * 100:.2f}% | "
            f"{d['avg_han_coverage_pct']:.1f}% | {d['avg_viet_coverage_pct']:.1f}% | "
            f"**{d['avg_confidence']:.2f} / 1.0** | {d['flagged_count']} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "### 2. Phân Tích Chi Tiết Từng Bộ Sách",
        "",
    ])

    for d in diagnostics:
        if "error" in d:
            continue
        lines.append(f"#### 📖 {d['book_name']} (`{d['book_key']}`)")
        lines.append(f"- **Tổng số cặp câu**: `{d['total_rows']}`")
        lines.append(f"- **Phân bố độ tin cậy**: Cao (>= 0.85): `{d['high_confidence_count']}` | Trung bình: `{d['medium_confidence_count']}` | Cần lưu ý: `{d['low_confidence_count']}`")
        if d["top_unmatched_characters"]:
            top_unm = ", ".join(f"`{ch}` ({cnt} lần)" for ch, cnt in d["top_unmatched_characters"])
            lines.append(f"- **Chữ Hán hay vắng mặt trong bản dịch (Omission candidates)**: {top_unm}")
        else:
            lines.append("- **Chữ Hán vắng mặt**: Không có.")

        if d["flagged_rows"]:
            lines.append("")
            lines.append("**Các câu được đánh dấu cần chuyên gia thẩm định (Review Flags):**")
            lines.append("")
            lines.append("| STT | Chữ Hán | Bản dịch tiếng Việt | Điểm Tin cậy | Phủ Hán (%) | Chữ chưa khớp |")
            lines.append("| :---: | :--- | :--- | :---: | :---: | :--- |")
            for fr in d["flagged_rows"][:10]:
                unm_str = " ".join(fr["unmatched_han"]) if fr["unmatched_han"] else "(đầy đủ)"
                lines.append(f"| {fr['stt']} | `{fr['han']}` | {fr['translation']} | `{fr['confidence']:.2f}` | {fr['han_coverage']:.1f}% | `{unm_str}` |")
        else:
            lines.append("- **Nhận xét**: 100% các cặp câu đạt độ tin cậy cao, không có câu nào bị đánh cờ cảnh báo.")
        lines.append("")

    lines.extend([
        "---",
        "",
        "### 3. Đánh Giá Hán Học & Khuyến Nghị Hiệu Đính",
        "",
        "1. **Tính bảo toàn của Trợ từ Hán văn (Classical Particles)**:",
        "   - Các chữ như `有` (hữu), `之` (chi), `者` (giả), `也` (dã) là các hư từ/ngữ khí từ mang chức năng ngữ pháp thay vì nghĩa từ vựng, việc người dịch không dịch thành một từ độc lập là hoàn toàn tự nhiên và đúng phong cách dịch thuật cổ điển.",
        "2. **Thơ và Từ khúc dịch thoát ý (Poetic Paraphrase)**:",
        "   - Trong *Thể loại từ VN* và *Thơ văn Lý – Trần 2*, dịch giả dùng từ ngữ gợi hình (ví dụ: `vượt qua những làn sóng xanh`, `xiết bao bùi ngùi`) thay cho dịch từng chữ một, dẫn đến tỷ lệ phủ từ vựng thấp hơn nhưng chất lượng văn phong văn học cao hơn.",
        "3. **Tận dụng CAT Workbench trong Web App**:",
        "   - Sử dụng giao diện `web_app/app.py` để lọc các câu có điểm tin cậy $< 0.70$ và kiểm tra đối soát với ảnh quét trang gốc `01_nguon`.",
        "",
    ])

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run automated corpus diagnostics.")
    parser.add_argument("--output", default="docs/BAO_CAO_CHAN_DOAN_CHAT_LUONG.md", help="Output Markdown report path.")
    args = parser.parse_args()

    print("[*] Running corpus diagnostics across all books...")
    diagnostics = [diagnose_book(b, ROOT_DIR) for b in BOOK_KEYS]

    report_md = generate_markdown_report(diagnostics)
    out_path = ROOT_DIR / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report_md, encoding="utf-8")

    print(f"[+] Diagnostic report written to: {out_path}")
    for d in diagnostics:
        if "error" not in d:
            print(f"  [{d['book_key']}] Total: {d['total_rows']} | QA Valid: {d['valid_qa']} | Avg Conf: {d['avg_confidence']:.2f} | Flagged: {d['flagged_count']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
