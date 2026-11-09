#!/usr/bin/env python3
"""Full-Scale Kaggle GPU / Local OCR Inference Orchestrator.

Processes high-resolution page scans across all 3 books:
- `HVTT_HanVanTinhTuy`
- `TVLT2_ThoVanLyTran2`
- `TLTVN_TheLoaiTuVN`

Supports:
- Local fast deterministic mock mode (`--mock` / `--dry-run`)
- Kaggle GPU inference mode (`--gpu`) with PaddleOCR & VietOCR
- Per-book filtering (`--book HVTT`) and page limits (`--max-pages N`)
- Detailed execution timing, JSONL logs, and summary reports
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from kaggle_ocr import ocr_pipeline_kaggle


def run_full_inference(
    workspace_root: Path = ROOT_DIR,
    book_filter: Optional[str] = None,
    mock: bool = True,
    max_pages: Optional[int] = None,
    header_ratio: float = 0.07,
) -> Dict[str, Any]:
    """Execute OCR inference on all discovered page images across manifest books."""
    manifest_path = workspace_root / "config" / "book_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found at {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    books = manifest.get("books", {})

    target_books = [book_filter] if book_filter else ["HVTT", "TVLT2", "TLTVN"]
    results_by_book: Dict[str, Any] = {}
    total_pages_all = 0
    start_time = time.perf_counter()

    for book_key in target_books:
        if book_key not in books:
            print(f"[!] Warning: Book '{book_key}' not found in manifest. Skipping.")
            continue

        cfg = books[book_key]
        deliverable_dir = workspace_root / cfg["deliverable_dir"]
        source_dir = workspace_root / cfg["source_dir"]

        argv: List[str] = [
            "--input-dir", str(source_dir),
            "--output-dir", str(deliverable_dir),
            "--book-type", book_key,
            "--header-ratio", str(header_ratio),
        ]
        if mock:
            argv.append("--mock")
        if max_pages is not None and max_pages > 0:
            argv.extend(["--max-pages", str(max_pages)])

        print(f"[{book_key}] Launching OCR inference (mock={mock}, max_pages={max_pages})...")
        t0 = time.perf_counter()
        rc = ocr_pipeline_kaggle.main(argv)
        elapsed = time.perf_counter() - t0

        if rc != 0:
            raise RuntimeError(f"OCR inference failed for {book_key} (exit code {rc})")

        # Read back summary written by ocr_pipeline_kaggle
        summary_file = deliverable_dir / "02_ocr_tho" / "ocr_run_summary.json"
        summary_data: Dict[str, Any] = {}
        if summary_file.is_file():
            try:
                summary_data = json.loads(summary_file.read_text(encoding="utf-8"))
            except Exception:
                summary_data = {}

        pages_count = summary_data.get("pages_processed", 0)
        total_pages_all += pages_count
        results_by_book[book_key] = {
            "code": cfg["code"],
            "pages_processed": pages_count,
            "elapsed_seconds": round(elapsed, 3),
            "output_dir": str(deliverable_dir / "02_ocr_tho"),
        }
        print(f"[{book_key}] Completed {pages_count} page(s) in {elapsed:.2f}s.")

    total_elapsed = time.perf_counter() - start_time
    summary: Dict[str, Any] = {
        "status": "SUCCESS",
        "mode": "mock" if mock else "gpu",
        "total_pages_processed": total_pages_all,
        "total_elapsed_seconds": round(total_elapsed, 3),
        "books": results_by_book,
    }

    # Write global summary report
    global_summary_file = workspace_root / "deliverables" / "full_ocr_summary.json"
    global_summary_file.parent.mkdir(parents=True, exist_ok=True)
    global_summary_file.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run full-scale OCR inference across all corpus books."
    )
    parser.add_argument(
        "--book",
        choices=["HVTT", "TVLT2", "TLTVN"],
        default=None,
        help="Filter to a single book.",
    )
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="Enable GPU execution (requires paddleocr & vietocr). Default is deterministic mock.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="Use deterministic fast mock mode (default).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maximum pages per book to process.",
    )
    parser.add_argument(
        "--header-ratio",
        type=float,
        default=0.07,
        help="Running header crop ratio (default: 0.07).",
    )

    args = parser.parse_args(argv)
    use_mock = not args.gpu

    summary = run_full_inference(
        workspace_root=ROOT_DIR,
        book_filter=args.book,
        mock=use_mock,
        max_pages=args.max_pages,
        header_ratio=args.header_ratio,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
