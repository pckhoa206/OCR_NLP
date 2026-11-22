"""CAT Workbench Editor Engine for Sino-Vietnamese Parallel Corpora.

Enables human-in-the-loop (HITL) computer-assisted post-editing operations:
- Edit row text (inline editing of Han, Phien Am, Dich Nghia, Dich Tho)
- Split row into two separate aligned rows at specified sentence/token boundaries
- Merge two adjacent rows into a single combined pair
- Insert or delete rows with atomic validation
- Save and re-export synchronously to TSV, OpenXML (.xlsx 2-sheet), and QA reports
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.exporter_and_qa import export_tsv, export_xlsx_zero_dep, read_tsv, validate_pairs
from src.text_cleaner import clean_han_text, clean_viet_text
from src.word_aligner import batch_evaluate_word_coverage

BOOK_FOLDER_MAP: Dict[str, str] = {
    "HVTT": "HVTT_HanVanTinhTuy",
    "TVLT2": "TVLT2_ThoVanLyTran2",
    "TLTVN": "TLTVN_TheLoaiTuVN",
}


def get_book_paths(book_key: str, workspace_root: Path) -> Dict[str, Path]:
    """Retrieve absolute file paths for a given book's deliverables."""
    code = book_key.upper().strip()
    folder_name = BOOK_FOLDER_MAP.get(code, code)
    align_dir = workspace_root / "deliverables" / folder_name / "04_dong_hang"
    align_dir.mkdir(parents=True, exist_ok=True)

    tsv_path = align_dir / f"{folder_name}_parallel.tsv"
    if not tsv_path.is_file():
        legacy_tsv = align_dir / f"{code}_parallel.tsv"
        if legacy_tsv.is_file():
            tsv_path = legacy_tsv

    xlsx_path = align_dir / f"{folder_name}_parallel.xlsx"
    if not xlsx_path.is_file():
        legacy_xlsx = align_dir / f"{code}_parallel.xlsx"
        if legacy_xlsx.is_file():
            xlsx_path = legacy_xlsx

    qa_report_path = align_dir / "qa_report.json"

    return {
        "folder_name": Path(folder_name),
        "align_dir": align_dir,
        "tsv": tsv_path,
        "xlsx": xlsx_path,
        "qa_report": qa_report_path,
    }


def load_corpus(book_key: str, workspace_root: Path) -> List[Tuple[str, ...]]:
    """Read the current parallel rows from TSV."""
    paths = get_book_paths(book_key, workspace_root)
    if not paths["tsv"].is_file():
        raise FileNotFoundError(f"TSV not found for {book_key} at {paths['tsv']}")
    return read_tsv(str(paths["tsv"]))


def edit_row(
    rows: List[Tuple[str, ...]],
    row_idx: int,
    new_cells: Tuple[str, ...],
) -> List[Tuple[str, ...]]:
    """Replace content of a specific row with validated and cleaned cells."""
    if not 0 <= row_idx < len(rows):
        raise IndexError(f"Row index {row_idx} out of range [0, {len(rows) - 1}]")

    cleaned_cells: List[str] = []
    for c_idx, cell in enumerate(new_cells):
        if c_idx == 0:
            cleaned_cells.append(clean_han_text(cell))
        else:
            cleaned_cells.append(clean_viet_text(cell))

    updated = list(rows)
    updated[row_idx] = tuple(cleaned_cells)
    return updated


def split_row(
    rows: List[Tuple[str, ...]],
    row_idx: int,
    han_split_pos: int,
    viet_split_pos: int = 0,
    dich_am_split_pos: Optional[int] = None,
    dich_nghia_split_pos: Optional[int] = None,
    dich_tho_split_pos: Optional[int] = None,
) -> List[Tuple[str, ...]]:
    """Split a row at specified string offsets into two consecutive rows.

    For 4-column rows `(Hán, Dịch âm, Dịch nghĩa, Dịch thơ)`, optional per-column
    offsets (`dich_am_split_pos`, `dich_nghia_split_pos`, `dich_tho_split_pos`) can
    be provided independently; if omitted, `dich_am` and `dich_nghia` fall back to
    `viet_split_pos` and `dich_tho` remains attached to the first row.
    """
    if not 0 <= row_idx < len(rows):
        raise IndexError(f"Row index {row_idx} out of range [0, {len(rows) - 1}]")

    target = rows[row_idx]
    han_full = target[0]

    part1_han = clean_han_text(han_full[:han_split_pos])
    part2_han = clean_han_text(han_full[han_split_pos:])

    new_rows: List[Tuple[str, ...]] = []
    if len(target) >= 4:
        # 4-column: Hán, Dịch âm, Dịch nghĩa, Dịch thơ
        dich_am = target[1]
        dich_nghia = target[2]
        dich_tho = target[3]

        da_pos = dich_am_split_pos if dich_am_split_pos is not None else viet_split_pos
        dn_pos = dich_nghia_split_pos if dich_nghia_split_pos is not None else viet_split_pos

        part1_da = clean_viet_text(dich_am[:da_pos]) if dich_am.strip() else ""
        part2_da = clean_viet_text(dich_am[da_pos:]) if dich_am.strip() else ""
        part1_dn = clean_viet_text(dich_nghia[:dn_pos]) if dich_nghia.strip() else ""
        part2_dn = clean_viet_text(dich_nghia[dn_pos:]) if dich_nghia.strip() else ""

        if dich_tho_split_pos is not None:
            part1_dt = clean_viet_text(dich_tho[:dich_tho_split_pos]) if dich_tho.strip() else ""
            part2_dt = clean_viet_text(dich_tho[dich_tho_split_pos:]) if dich_tho.strip() else ""
        else:
            part1_dt = clean_viet_text(dich_tho) if dich_tho.strip() else ""
            part2_dt = ""

        row1 = (part1_han, part1_da, part1_dn, part1_dt)
        row2 = (part2_han, part2_da, part2_dn, part2_dt)
        new_rows = [row1, row2]
    else:
        viet_full = target[1] if len(target) > 1 else ""
        part1_viet = clean_viet_text(viet_full[:viet_split_pos])
        part2_viet = clean_viet_text(viet_full[viet_split_pos:])
        new_rows = [(part1_han, part1_viet), (part2_han, part2_viet)]

    result = list(rows[:row_idx]) + new_rows + list(rows[row_idx + 1:])
    return result


def merge_rows(
    rows: List[Tuple[str, ...]],
    row_idx_1: int,
    row_idx_2: int,
) -> List[Tuple[str, ...]]:
    """Merge two rows into a single cohesive row without emitting stray commas on empty cells."""
    if not (0 <= row_idx_1 < len(rows) and 0 <= row_idx_2 < len(rows)):
        raise IndexError("Row index out of range")
    if abs(row_idx_1 - row_idx_2) != 1:
        raise ValueError("Can only merge adjacent rows")

    first_idx = min(row_idx_1, row_idx_2)
    second_idx = max(row_idx_1, row_idx_2)

    r1 = rows[first_idx]
    r2 = rows[second_idx]

    merged_cells: List[str] = []
    col_count = max(len(r1), len(r2))

    for c in range(col_count):
        val1 = (r1[c] if c < len(r1) else "").strip()
        val2 = (r2[c] if c < len(r2) else "").strip()
        if c == 0:
            if not val1 and not val2:
                merged_cells.append("")
            elif not val1:
                merged_cells.append(clean_han_text(val2))
            elif not val2:
                merged_cells.append(clean_han_text(val1))
            else:
                sep = "" if val1.endswith(("，", "、", "。", "？", "！", "；", "：")) else "，"
                merged_cells.append(clean_han_text(f"{val1}{sep}{val2}"))
        else:
            if not val1 and not val2:
                merged_cells.append("")
            elif not val1:
                merged_cells.append(clean_viet_text(val2))
            elif not val2:
                merged_cells.append(clean_viet_text(val1))
            else:
                sep = " " if val1.endswith((",", ";", ".", "?", "!", ":")) else ", "
                merged_cells.append(clean_viet_text(f"{val1}{sep}{val2}"))

    result = list(rows[:first_idx]) + [tuple(merged_cells)] + list(rows[second_idx + 1:])
    return result


def delete_row(
    rows: List[Tuple[str, ...]],
    row_idx: int,
) -> List[Tuple[str, ...]]:
    """Remove a row by its index."""
    if not 0 <= row_idx < len(rows):
        raise IndexError(f"Row index {row_idx} out of range")
    result = list(rows)
    result.pop(row_idx)
    return result


def insert_row(
    rows: List[Tuple[str, ...]],
    insert_at_idx: int,
    cells: Tuple[str, ...],
) -> List[Tuple[str, ...]]:
    """Insert a new pair at specified index."""
    if not 0 <= insert_at_idx <= len(rows):
        raise IndexError(f"Insert index {insert_at_idx} out of range [0, {len(rows)}]")
    cleaned = [clean_han_text(cells[0])] + [clean_viet_text(c) for c in cells[1:]]
    result = list(rows)
    result.insert(insert_at_idx, tuple(cleaned))
    return result


def save_and_reexport_corpus(
    book_key: str,
    rows: List[Tuple[str, ...]],
    workspace_root: Path,
) -> Dict[str, Any]:
    """Atomically validate, re-export TSV and XLSX, and update QA metrics."""
    paths = get_book_paths(book_key, workspace_root)
    folder_name = str(paths["folder_name"])

    # 1. QA Validation
    qa_report = validate_pairs(rows)
    word_coverage = batch_evaluate_word_coverage(rows)

    # 2. Re-export canonical TSV
    tsv_target = paths["align_dir"] / f"{folder_name}_parallel.tsv"
    export_tsv(rows, str(tsv_target))

    # Sync legacy short TSV only if a pre-existing non-symlink file exists
    short_tsv = paths["align_dir"] / f"{book_key}_parallel.tsv"
    if short_tsv != tsv_target and short_tsv.is_file() and not short_tsv.is_symlink():
        export_tsv(rows, str(short_tsv))

    # 3. Re-export canonical XLSX 2-sheet with explicit headers & stats
    is_four_col = any(len(r) >= 4 for r in rows) or (
        not rows and book_key.upper().strip() in BOOK_FOLDER_MAP
    )
    explicit_headers: Tuple[str, ...] = (
        ("Hán", "Dịch âm", "Dịch nghĩa", "Dịch thơ")
        if is_four_col
        else ("Hán", "Việt")
    )
    avg_han_cov = float(word_coverage.get("avg_han_coverage_pct", 0.0))
    avg_conf = float(word_coverage.get("avg_confidence", 0.0))
    stats_dict = {
        "Mã tài liệu": folder_name,
        "Tổng số cặp câu": len(rows),
        "Số cặp hợp lệ": qa_report["valid_checked_pairs"],
        "Tỷ lệ lỗi QA": f"{qa_report['error_rate'] * 100:.2f}%",
        "Độ bao phủ Hán tự": f"{avg_han_cov:.2f}%",
        "Điểm tin cậy liên kết": f"{avg_conf:.4f}",
    }

    xlsx_target = paths["align_dir"] / f"{folder_name}_parallel.xlsx"
    export_xlsx_zero_dep(
        rows,
        str(xlsx_target),
        stats=stats_dict,
        headers=explicit_headers,
    )
    short_xlsx = paths["align_dir"] / f"{book_key}_parallel.xlsx"
    if short_xlsx != xlsx_target and short_xlsx.is_file() and not short_xlsx.is_symlink():
        export_xlsx_zero_dep(
            rows,
            str(short_xlsx),
            stats=stats_dict,
            headers=explicit_headers,
        )

    # 4. Write updated QA report
    qa_full = {
        "book_code": book_key,
        "qa_validation": qa_report,
        "word_coverage": word_coverage,
    }
    paths["qa_report"].write_text(
        json.dumps(qa_full, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "status": "SUCCESS",
        "book_code": book_key,
        "total_rows": len(rows),
        "is_valid": qa_report["is_valid"],
        "error_rate": qa_report["error_rate"],
        "avg_confidence": avg_conf,
        "avg_han_coverage_pct": avg_han_cov,
        "tsv_path": str(tsv_target),
        "xlsx_path": str(xlsx_target),
    }
