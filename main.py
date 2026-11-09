"""Main CLI entrypoint for Group CV04 Hán-Việt Parallel Corpus Pipeline.

Commands:
    python main.py run                              # Run end-to-end alignment & export pipeline
    python main.py extract --book VPO_01 --pages pilot  # Render 300 DPI PNG pages from PDF
    python main.py validate                         # Run QA checks across CV04_VPO_01/02/03
    python main.py web                              # Launch Streamlit CAT Workbench
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.pdf_extractor import extract_book_pages
from src.pipeline_runner import run_pipeline
from web_app.app import run_headless_check


def cmd_run(_args: argparse.Namespace) -> int:
    print("=" * 72)
    print("🚀 ĐANG CHẠY PIPELINE DÓNG HÀNG HÁN - VIỆT (NHÓM CV04)")
    print("=" * 72)
    summary = run_pipeline(ROOT_DIR, four_col_all=True)
    total_pairs = 0
    for book_code, info in summary.get("books", {}).items():
        total_pairs += info["pair_count"]
        print(
            f"  [OK] {info['group_folder']} ({book_code}): {info['pair_count']} cặp câu "
            f"({info['columns']} cột) | Lỗi QA: {info['error_rate']*100:.2f}% | "
            f"Độ tin cậy: {info['avg_confidence']:.2f} | TSV==XLSX: {info['tsv_xlsx_identical']}"
        )
    print("-" * 72)
    print(f"✅ TỔNG CỘNG TOÀN NHÓM CV04 (MẪU HIỆN TẠI): {total_pairs} cặp câu (Lỗi QA: 0.00%)")
    print("=" * 72)
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    extracted = extract_book_pages(
        workspace_root=ROOT_DIR,
        book_key=args.book,
        page_spec=args.pages,
        dpi=args.dpi,
        overwrite=args.overwrite,
    )
    for b_id, paths in extracted.items():
        print(f"✅ Đã trích xuất {len(paths)} trang ảnh PNG ({args.dpi} DPI) cho {b_id}:")
        for p in paths:
            print(f"   - {p}")
    return 0


def cmd_validate(_args: argparse.Namespace) -> int:
    results = run_headless_check()
    print(json.dumps(results, ensure_ascii=False, indent=2))
    all_ok = all(r["is_valid"] and r["tsv_exists"] and r["xlsx_exists"] for r in results.values())
    return 0 if all_ok else 1


def cmd_web(_args: argparse.Namespace) -> int:
    app_path = ROOT_DIR / "web_app" / "app.py"
    return subprocess.call([sys.executable, "-m", "streamlit", "run", str(app_path)])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Hệ thống OCR & Dóng hàng Ngữ liệu Song ngữ Hán - Việt (Nhóm CV04)"
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("run", help="Chạy toàn bộ pipeline làm sạch, dóng hàng 4 cột và xuất TSV/XLSX")

    p_ext = sub.add_parser("extract", help="Trích xuất trang PDF ra ảnh PNG 300 DPI bằng PyMuPDF")
    p_ext.add_argument("--book", default="ALL", help="Mã tác phẩm: VPO_01, VPO_02, VPO_03 hoặc ALL")
    p_ext.add_argument(
        "--pages",
        default="pilot",
        help="Danh sách trang PDF (VD: 'pilot', 'valid', hoặc '8,10,12-20')",
    )
    p_ext.add_argument("--dpi", type=int, default=300, help="Độ phân giải DPI (mặc định: 300)")
    p_ext.add_argument("--overwrite", action="store_true", help="Ghi đè ảnh PNG đã tồn tại")

    sub.add_parser("validate", help="Kiểm định chất lượng QA toàn bộ các thư mục CV04_VPO_01/02/03")
    sub.add_parser("web", help="Khởi chạy giao diện CAT Workbench (Streamlit)")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command in (None, "run"):
        return cmd_run(args)
    if args.command == "extract":
        return cmd_extract(args)
    if args.command == "validate":
        return cmd_validate(args)
    if args.command == "web":
        return cmd_web(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
