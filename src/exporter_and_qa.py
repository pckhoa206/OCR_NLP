"""Quality assurance validator and zero-dependency TSV & OpenXML (.xlsx) exporter.

Implements Sections 2, 3, 6, 7, 8 of Guideline.pdf:
- `validate_pairs`: validates technical formatting and semantic/alignment quality criteria
  (`MISSING`, `OMISSION`, `ADDITION`, leftover markers, number consistency) and computes
  Section 8 acceptance metrics (`Tỷ lệ lỗi <= 30%`, internal target `<= 20%`).
- `export_tsv`: writes `<CÂU_HÁN>\\t<CÂU_VIỆT>` in UTF-8 without index or header rows.
- `export_xlsx_zero_dep`: writes a 100% standards-compliant OpenXML `.xlsx` archive
  using only Python's standard `zipfile` and `xml.etree.ElementTree`, with first sheet
  `DONG_HANG` (row 1 headers `Hán` and `Việt`, row i+1 identical to line i of `.tsv`)
  and optional second sheet `THONG_KE`.
- `read_xlsx_zero_dep`: reads `.xlsx` files using only `zipfile` and `xml.etree.ElementTree`
  to verify 100% content identity between `.tsv` and `.xlsx`.
"""

from __future__ import annotations

import os
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Any

from src.aligner import count_han_chars, count_viet_words

# Mandatory thresholds from Guideline.pdf Section 8 & task specification
OMISSION_RATIO_THRESHOLD: float = 0.7
ADDITION_RATIO_THRESHOLD: float = 4.5
ACCEPTANCE_ERROR_RATE_THRESHOLD: float = 0.30
INTERNAL_TARGET_ERROR_RATE: float = 0.20

_CJK_RE = re.compile(
    r"\[\s*MASK\s*\]|[\u3007\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002ebef\u25a0-\u25a3]",
    re.IGNORECASE,
)
_VIET_LETTER_RE = re.compile(r"[A-Za-zÀ-ỹà-ỹ]")
_VIET_TOKEN_RE = re.compile(r"[A-Za-zÀ-ỹà-ỹ0-9]+")

# Leftover footnote or section markers that must not appear in cleaned output
_LEFTOVER_MARKER_RE = re.compile(
    r"(?:\[\s*\d{1,3}\s*\]|\(\s*\d{1,2}\s*\)|(?<!\d)\d{1,3}\s*\*+|[¹²³⁴⁵⁶⁷⁸⁹⁰]+|"
    r"\b(?:PHIÊN\s*ÂM|DỊCH\s*NGHĨA|DỊCH\s*THƠ|DỊCH\s*THEO\s*NGUYÊN\s*ĐIỆU|NGUYÊN\s*VĂN)\b)",
    re.IGNORECASE,
)

# Cardinal number consistency checks (Hán char -> acceptable Vietnamese equivalents)
_NUMBER_CONSISTENCY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("三", ("ba", "tam", "3")),
    ("四", ("bốn", "tư", "tứ", "4")),
    ("五", ("năm", "lăm", "ngũ", "5")),
    ("六", ("sáu", "lục", "6")),
    ("七", ("bảy", "bẩy", "thất", "7")),
    ("八", ("tám", "bát", "8")),
    ("九", ("chín", "cửu", "9")),
    ("百", ("trăm", "bách", "bá", "100")),
    ("千", ("nghìn", "ngàn", "thiên", "1000", "1.000", "muôn", "vạn")),
    ("萬", ("vạn", "muôn", "ngàn", "nghìn", "10000", "10.000")),
]

# Illegal XML 1.0 control characters
_ILLEGAL_XML_CHARS_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f\ufdd0-\ufddf\ufffe\uffff]"
)

# OpenXML namespaces
_NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS_REL_DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_NS_REL_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
_NS_CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"


def check_number_consistency(han_text: str, viet_text: str) -> list[str]:
    """Check whether key Hán numbers have corresponding Vietnamese number words/digits.

    Returns a list of Hán number characters that appear in `han_text` without
    any corresponding Vietnamese equivalent in `viet_text`.
    """
    if not han_text or not viet_text:
        return []
    viet_lower = viet_text.lower()
    viet_tokens = set(_VIET_TOKEN_RE.findall(viet_lower))

    missing_nums: list[str] = []
    for han_num, equivalents in _NUMBER_CONSISTENCY_RULES:
        if han_num in han_text:
            found = any(
                (eq in viet_tokens if " " not in eq and "." not in eq else eq in viet_lower)
                for eq in equivalents
            )
            if not found:
                missing_nums.append(han_num)
    return missing_nums


def validate_pairs(pairs: list[tuple[str, ...]]) -> dict[str, Any]:
    """Validate aligned Hán-Việt pairs (2-column or 4-column) against Guideline.pdf.

    Supports:
    - 2-column pairs: `(han, viet)`
    - 4-column rows (`HVTT`): `(han, dich_am, dich_nghia, dich_tho)` where `dich_nghia`
      may be empty `""` for verse-only works (e.g., final poem *Thu dạ hoài ngâm* at
      PDF 367-381) as long as `dich_am` and `dich_tho` are populated.

    Checks:
    - `MISSING`: empty Hán or empty target translation, or missing CJK / Vietnamese letters.
    - `FORMAT_ERROR`: embedded `\\t`, `\\n`, `\\r`, or multiple consecutive spaces.
    - `LEFTOVER_MARKER`: uncleaned footnote markers (`[1]`, `1*`, `(1)`) or section
      headers (`PHIÊN ÂM`, `DỊCH NGHĨA`).
    - `OMISSION`: `viet_words / han_chars < 0.7`.
    - `ADDITION`: `viet_words / han_chars > 4.5`.
    - `NUMBER_MISMATCH`: Hán cardinal numbers (`三, 五, 百, 千, 萬`, etc.) missing in Việt.
    """
    total_pairs = len(pairs)
    issues: list[dict[str, Any]] = []
    error_row_indices: set[int] = set()
    warning_row_indices: set[int] = set()

    breakdown: dict[str, int] = {
        "MISSING": 0,
        "OMISSION": 0,
        "ADDITION": 0,
        "FORMAT_ERROR": 0,
        "LEFTOVER_MARKER": 0,
        "NUMBER_MISMATCH": 0,
    }

    for idx, pair in enumerate(pairs):
        if not isinstance(pair, (tuple, list)) or len(pair) < 2:
            breakdown["MISSING"] += 1
            error_row_indices.add(idx)
            issues.append(
                {
                    "row_index": idx,
                    "category": "MISSING",
                    "severity": "error",
                    "reason": "Row does not contain at least two elements.",
                    "han": "",
                    "viet": "",
                }
            )
            continue

        is_four_col = len(pair) >= 4
        han = "" if pair[0] is None else str(pair[0])
        if is_four_col:
            dich_am = "" if pair[1] is None else str(pair[1])
            dich_nghia = "" if pair[2] is None else str(pair[2])
            dich_tho = "" if pair[3] is None else str(pair[3])
            # Primary Vietnamese translation for semantic/ratio validation:
            # prefer dich_nghia when present, otherwise fallback to dich_tho
            viet = dich_nghia if dich_nghia.strip() else dich_tho
            all_cells = (han, dich_am, dich_nghia, dich_tho)
            has_missing_side = (
                not han.strip()
                or not dich_am.strip()
                or (not dich_nghia.strip() and not dich_tho.strip())
            )
        else:
            viet = "" if pair[1] is None else str(pair[1])
            all_cells = (han, viet)
            has_missing_side = not han.strip() or not viet.strip()

        # 1. MISSING check (empty side or missing script characters)
        if has_missing_side:
            breakdown["MISSING"] += 1
            error_row_indices.add(idx)
            issues.append(
                {
                    "row_index": idx,
                    "category": "MISSING",
                    "severity": "error",
                    "reason": "Empty Hán or Việt translation side.",
                    "han": han,
                    "viet": viet,
                }
            )
            continue

        if not _CJK_RE.search(han):
            breakdown["MISSING"] += 1
            error_row_indices.add(idx)
            issues.append(
                {
                    "row_index": idx,
                    "category": "MISSING",
                    "severity": "error",
                    "reason": "Hán side contains no CJK characters.",
                    "han": han,
                    "viet": viet,
                }
            )
            continue

        if not _VIET_LETTER_RE.search(viet):
            breakdown["MISSING"] += 1
            error_row_indices.add(idx)
            issues.append(
                {
                    "row_index": idx,
                    "category": "MISSING",
                    "severity": "error",
                    "reason": "Việt side contains no alphabetical/Vietnamese characters.",
                    "han": han,
                    "viet": viet,
                }
            )
            continue

        # 2. Technical format check: no \t, \n, \r, or multiple spaces in place of tab
        if any(
            any(ch in cell for ch in ("\t", "\n", "\r")) or "  " in cell
            for cell in all_cells
            if cell
        ):
            breakdown["FORMAT_ERROR"] += 1
            error_row_indices.add(idx)
            issues.append(
                {
                    "row_index": idx,
                    "category": "FORMAT_ERROR",
                    "severity": "error",
                    "reason": "Contains embedded tab, newline, or multiple consecutive spaces.",
                    "han": han,
                    "viet": viet,
                }
            )

        # 3. Leftover footnote markers / section labels check
        if any(_LEFTOVER_MARKER_RE.search(cell) for cell in all_cells if cell):
            breakdown["LEFTOVER_MARKER"] += 1
            breakdown["ADDITION"] += 1
            error_row_indices.add(idx)
            issues.append(
                {
                    "row_index": idx,
                    "category": "ADDITION",
                    "severity": "error",
                    "reason": "Contains uncleaned footnote marker ([1], 1*, (1)) or section header (PHIÊN ÂM, DỊCH NGHĨA).",
                    "han": han,
                    "viet": viet,
                }
            )

        # 4. Length ratio check (OMISSION < 0.7, ADDITION > 4.5)
        n_han = max(1, count_han_chars(han))
        n_viet = count_viet_words(viet)
        ratio = n_viet / n_han

        if ratio < OMISSION_RATIO_THRESHOLD:
            breakdown["OMISSION"] += 1
            error_row_indices.add(idx)
            issues.append(
                {
                    "row_index": idx,
                    "category": "OMISSION",
                    "severity": "warning",
                    "reason": f"Length ratio {ratio:.2f} < {OMISSION_RATIO_THRESHOLD} ({n_viet} Viet words / {n_han} Han chars).",
                    "han": han,
                    "viet": viet,
                }
            )
        elif ratio > ADDITION_RATIO_THRESHOLD:
            breakdown["ADDITION"] += 1
            error_row_indices.add(idx)
            issues.append(
                {
                    "row_index": idx,
                    "category": "ADDITION",
                    "severity": "warning",
                    "reason": f"Length ratio {ratio:.2f} > {ADDITION_RATIO_THRESHOLD} ({n_viet} Viet words / {n_han} Han chars).",
                    "han": han,
                    "viet": viet,
                }
            )

        # 5. Number consistency check (combined across available Vietnamese columns in 4-col mode)
        viet_for_num_check = (
            f"{dich_am} {dich_nghia} {dich_tho}" if is_four_col else viet
        )
        missing_nums = check_number_consistency(han, viet_for_num_check)
        if missing_nums:
            breakdown["NUMBER_MISMATCH"] += 1
            warning_row_indices.add(idx)
            error_row_indices.add(idx)
            issues.append(
                {
                    "row_index": idx,
                    "category": "NUMBER_MISMATCH",
                    "severity": "warning",
                    "reason": f"Hán number(s) {missing_nums} not reflected in Việt translation.",
                    "han": han,
                    "viet": viet,
                }
            )

    valid_checked_pairs = max(1, total_pairs) if total_pairs > 0 else 0
    num_error_pairs = len(error_row_indices)
    error_rate = (
        num_error_pairs / valid_checked_pairs if valid_checked_pairs > 0 else 0.0
    )
    passes_acceptance = error_rate <= ACCEPTANCE_ERROR_RATE_THRESHOLD
    passes_internal = error_rate <= INTERNAL_TARGET_ERROR_RATE

    return {
        "total_pairs": total_pairs,
        "valid_pairs": total_pairs - breakdown["MISSING"],
        "valid_checked_pairs": total_pairs,
        "error_pairs": num_error_pairs,
        "num_error_pairs": num_error_pairs,
        "clean_pairs": total_pairs - num_error_pairs,
        "error_rate": round(error_rate, 6),
        "passes_acceptance_threshold": passes_acceptance,
        "passes_threshold_30pct": passes_acceptance,
        "passes_internal_target": passes_internal,
        "passes_target_20pct": passes_internal,
        "is_valid": passes_acceptance
        and breakdown["MISSING"] == 0
        and breakdown["FORMAT_ERROR"] == 0,
        "error_counts_by_type": breakdown,
        "error_breakdown": breakdown,
        "missing_count": breakdown["MISSING"],
        "omission_count": breakdown["OMISSION"],
        "addition_count": breakdown["ADDITION"],
        "format_error_count": breakdown["FORMAT_ERROR"],
        "leftover_marker_count": breakdown["LEFTOVER_MARKER"],
        "number_mismatch_count": breakdown["NUMBER_MISMATCH"],
        "issues": issues,
        "errors": [iss for iss in issues if iss["severity"] == "error"],
        "warnings": [iss for iss in issues if iss["severity"] == "warning"],
    }


def _sanitize_cell_text(text: str) -> str:
    """Ensure a string has no tabs, newlines, or illegal XML characters."""
    if not text:
        return ""
    s = _ILLEGAL_XML_CHARS_RE.sub("", str(text))
    s = re.sub(r"[\r\n\t]+", " ", s)
    s = re.sub(r" {2,}", " ", s)
    return s.strip()


def export_tsv(pairs: list[tuple[str, ...]], tsv_path: str) -> None:
    """Write aligned rows to UTF-8 TSV file per Section 3 & instructor specification.

    Supports both:
    - 2-column rows: `<CÂU_HÁN>\\t<CÂU_VIỆT>`
    - 4-column rows (`HVTT`): `<HÁN>\\t<DỊCH_ÂM>\\t<DỊCH_NGHĨA>\\t<DỊCH_THƠ>`
      (where `<DỊCH_NGHĨA>` may be empty `""` for verse-only works).
    """
    parent = os.path.dirname(os.path.abspath(tsv_path))
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(tsv_path, "w", encoding="utf-8", newline="\n") as f:
        for row in pairs:
            cleaned_cells = [_sanitize_cell_text(c) for c in row]
            f.write("\t".join(cleaned_cells) + "\n")


def read_tsv(tsv_path: str) -> list[tuple[str, ...]]:
    """Read a UTF-8 TSV file into a list of 2-column or 4-column string tuples."""
    result: list[tuple[str, ...]] = []
    with open(tsv_path, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.rstrip("\r\n")
            if not raw:
                continue
            parts = raw.split("\t")
            if len(parts) >= 4:
                result.append((parts[0], parts[1], parts[2], parts[3]))
            elif len(parts) >= 2:
                result.append((parts[0], parts[1]))
            elif len(parts) == 1:
                result.append((parts[0], ""))
    return result


def _col_letter(col_idx_1based: int) -> str:
    """Convert 1-based column index to Excel column letters (1 -> 'A', 2 -> 'B')."""
    letters = []
    n = col_idx_1based
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters.append(chr(ord("A") + rem))
    return "".join(reversed(letters))


def _build_worksheet_xml(
    rows: list[tuple[str, ...]],
    shared_str_map: dict[str, int],
    shared_str_list: list[str],
) -> bytes:
    """Build an OpenXML `worksheet` XML byte string referencing shared strings."""
    worksheet = ET.Element(
        "worksheet",
        {
            "xmlns": _NS_MAIN,
            "xmlns:r": _NS_REL_DOC,
        },
    )
    last_row = max(1, len(rows))
    last_col = _col_letter(max((len(r) for r in rows), default=2))
    ET.SubElement(worksheet, "dimension", {"ref": f"A1:{last_col}{last_row}"})

    sheet_views = ET.SubElement(worksheet, "sheetViews")
    ET.SubElement(sheet_views, "sheetView", {"workbookViewId": "0"})
    ET.SubElement(worksheet, "sheetFormatPr", {"defaultRowHeight": "15"})

    sheet_data = ET.SubElement(worksheet, "sheetData")
    for r_idx, row_vals in enumerate(rows, start=1):
        row_el = ET.SubElement(sheet_data, "row", {"r": str(r_idx)})
        for c_idx, val in enumerate(row_vals, start=1):
            clean_val = _sanitize_cell_text(val)
            s_idx = shared_str_map.get(clean_val)
            if s_idx is None:
                s_idx = len(shared_str_list)
                shared_str_map[clean_val] = s_idx
                shared_str_list.append(clean_val)
            cell_ref = f"{_col_letter(c_idx)}{r_idx}"
            cell_el = ET.SubElement(
                row_el,
                "c",
                {"r": cell_ref, "t": "s"},
            )
            v_el = ET.SubElement(cell_el, "v")
            v_el.text = str(s_idx)

    return ET.tostring(worksheet, encoding="utf-8", xml_declaration=True)


def export_xlsx_zero_dep(
    pairs: list[tuple[str, ...]],
    xlsx_path: str,
    stats: dict[str, Any] | None = None,
    headers: tuple[str, ...] | None = None,
) -> None:
    """Write a 100% standards-compliant OpenXML `.xlsx` file with zero external dependencies.

    Strictly follows Guideline.pdf Section 3 and instructor specification:
    - First sheet is named `DONG_HANG`.
    - Row 1 contains headers:
      * `("Hán", "Việt")` for 2-column datasets (`TVLT2`, `TLTVN`), or
      * `("Hán", "Dịch âm", "Dịch nghĩa", "Dịch thơ")` for 4-column datasets (`HVTT`).
    - Row `i + 1` (for `i >= 1`) matches line `i` of the `.tsv` file 100% identically.
    - No merged cells, no blank rows, no formulas, and no index column.
    - Optional second sheet `THONG_KE` when `stats` is provided.
    """
    parent = os.path.dirname(os.path.abspath(xlsx_path))
    if parent:
        os.makedirs(parent, exist_ok=True)

    shared_str_map: dict[str, int] = {}
    shared_str_list: list[str] = []

    is_four_col = bool(pairs and len(pairs[0]) >= 4)
    if headers is None:
        headers = (
            ("Hán", "Dịch âm", "Dịch nghĩa", "Dịch thơ")
            if is_four_col
            else ("Hán", "Việt")
        )

    # Build rows for sheet1: DONG_HANG
    dong_hang_rows: list[tuple[str, ...]] = [headers]
    for row in pairs:
        dong_hang_rows.append(tuple(_sanitize_cell_text(c) for c in row))

    sheet1_bytes = _build_worksheet_xml(
        dong_hang_rows, shared_str_map, shared_str_list
    )

    # Optional sheet2: THONG_KE
    has_stats_sheet = stats is not None
    sheet2_bytes: bytes | None = None
    if has_stats_sheet and stats is not None:
        stat_rows: list[tuple[str, ...]] = [("Chỉ số", "Giá trị")]
        for k, v in stats.items():
            if isinstance(v, (int, float, str, bool)):
                stat_rows.append((str(k), str(v)))
        sheet2_bytes = _build_worksheet_xml(
            stat_rows, shared_str_map, shared_str_list
        )

    # Build xl/sharedStrings.xml
    sst = ET.Element(
        "sst",
        {
            "xmlns": _NS_MAIN,
            "count": str(
                len(dong_hang_rows) * len(headers)
                + (len(stats) * 2 if stats else 0)
            ),
            "uniqueCount": str(len(shared_str_list)),
        },
    )
    for text_val in shared_str_list:
        si = ET.SubElement(sst, "si")
        t_el = ET.SubElement(si, "t")
        if text_val != text_val.strip():
            t_el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        t_el.text = text_val
    shared_strings_bytes = ET.tostring(sst, encoding="utf-8", xml_declaration=True)

    # Build [Content_Types].xml
    types_el = ET.Element("Types", {"xmlns": _NS_CONTENT_TYPES})
    ET.SubElement(
        types_el,
        "Default",
        {
            "Extension": "rels",
            "ContentType": "application/vnd.openxmlformats-package.relationships+xml",
        },
    )
    ET.SubElement(
        types_el,
        "Default",
        {"Extension": "xml", "ContentType": "application/xml"},
    )
    ET.SubElement(
        types_el,
        "Override",
        {
            "PartName": "/xl/workbook.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
        },
    )
    ET.SubElement(
        types_el,
        "Override",
        {
            "PartName": "/xl/worksheets/sheet1.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
        },
    )
    if has_stats_sheet:
        ET.SubElement(
            types_el,
            "Override",
            {
                "PartName": "/xl/worksheets/sheet2.xml",
                "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
            },
        )
    ET.SubElement(
        types_el,
        "Override",
        {
            "PartName": "/xl/styles.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml",
        },
    )
    ET.SubElement(
        types_el,
        "Override",
        {
            "PartName": "/xl/sharedStrings.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml",
        },
    )
    content_types_bytes = ET.tostring(
        types_el, encoding="utf-8", xml_declaration=True
    )

    # Build _rels/.rels
    pkg_rels = ET.Element("Relationships", {"xmlns": _NS_REL_PKG})
    ET.SubElement(
        pkg_rels,
        "Relationship",
        {
            "Id": "rId1",
            "Type": f"{_NS_REL_DOC}/officeDocument",
            "Target": "xl/workbook.xml",
        },
    )
    pkg_rels_bytes = ET.tostring(pkg_rels, encoding="utf-8", xml_declaration=True)

    # Build xl/workbook.xml
    workbook_el = ET.Element(
        "workbook",
        {
            "xmlns": _NS_MAIN,
            "xmlns:r": _NS_REL_DOC,
        },
    )
    sheets_el = ET.SubElement(workbook_el, "sheets")
    ET.SubElement(
        sheets_el,
        "sheet",
        {"name": "DONG_HANG", "sheetId": "1", "r:id": "rId1"},
    )
    if has_stats_sheet:
        ET.SubElement(
            sheets_el,
            "sheet",
            {"name": "THONG_KE", "sheetId": "2", "r:id": "rId2"},
        )
    workbook_bytes = ET.tostring(workbook_el, encoding="utf-8", xml_declaration=True)

    # Build xl/_rels/workbook.xml.rels
    wb_rels = ET.Element("Relationships", {"xmlns": _NS_REL_PKG})
    ET.SubElement(
        wb_rels,
        "Relationship",
        {
            "Id": "rId1",
            "Type": f"{_NS_REL_DOC}/worksheet",
            "Target": "worksheets/sheet1.xml",
        },
    )
    next_rid = 2
    if has_stats_sheet:
        ET.SubElement(
            wb_rels,
            "Relationship",
            {
                "Id": f"rId{next_rid}",
                "Type": f"{_NS_REL_DOC}/worksheet",
                "Target": "worksheets/sheet2.xml",
            },
        )
        next_rid += 1
    ET.SubElement(
        wb_rels,
        "Relationship",
        {
            "Id": f"rId{next_rid}",
            "Type": f"{_NS_REL_DOC}/styles",
            "Target": "styles.xml",
        },
    )
    next_rid += 1
    ET.SubElement(
        wb_rels,
        "Relationship",
        {
            "Id": f"rId{next_rid}",
            "Type": f"{_NS_REL_DOC}/sharedStrings",
            "Target": "sharedStrings.xml",
        },
    )
    wb_rels_bytes = ET.tostring(wb_rels, encoding="utf-8", xml_declaration=True)

    # Build minimal valid xl/styles.xml
    styles_xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<styleSheet xmlns="{_NS_MAIN}">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
        "</styleSheet>"
    ).encode("utf-8")

    with zipfile.ZipFile(xlsx_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_bytes)
        zf.writestr("_rels/.rels", pkg_rels_bytes)
        zf.writestr("xl/workbook.xml", workbook_bytes)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels_bytes)
        zf.writestr("xl/styles.xml", styles_xml)
        zf.writestr("xl/sharedStrings.xml", shared_strings_bytes)
        zf.writestr("xl/worksheets/sheet1.xml", sheet1_bytes)
        if has_stats_sheet and sheet2_bytes is not None:
            zf.writestr("xl/worksheets/sheet2.xml", sheet2_bytes)


def _col_letters_to_index(cell_ref: str) -> int:
    """Extract column letters from cell ref (e.g. 'A1' -> 0, 'B12' -> 1)."""
    letters = "".join(ch for ch in cell_ref if ch.isalpha()).upper()
    if not letters:
        return 0
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def read_xlsx_zero_dep(
    xlsx_path: str,
    sheet_name: str = "DONG_HANG",
    include_header: bool = False,
) -> list[tuple[str, str]]:
    """Read back an `.xlsx` file using only `zipfile` and `xml.etree.ElementTree`.

    Supports both `sharedStrings.xml` (`t="s"`) and inline strings (`t="inlineStr"`).
    For `sheet_name == "DONG_HANG"`, verifies that row 1 has headers `("Hán", "Việt")`
    and returns the data rows `[(han, viet), ...]` so the output can be compared
    directly against `pairs` or `read_tsv(tsv_path)`.

    Args:
        xlsx_path: Path to the `.xlsx` file.
        sheet_name: Worksheet name to read (default `"DONG_HANG"`).
        include_header: If True, includes row 1 `("Hán", "Việt")` at index 0.

    Returns:
        List of `(col_A, col_B)` string tuples.
    """
    with zipfile.ZipFile(xlsx_path, "r") as zf:
        namelist = set(zf.namelist())

        # 1. Load sharedStrings.xml if present
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in namelist:
            sst_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sst_root.iter(f"{{{_NS_MAIN}}}si"):
                parts = [t.text or "" for t in si.iter(f"{{{_NS_MAIN}}}t")]
                shared_strings.append("".join(parts))

        # 2. Resolve sheet_name -> worksheet path via workbook.xml and workbook.xml.rels
        wb_root = ET.fromstring(zf.read("xl/workbook.xml"))
        target_rid: str | None = None
        for sheet_el in wb_root.iter(f"{{{_NS_MAIN}}}sheet"):
            if sheet_el.attrib.get("name") == sheet_name:
                target_rid = sheet_el.attrib.get(
                    f"{{{_NS_REL_DOC}}}id"
                ) or sheet_el.attrib.get("r:id")
                break

        if target_rid is None:
            raise ValueError(f"Worksheet {sheet_name!r} not found in {xlsx_path}")

        rels_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        sheet_target: str | None = None
        for rel_el in rels_root.iter(f"{{{_NS_REL_PKG}}}Relationship"):
            if rel_el.attrib.get("Id") == target_rid:
                sheet_target = rel_el.attrib.get("Target")
                break

        if not sheet_target:
            sheet_target = "worksheets/sheet1.xml"

        sheet_zip_path = (
            sheet_target.lstrip("/")
            if sheet_target.startswith("/xl/") or sheet_target.startswith("xl/")
            else f"xl/{sheet_target.lstrip('/')}"
        )

        # 3. Parse worksheet rows
        ws_root = ET.fromstring(zf.read(sheet_zip_path))
        raw_row_dicts: list[dict[int, str]] = []
        max_col_idx = 1

        for row_el in ws_root.iter(f"{{{_NS_MAIN}}}row"):
            row_cells: dict[int, str] = {}
            for col_pos, cell_el in enumerate(row_el.findall(f"{{{_NS_MAIN}}}c")):
                cell_ref = cell_el.attrib.get("r", "")
                c_idx = (
                    _col_letters_to_index(cell_ref) if cell_ref else col_pos
                )
                if c_idx > max_col_idx:
                    max_col_idx = c_idx
                cell_type = cell_el.attrib.get("t", "")
                val_str = ""
                if cell_type == "s":
                    v_el = cell_el.find(f"{{{_NS_MAIN}}}v")
                    if v_el is not None and v_el.text is not None:
                        s_idx = int(v_el.text)
                        if 0 <= s_idx < len(shared_strings):
                            val_str = shared_strings[s_idx]
                elif cell_type == "inlineStr":
                    parts = [
                        t.text or "" for t in cell_el.iter(f"{{{_NS_MAIN}}}t")
                    ]
                    val_str = "".join(parts)
                else:
                    v_el = cell_el.find(f"{{{_NS_MAIN}}}v")
                    if v_el is not None and v_el.text is not None:
                        val_str = v_el.text
                row_cells[c_idx] = val_str
            raw_row_dicts.append(row_cells)

    if not raw_row_dicts:
        return []

    num_cols = 4 if max_col_idx >= 3 else 2
    all_rows: list[tuple[str, ...]] = [
        tuple(r.get(c, "") for c in range(num_cols)) for r in raw_row_dicts
    ]

    if not include_header and all_rows[0] in (
        ("Hán", "Việt"),
        ("Hán", "Dịch âm", "Dịch nghĩa", "Dịch thơ"),
    ):
        return all_rows[1:]
    return all_rows
