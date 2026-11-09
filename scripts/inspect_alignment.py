#!/usr/bin/env python3
"""Interactive Terminal Alignment Inspector for Hán–Việt Parallel Corpus.

Provides fast terminal inspection, confidence filtering, and statistical summaries:
- Inspect alignment pairs for any book (`HVTT`, `TVLT2`, `TLTVN`)
- Check QA error metrics and confidence score distributions
- Preview parallel columns (`Hán | Dịch âm | Dịch nghĩa | Dịch thơ`)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.exporter_and_qa import read_tsv, validate_pairs
from src.word_aligner import align_words_in_pair, batch_evaluate_word_coverage

BOOK_DIRS = {
    "HVTT": ROOT_DIR / "deliverables" / "HVTT_HanVanTinhTuy" / "04_dong_hang",
    "TVLT2": ROOT_DIR / "deliverables" / "TVLT2_ThoVanLyTran2" / "04_dong_hang",
    "TLTVN": ROOT_DIR / "deliverables" / "TLTVN_TheLoaiTuVN" / "04_dong_hang",
}

BOOK_TSV_FILENAMES = {
    "HVTT": "HVTT_HanVanTinhTuy_parallel.tsv",
    "TVLT2": "TVLT2_ThoVanLyTran2_parallel.tsv",
    "TLTVN": "TLTVN_TheLoaiTuVN_parallel.tsv",
}


def load_alignment_data(book_key: str) -> List[tuple[str, ...]]:
    """Load aligned pairs/rows from the book's parallel TSV deliverable."""
    book_key = book_key.upper().strip()
    folder = BOOK_DIRS.get(book_key)
    filename = BOOK_TSV_FILENAMES.get(book_key)
    if not folder or not filename:
        raise ValueError(f"Unknown book key: {book_key}. Choices: {list(BOOK_DIRS.keys())}")

    tsv_path = folder / filename
    if not tsv_path.is_file():
        # Fallback to short name
        tsv_path = folder / f"{book_key}_parallel.tsv"

    if not tsv_path.is_file():
        raise FileNotFoundError(f"TSV deliverable not found for {book_key} at {tsv_path}")

    return read_tsv(str(tsv_path))


def print_summary(book_key: str, rows: List[tuple[str, ...]]) -> Dict[str, Any]:
    """Validate rows and print formatted summary."""
    report = validate_pairs(rows)
    word_eval = batch_evaluate_word_coverage(rows)
    is_four_col = bool(rows and len(rows[0]) >= 4)

    print("=" * 72)
    print(f"  HÁN–VIỆT CORPUS ALIGNMENT REPORT — [{book_key}]")
    print("=" * 72)
    print(f"  Total Aligned Rows      : {report['total_pairs']}")
    print(f"  Valid Checked Rows      : {report['valid_checked_pairs']}")
    print(f"  Error / Warning Rows    : {report['error_pairs']}")
    print(f"  Error Rate              : {report['error_rate'] * 100:.2f}% (Threshold: <= 30.0%)")
    print(f"  Passes 30% Threshold    : {report['passes_threshold_30pct']}")
    print(f"  Passes 20% Target       : {report['passes_target_20pct']}")
    print(f"  Column Format           : {'4-Column (Hán | Dịch âm | Dịch nghĩa | Dịch thơ)' if is_four_col else '2-Column (Hán | Việt)'}")
    print("-" * 72)
    print(f"  Word Coverage & Confidence (SOTA Grounding):")
    print(f"    - Avg Han Coverage    : {word_eval['avg_han_coverage_pct']:.2f}%")
    print(f"    - Avg Viet Grounding  : {word_eval['avg_viet_coverage_pct']:.2f}%")
    print(f"    - Avg Confidence Score: {word_eval['avg_confidence']:.4f} (High: {word_eval['high_confidence_pairs']}, Med: {word_eval['medium_confidence_pairs']}, Low: {word_eval['low_confidence_pairs']})")
    print("-" * 72)
    print("  Breakdown by Category:")
    for cat, cnt in report["error_breakdown"].items():
        print(f"    - {cat:<18}: {cnt}")
    print("=" * 72)
    report["word_coverage"] = word_eval
    return report


def display_sample_rows(rows: List[tuple[str, ...]], limit: int = 5) -> None:
    """Print formatted preview rows with fine-grained confidence metrics."""
    print(f"\n--- Alignment Preview (First {min(limit, len(rows))} row(s)) ---")
    for idx, row in enumerate(rows[:limit], start=1):
        han = row[0]
        if len(row) >= 4:
            dich_am, dich_nghia, dich_tho = row[1], row[2], row[3]
            combined_v = f"{dich_am} {dich_nghia} {dich_tho}".strip()
            word_res = align_words_in_pair(han, combined_v)
            conf = word_res["confidence_score"]
            han_cov = word_res["han_coverage_pct"]
            print(f"\n[Row {idx:02d}] (Confidence: {conf:.2f} | Han Coverage: {han_cov:.1f}%)")
            print(f"  Hán        : {han}")
            print(f"  Dịch âm    : {dich_am}")
            print(f"  Dịch nghĩa : {dich_nghia if dich_nghia else '(để trống)'}")
            print(f"  Dịch thơ   : {dich_tho if dich_tho else '(không có)'}")
        else:
            viet = row[1] if len(row) > 1 else ""
            word_res = align_words_in_pair(han, viet)
            conf = word_res["confidence_score"]
            han_cov = word_res["han_coverage_pct"]
            print(f"\n[Row {idx:02d}] (Confidence: {conf:.2f} | Han Coverage: {han_cov:.1f}%)")
            print(f"  Hán  : {han}")
            print(f"  Việt : {viet}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect and validate Hán–Việt aligned parallel deliverables."
    )
    parser.add_argument(
        "--book",
        choices=["HVTT", "TVLT2", "TLTVN", "ALL"],
        default="HVTT",
        help="Book key to inspect (default: HVTT).",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print summary statistical QA report.",
    )
    parser.add_argument(
        "--preview",
        type=int,
        default=5,
        help="Number of preview rows to print (default: 5).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw QA report as JSON.",
    )

    args = parser.parse_args(argv)
    targets = ["HVTT", "TVLT2", "TLTVN"] if args.book == "ALL" else [args.book]

    all_reports: Dict[str, Any] = {}
    for b in targets:
        try:
            rows = load_alignment_data(b)
            report = print_summary(b, rows)
            all_reports[b] = report
            if args.preview > 0 and not args.json:
                display_sample_rows(rows, limit=args.preview)
        except Exception as e:
            print(f"[!] Error inspecting {b}: {e}", file=sys.stderr)
            all_reports[b] = {"error": str(e)}

    if args.json:
        print(json.dumps(all_reports, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
