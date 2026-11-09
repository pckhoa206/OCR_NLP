"""Interactive Visual Alignment & QA Verification Web Application.

A lightweight, production-ready Streamlit app for exploring, searching,
and verifying bilingual Hán–Việt aligned parallel corpora for Group CV04.

Usage:
    streamlit run web_app/app.py
    python main.py web
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.exporter_and_qa import read_tsv, validate_pairs
from src.word_aligner import align_words_in_pair, batch_evaluate_word_coverage
from src.workbench_editor import (
    delete_row,
    edit_row,
    merge_rows,
    save_and_reexport_corpus,
)

BOOK_METADATA = {
    "VPO_01": {
        "title": "Hán Văn Tinh Túy",
        "author": "Lãng Nhân (Phùng Tất Đắc)",
        "folder": ROOT_DIR / "CV04_VPO_01",
        "tsv": ROOT_DIR / "CV04_VPO_01" / "04_dong_hang" / "VPO_01_parallel.tsv",
        "xlsx": ROOT_DIR / "CV04_VPO_01" / "04_dong_hang" / "VPO_01_parallel.xlsx",
        "img_dir": ROOT_DIR / "CV04_VPO_01" / "01_nguon",
        "is_four_col": True,
    },
    "VPO_02": {
        "title": "Thể loại từ VN thời trung đại",
        "author": "Phạm Văn Ánh / Nguyễn Xuân Diện – Nguyễn Quảng Tuân",
        "folder": ROOT_DIR / "CV04_VPO_02",
        "tsv": ROOT_DIR / "CV04_VPO_02" / "04_dong_hang" / "VPO_02_parallel.tsv",
        "xlsx": ROOT_DIR / "CV04_VPO_02" / "04_dong_hang" / "VPO_02_parallel.xlsx",
        "img_dir": ROOT_DIR / "CV04_VPO_02" / "01_nguon",
        "is_four_col": True,
    },
    "VPO_03": {
        "title": "Thơ văn Lý – Trần (Tập II – Quyển Thượng)",
        "author": "Nguyễn Huệ Chi (chủ biên)",
        "folder": ROOT_DIR / "CV04_VPO_03",
        "tsv": ROOT_DIR / "CV04_VPO_03" / "04_dong_hang" / "VPO_03_parallel.tsv",
        "xlsx": ROOT_DIR / "CV04_VPO_03" / "04_dong_hang" / "VPO_03_parallel.xlsx",
        "img_dir": ROOT_DIR / "CV04_VPO_03" / "01_nguon",
        "is_four_col": True,
    },
}


def load_book_rows(book_key: str) -> List[tuple[str, ...]]:
    """Read parallel TSV deliverable for a given book."""
    meta = BOOK_METADATA.get(book_key)
    if not meta:
        return []
    tsv_path = meta["tsv"]
    if not tsv_path.is_file():
        return []
    return read_tsv(str(tsv_path))


def run_headless_check() -> Dict[str, Any]:
    """Verify all book datasets can be loaded and validated headlessly."""
    results = {}
    for key, meta in BOOK_METADATA.items():
        rows = load_book_rows(key)
        report = validate_pairs(rows)
        coverage = batch_evaluate_word_coverage(rows)
        results[key] = {
            "folder": meta["folder"].name,
            "title": meta["title"],
            "row_count": len(rows),
            "is_valid": report["is_valid"],
            "error_rate": report["error_rate"],
            "avg_confidence": coverage["avg_confidence"],
            "avg_han_coverage_pct": coverage["avg_han_coverage_pct"],
            "tsv_exists": meta["tsv"].is_file(),
            "xlsx_exists": meta["xlsx"].is_file(),
        }
    return results


def run_streamlit_app() -> None:
    """Streamlit graphical interactive application."""
    import streamlit as st  # type: ignore

    st.set_page_config(
        page_title="CV04 — Hán–Việt Parallel Corpus Explorer",
        page_icon="📜",
        layout="wide",
    )

    st.title("📜 CV04 — Hán–Việt Parallel Corpus Explorer & CAT Workbench")
    st.markdown(
        "Nền tảng trực quan hóa, đối soát và hiệu đính ngữ liệu song ngữ Hán – Việt "
        "theo quy chuẩn **Lab 2. Dóng hàng Hán-Việt.pdf** & hướng dẫn của **chị Lưu Như** (Nhóm `CV04`)."
    )

    st.sidebar.header("Bộ lọc & Lựa chọn tư liệu")
    book_choice = st.sidebar.selectbox(
        "Chọn mã tác phẩm:",
        options=list(BOOK_METADATA.keys()),
        format_func=lambda k: f"CV04_{k} — {BOOK_METADATA[k]['title']}",
    )

    meta = BOOK_METADATA[book_choice]
    rows = load_book_rows(book_choice)
    qa_report = validate_pairs(rows)
    coverage_report = batch_evaluate_word_coverage(rows)

    # Top Metric KPIs
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Tổng số cặp câu", f"{len(rows):,}")
    with col2:
        st.metric("Số cặp hợp lệ", f"{qa_report['valid_pairs']:,}")
    with col3:
        error_pct = qa_report["error_rate"] * 100
        st.metric("Tỷ lệ lỗi QA", f"{error_pct:.2f}%", delta="Chuẩn <= 30%")
    with col4:
        st.metric("Bao phủ Hán tự", f"{coverage_report['avg_han_coverage_pct']:.1f}%")
    with col5:
        st.metric("Điểm tin cậy (SOTA)", f"{coverage_report['avg_confidence']:.2f}/1.0")

    st.divider()

    # Search filter
    search_query = st.sidebar.text_input("Tìm kiếm từ khóa (Hán / Việt / [MASK]):", "")
    filtered_rows = rows
    if search_query.strip():
        q = search_query.strip().lower()
        filtered_rows = [
            r for r in rows if any(q in str(cell).lower() for cell in r)
        ]
        st.info(f"Tìm thấy **{len(filtered_rows)}** dòng khớp với từ khóa `{search_query}`.")

    # Main Parallel Table
    st.subheader(f"Dữ liệu Dóng hàng 4 Cột — CV04_{book_choice}: {meta['title']} ({meta['author']})")

    table_data = []
    for idx, r in enumerate(filtered_rows, start=1):
        han_txt = r[0]
        if len(r) >= 4:
            combined_v = f"{r[1]} {r[2]} {r[3]}".strip()
            w_res = align_words_in_pair(han_txt, combined_v)
            conf_val = w_res["confidence_score"]
            badge = f"{conf_val:.2f} ({'Cao' if conf_val >= 0.8 else 'TB'})"
            table_data.append({
                "STT": idx,
                "Hán": r[0],
                "Dịch âm": r[1],
                "Dịch nghĩa": r[2],
                "Dịch thơ": r[3],
                "Độ tin cậy": badge,
            })
        else:
            viet_txt = r[1] if len(r) > 1 else ""
            w_res = align_words_in_pair(han_txt, viet_txt)
            conf_val = w_res["confidence_score"]
            badge = f"{conf_val:.2f} ({'Cao' if conf_val >= 0.8 else 'TB'})"
            table_data.append({
                "STT": idx,
                "Hán": r[0],
                "Dịch nghĩa tiếng Việt": viet_txt,
                "Độ tin cậy": badge,
            })

    st.dataframe(table_data, use_container_width=True, height=450)

    # Download Buttons
    st.subheader("Xuất bản Dữ liệu Chuẩn")
    dcol1, dcol2 = st.columns(2)
    tsv_file = meta["tsv"]
    xlsx_file = meta["xlsx"]

    if tsv_file.is_file():
        with dcol1:
            st.download_button(
                label=f"Tải file TSV ({tsv_file.name})",
                data=tsv_file.read_bytes(),
                file_name=tsv_file.name,
                mime="text/tab-separated-values",
            )
    if xlsx_file.is_file():
        with dcol2:
            st.download_button(
                label=f"Tải file XLSX 2 Sheet ({xlsx_file.name})",
                data=xlsx_file.read_bytes(),
                file_name=xlsx_file.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    # CAT Workbench Interactive Editor
    st.divider()
    st.subheader("🛠️ CAT Workbench — Hiệu đính Trực tiếp & Tái xuất bản")
    with st.expander("Mở Bàn làm việc Hiệu đính (Interactive Editor)", expanded=False):
        if rows:
            row_idx = st.number_input(
                "Chọn số thứ tự dòng để chỉnh sửa (STT):",
                min_value=1,
                max_value=len(rows),
                value=1,
                step=1,
            ) - 1

            curr_row = rows[row_idx]
            if len(curr_row) >= 4:
                e_han = st.text_input("Hán (dùng [MASK] cho chữ mờ/khuyết):", value=curr_row[0], key="edit_han")
                e_da = st.text_input("Dịch âm:", value=curr_row[1], key="edit_da")
                e_dn = st.text_input("Dịch nghĩa:", value=curr_row[2], key="edit_dn")
                e_dt = st.text_input("Dịch thơ:", value=curr_row[3], key="edit_dt")
                updated_tuple = (e_han, e_da, e_dn, e_dt)
            else:
                e_han = st.text_input("Hán (dùng [MASK] cho chữ mờ/khuyết):", value=curr_row[0], key="edit_han")
                e_viet = st.text_input("Dịch tiếng Việt:", value=curr_row[1] if len(curr_row) > 1 else "", key="edit_viet")
                updated_tuple = (e_han, e_viet)

            b_col1, b_col2, b_col3 = st.columns(3)
            with b_col1:
                if st.button("💾 Cập nhật Dòng Này", use_container_width=True):
                    new_rows = edit_row(rows, row_idx, updated_tuple)
                    save_res = save_and_reexport_corpus(book_choice, new_rows, ROOT_DIR)
                    st.success(f"Đã cập nhật dòng {row_idx + 1} và tái xuất bản! (Lỗi: {save_res['error_rate']*100:.2f}%)")
                    st.rerun() if hasattr(st, "rerun") else None

            with b_col2:
                if row_idx < len(rows) - 1:
                    if st.button("🔗 Ghép với dòng kế tiếp", use_container_width=True):
                        new_rows = merge_rows(rows, row_idx, row_idx + 1)
                        save_res = save_and_reexport_corpus(book_choice, new_rows, ROOT_DIR)
                        st.success(f"Đã ghép dòng {row_idx + 1} và {row_idx + 2} thành công!")
                        st.rerun() if hasattr(st, "rerun") else None

            with b_col3:
                if len(rows) > 1:
                    if st.button("🗑️ Xóa dòng này", use_container_width=True):
                        new_rows = delete_row(rows, row_idx)
                        save_res = save_and_reexport_corpus(book_choice, new_rows, ROOT_DIR)
                        st.warning(f"Đã xóa dòng {row_idx + 1}!")
                        st.rerun() if hasattr(st, "rerun") else None

    # Page Scan Viewer
    st.divider()
    st.subheader("Đối soát Ảnh Quét Trang Sách Gốc (01_nguon)")
    img_dir = meta["img_dir"]
    if img_dir.is_dir():
        png_files = sorted(img_dir.glob("*.png"))
        if png_files:
            chosen_png = st.selectbox(
                "Chọn trang ảnh nguồn để xem đối chiếu:",
                options=png_files,
                format_func=lambda p: p.name,
            )
            if chosen_png and chosen_png.is_file():
                st.image(str(chosen_png), caption=f"Trang {chosen_png.stem} — CV04_{book_choice}: {meta['title']}", width=700)


def main() -> None:
    if "streamlit" in sys.modules or os.environ.get("STREAMLIT_SERVER_PORT"):
        run_streamlit_app()
    else:
        results = run_headless_check()
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

