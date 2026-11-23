"""Interactive Visual Alignment & QA Verification Web Application.

A lightweight, production-ready Streamlit app for exploring, searching,
and verifying bilingual Hán–Việt aligned parallel corpora for Group CV04.

Usage:
    streamlit run web_app/app.py
    python main.py web
"""

from __future__ import annotations

import html
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

    st.sidebar.header("Bộ lọc & Lựa chọn tư liệu")

    # Load all 4 members from config/member_splits.json and auto-detect active member
    splits_file = ROOT_DIR / "config" / "member_splits.json"
    members_map = {}
    if splits_file.is_file():
        try:
            splits_data = json.loads(splits_file.read_text(encoding="utf-8"))
            members_map = splits_data.get("members", {})
        except Exception:
            members_map = {}

    member_labels = {
        "kin": "Cái Hoàng Bảo Kin (kin — 393 trang)",
        "khanh": "Lê Gia Khánh (khanh — 396 trang)",
        "khoa": "Phạm Chấn Khoa (khoa — 397 trang)",
        "hieu": "Trần Trung Hiếu (hieu — 397 trang)",
    }
    member_options = [m for m in ("kin", "khanh", "khoa", "hieu") if m in members_map] or ["kin", "khanh"]

    def _count_member_ocr(m_key: str) -> int:
        m_books = members_map.get(m_key, {}).get("books", {})
        cnt = 0
        for b_code, b_meta in BOOK_METADATA.items():
            b_slice = m_books.get(b_code, {})
            ocr_han_dir = b_meta["folder"] / "02_ocr_tho" / "han"
            if not ocr_han_dir.is_dir():
                continue
            for p in b_slice.get("pdf_pages", []):
                if (ocr_han_dir / f"{int(p):04d}.json").is_file():
                    cnt += 1
        return cnt

    best_member = max(member_options, key=_count_member_ocr) if member_options else "kin"
    default_idx = member_options.index(best_member) if best_member in member_options else 0
    selected_member = st.sidebar.selectbox(
        "Theo dõi thành viên:",
        options=member_options,
        index=default_idx,
        format_func=lambda m: member_labels.get(m, m),
    )

    member_info = members_map.get(selected_member, {})
    member_display = member_info.get("display_name", selected_member)
    member_books = member_info.get("books", {})
    total_assigned = int(member_info.get("total_pages", 0)) or 393

    st.title("📜 CV04 — Hán–Việt Parallel Corpus Explorer & CAT Workbench")
    st.markdown(
        "Nền tảng trực quan hóa, theo dõi tiến độ OCR, đối soát và hiệu đính ngữ liệu song ngữ Hán – Việt "
        f"theo quy chuẩn **Lab 2. Dóng hàng Hán-Việt.pdf** & hướng dẫn của **chị Lưu Như** (Nhóm `CV04` — Thành viên: **{member_display}**)."
    )

    with st.expander(f"📊 Theo dõi Tiến độ Chạy {total_assigned} Trang Phân công Của {member_display} (Live Monitor)", expanded=True):
        pcol1, pcol2, pcol3, pcol4 = st.columns(4)
        total_ocr_done = 0
        total_pairs_all = 0
        per_book_stat = {}

        for b_idx, (b_code, b_meta) in enumerate(BOOK_METADATA.items()):
            b_slice = member_books.get(b_code, {})
            assigned_pages = set(int(p) for p in b_slice.get("pdf_pages", []))
            n_assigned = len(assigned_pages) if assigned_pages else 0

            png_dir = b_meta["img_dir"]
            ocr_han_dir = b_meta["folder"] / "02_ocr_tho" / "han"
            n_png = sum(1 for p in assigned_pages if (png_dir / f"{p:04d}.png").is_file()) if png_dir.is_dir() else 0
            n_ocr = 0
            if ocr_han_dir.is_dir():
                for p in assigned_pages:
                    jf = ocr_han_dir / f"{p:04d}.json"
                    if jf.is_file():
                        try:
                            jmeta = json.loads(jf.read_text(encoding="utf-8"))
                            if "mock" not in str(jmeta.get("engine", "")).lower():
                                n_ocr += 1
                        except Exception:
                            pass
            b_rows = load_book_rows(b_code)
            total_ocr_done += n_ocr
            total_pairs_all += len(b_rows)
            per_book_stat[b_code] = (n_assigned, n_png, n_ocr, len(b_rows))

        with pcol1:
            st.metric(
                f"Tổng tiến độ OCR ({member_display})",
                f"{total_ocr_done} / {total_assigned} trang",
                f"{(total_ocr_done / max(1, total_assigned)) * 100:.1f}%",
            )
            st.progress(min(1.0, total_ocr_done / max(1, total_assigned)))
        with pcol2:
            a1, png1, ocr1, r1 = per_book_stat["VPO_01"]
            st.metric(f"CV04_VPO_01 ({a1} trang)", f"OCR: {ocr1}/{a1} tr", f"Ảnh: {png1}/{a1} | {r1} cặp câu")
            st.progress(min(1.0, ocr1 / max(1, a1)))
        with pcol3:
            a2, png2, ocr2, r2 = per_book_stat["VPO_02"]
            st.metric(f"CV04_VPO_02 ({a2} trang)", f"OCR: {ocr2}/{a2} tr", f"Ảnh: {png2}/{a2} | {r2} cặp câu")
            st.progress(min(1.0, ocr2 / max(1, a2)))
        with pcol4:
            a3, png3, ocr3, r3 = per_book_stat["VPO_03"]
            st.metric(f"CV04_VPO_03 ({a3} trang)", f"OCR: {ocr3}/{a3} tr", f"Ảnh: {png3}/{a3} | {r3} cặp câu")
            st.progress(min(1.0, ocr3 / max(1, a3)))

        btn_c1, btn_c2 = st.columns(2)
        with btn_c1:
            if st.button("🔄 Làm mới Trạng thái Tiến độ", use_container_width=True):
                st.rerun() if hasattr(st, "rerun") else None
        with btn_c2:
            if st.button("⚡ Chạy Dóng hàng 4 Cột từ JSON OCR thật (02_ocr_tho/)", use_container_width=True):
                if total_ocr_done == 0:
                    st.warning(f"Chưa có file JSON OCR thật nào cho {total_assigned} trang của {member_display} (0/{total_assigned}). Hệ thống đang giữ nguyên bộ dữ liệu mẫu chuẩn để tránh ghi đè bằng dữ liệu giả lập (mock)!")
                else:
                    from src.corpus_pipeline import run_corpus_from_ocr
                    run_corpus_from_ocr(ROOT_DIR, ROOT_DIR)
                    st.success(f"Đã chạy xong Work Segmenter & Dóng hàng 4 cột từ {total_ocr_done} trang OCR thật!")
                    st.rerun() if hasattr(st, "rerun") else None

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

    # Render zero-pyarrow scrollable HTML table (avoids pyarrow vs NumPy 1.26 ABI error)
    if table_data:
        headers = list(table_data[0].keys())
        th_html = "".join(
            f"<th style='position:sticky;top:0;background:#1e293b;color:#f8fafc;padding:10px 12px;"
            f"border-bottom:2px solid #334155;text-align:left;font-weight:600;'>{html.escape(str(h))}</th>"
            for h in headers
        )
        trs = []
        for r_dict in table_data[:500]:
            tds = "".join(
                f"<td style='padding:8px 12px;border-bottom:1px solid #334155;vertical-align:top;'>"
                f"{html.escape(str(r_dict.get(h, '')))}</td>"
                for h in headers
            )
            trs.append(f"<tr>{tds}</tr>")
        table_html = (
            "<div style='max-height:460px;overflow-y:auto;border:1px solid #334155;border-radius:8px;'>"
            f"<table style='width:100%;border-collapse:collapse;font-size:14px;'>"
            f"<thead><tr>{th_html}</tr></thead>"
            f"<tbody>{''.join(trs)}</tbody>"
            "</table></div>"
        )
        st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.info("Chưa có dữ liệu dóng hàng cho bộ lọc này.")

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

