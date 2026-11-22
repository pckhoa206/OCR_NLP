#!/usr/bin/env python3
"""Cross-Page Work Segmentation State Machine for TVLT2 and TLTVN.

Transforms page-level OCR outputs (`han_items`, `viet_items`) into cohesive
`WorkRecord` objects (and `SubPoem` splits for multi-poem suites / *Niêm tụng kệ*),
while keeping synthetic/unit-test inputs and full Kaggle GPU scans seamlessly supported.
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from kaggle_ocr.ocr_pipeline_kaggle import (
    _FOLDED_DICH_NGHIA_HEADER_RE,
    _FOLDED_DICH_THO_HEADER_RE,
    _FOLDED_PHIEN_AM_HEADER_RE,
    _box_bounds,
    _count_cjk_and_latin,
    _extract_header_remainder,
    _fold_ascii_header,
    _is_primary_han_line,
    _sort_items_reading_order,
    _word_count,
    classify_section_header,
    deduplicate_overlapping_items,
)


@dataclass
class SubPoem:
    """Single poem, stanza, or section (*tiết*) within a multi-part work."""

    sub_id: str = ""
    label: str = ""
    han_lines: List[str] = field(default_factory=list)
    pa_lines: List[str] = field(default_factory=list)
    dn_lines: List[str] = field(default_factory=list)
    dt_lines: List[str] = field(default_factory=list)
    source_pages: List[int] = field(default_factory=list)


@dataclass
class WorkRecord:
    """Cross-page work unit containing cleanly separated Hán / Phiên âm / Dịch nghĩa / Dịch thơ."""

    work_id: int
    book_type: str
    han_title: str = ""
    pa_title: str = ""
    dn_title: str = ""
    author: str = ""
    han_lines: List[str] = field(default_factory=list)
    pa_lines: List[str] = field(default_factory=list)
    dn_lines: List[str] = field(default_factory=list)
    dt_lines: List[str] = field(default_factory=list)
    sub_poems: List[SubPoem] = field(default_factory=list)
    source_pages: List[int] = field(default_factory=list)
    is_two_column: bool = False
    has_han: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Shared Normalization & Regex Patterns
# ---------------------------------------------------------------------------

_PURE_INT_RE = re.compile(r"^\d{1,3}$")
_AUTHOR_BIO_HEADER_RE = re.compile(
    r"^[A-Z\u00C0-\u024F\u1E00-\u1EFF][A-Z\u00C0-\u024F\u1E00-\u1EFF\s.\-]{3,}"
    r"\s*\((?:\d{3,4}|TH[EÊ]\s*K[IỈ])",
    flags=re.UNICODE,
)
_FOLDED_BIO_HEADER_RE = re.compile(
    r"^[A-Z][A-Z\s.\-]{4,}\s*\((?:\d{3,4}|THE\s*K[I1]|TR[UO]*C)",
)
_NON_ALPHA_TITLE_CHARS_RE = re.compile(r"[\d\s.,;:!?()\[\]\"'«»—\-/*]+")

# TVLT2-specific patterns
_TVLT2_RUNNING_HEADER_RE = re.compile(
    r"(?:TH[O0]\s*[NV]?[AX]N\s*L[YX].*TR[AX]N|TH[O0]\s*[NV]?[AX]N\s*TR[AX]N)",
    flags=re.IGNORECASE,
)
_TVLT2_SECTION_DIVIDER_RE = re.compile(
    r"^(?:陳.{0,6}|太宗|課虛錄|普說|論文語錄|六時懺悔科儀|.*時)$"
)
_TVLT2_TRANSLATOR_SIGNATURES = (
    "NGUYEN DONG CHI",
    "VNGVHS1",
    "DAO PHUONG BINH",
    "NGUYEN DUC VAN",
    "BANG THANH",
    "BANG TILANH",
    "BANG TUAN",
    "RANG THANH",
    "DO VAN HY",
    "DO VAN MY",
    "DO VAN H",
    "HUE CHI",
    "LE HUU NHIEM",
    "THIEU CHUU",
    "THIEU CHUC",
    "TIIEU CHUU",
    "TAP SAN DUOC TUE",
    "HOANG LE",
    "PHAM TU CHAU",
    "DINH GIA KHANH",
    "TRAN LE SANG",
)
_TVLT2_XUAT_XU_RE = re.compile(r"^\s*XU[AÂ]T\s*X[UƯ]\b", flags=re.IGNORECASE)
_TVLT2_KHA_HU_NUI_RE = re.compile(
    r"^\s*(?:NUI\s*THU\s+(?:NHAT|HAI|BA|TU)|GIAI\s*(?:RANG|VIET)|CO\s*KE\s*RANG)\b",
    flags=re.IGNORECASE,
)
_TVLT2_WORK21_HAN_CU_RE = re.compile(r"^[舉擧举]")
_TVLT2_WORK21_HAN_MARK_RE = re.compile(r"^(?:[舉擧举拈招粘花頌颂]|公[頌颂顷])")
_TVLT2_WORK21_PA_CU_RE = re.compile(r"^\s*C[UƯ]\s*[:.]?\s*(.*)$", flags=re.IGNORECASE)
_TVLT2_WORK21_DN_NEU_RE = re.compile(r"^\s*N[EÊ][UÂN]\s*[:.]?\s*(.*)$", flags=re.IGNORECASE)
_TVLT2_WORK21_CU_COLON_RE = re.compile(r"^\s*C[UỬ]\s*:\s*(.*)$", flags=re.IGNORECASE)
_TVLT2_WORK21_NEU_COLON_RE = re.compile(r"^\s*N[ÊE]U\s*:\s*(.*)$", flags=re.IGNORECASE)

# TLTVN-specific patterns
_TLTVN_NOISE_DIVIDER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_TLTVN_NUMBERED_FOOTNOTE_RE = re.compile(r"^\d{1,2}\s+[A-Z\u00C0-\u024F\u1E00-\u1EFF]")
_TLTVN_FOOTNOTE_CUE_RE = re.compile(
    r"^(?:XET\s+TU\s+PHO\b|THEO\s+|NAM\s+.*\(\d{4}\)|\d{1,2}\s+[A-Z])",
    flags=re.IGNORECASE,
)
_TLTVN_SUITE_MARKER_RE = re.compile(
    r"^\s*(?:([IVX]+\.|II|III|IV|VI|VII|VIII|IX|IIL|[1-9]\d*\.)(?:\s+(.*))?)\s*$"
)
_TLTVN_TUNE_TITLE_RE = re.compile(
    r"^\s*\(?\s*(?:DIEU\b|NGUYEN\s+LANG\s+QUY\b|VONG\s+GIANG\s+NAM\b|TRUONG\s+TUONG\s+TU\b|"
    r"TAY\s+GIANG\s+NGUYET\b|GIA\s+CO\s+THIEN\b|THAM\s+VIEN\s+XUAN\b|XUAN\s+QUANG\s+HAO\b|"
    r"CACH\s+PHO\s+LIEN\b|BO\s+BO\s+THIEM\b|NHAT\s+TIEN\s+MAI\b|PHONG\s+VU\s+HAN\b|"
    r"UC\s+TAN\s+NGA\b|HOA\s+DUONG\s+XUAN\b|HA\s+THANH\s+TRIEU\b|VU\s+TRUNG\s+HOA\b|"
    r"MAN\s+DINH\s+PHUONG\b|HA\s+HOANG\s+AN\b|THIEM\s+CUNG\s+KHUE\s+OAN\b|NAM\s+HUONG\s+TU\b|"
    r"YET\s+KIM\s+MON\b|QUE\s+CHI\s+HUONG\b|THANH\s+BINH\s+LAC\b|BO\s+TAT\s+MAN\b|NGU\s+GIA\s+NGAO\b)",
    flags=re.IGNORECASE,
)


def _nfc(text: Any) -> str:
    return unicodedata.normalize("NFC", str(text or "")).strip()


def _page_geometry(page: Dict[str, Any], all_items: Sequence[Dict[str, Any]]) -> Tuple[float, float, bool]:
    """Infer `(page_width, page_height, is_real_scan)` from page dict & items."""
    prep = page.get("preprocess") or {}
    if not prep and isinstance(page.get("layout"), dict):
        prep = page["layout"]
    pw = float(page.get("page_width") or prep.get("effective_width") or prep.get("original_width") or 0.0)
    ph = float(page.get("page_height") or prep.get("effective_height") or prep.get("original_height") or 0.0)
    max_x2 = 0.0
    max_y2 = 0.0
    for it in all_items:
        _x1, _y1, x2, y2 = _box_bounds(it)
        if x2 > max_x2:
            max_x2 = x2
        if y2 > max_y2:
            max_y2 = y2
    if pw <= 0.0:
        pw = max(1590.0, max_x2 + 100.0) if max_x2 > 900.0 else 2000.0
    if ph <= 0.0:
        ph = max(2056.0, max_y2 + 100.0) if max_y2 > 1100.0 else 2000.0
    is_real_scan = bool(
        float(prep.get("effective_height") or 0.0) > 1000.0
        or float(prep.get("original_height") or 0.0) > 1000.0
        or max_y2 > 1100.0
    )
    return pw, ph, is_real_scan


def _is_translator_signature(text: str, x1: float, page_width: float) -> bool:
    """Return True if a right-aligned uppercase item matches a TVLT2 translator attribution."""
    if x1 < 0.42 * page_width:
        return False
    folded = _fold_ascii_header(text).upper()
    cleaned = re.sub(r"[^A-Z0-9\s]", " ", folded)
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return False
    return any(sig in cleaned for sig in _TVLT2_TRANSLATOR_SIGNATURES)


def _is_all_caps_title(text: str) -> bool:
    """Return True if `text` is an ALL-CAPS Vietnamese title (not a section header)."""
    nfc = _nfc(text)
    if not nfc or _is_primary_han_line(nfc):
        return False
    if classify_section_header(nfc) is not None:
        return False
    folded = _fold_ascii_header(nfc)
    if _TVLT2_XUAT_XU_RE.match(folded) or _FOLDED_BIO_HEADER_RE.match(folded):
        return False
    if _TVLT2_KHA_HU_NUI_RE.match(folded):
        return False
    # Strip parenthetical footnote numbers like (1), (*) before checking case
    stripped = re.sub(r"\([^)]{0,6}\)", "", nfc)
    alpha_chars = [ch for ch in stripped if ch.isalpha()]
    if len(alpha_chars) < 3:
        return False
    # Allow minor OCR lowercase noise at most 1 char only if length >= 10
    lower_cnt = sum(1 for ch in alpha_chars if ch.islower())
    if lower_cnt > 0:
        return False
    words = [w for w in _NON_ALPHA_TITLE_CHARS_RE.split(stripped) if any(c.isalpha() for c in w)]
    return len(words) >= 2


def _is_bio_header(text: str) -> bool:
    nfc = _nfc(text)
    if not nfc:
        return False
    if _AUTHOR_BIO_HEADER_RE.match(nfc):
        return True
    folded = _fold_ascii_header(nfc).upper()
    return bool(_FOLDED_BIO_HEADER_RE.match(folded))


def _flush_work(
    works: List[WorkRecord],
    current: Optional[WorkRecord],
) -> None:
    """Finalize and append `current` to `works` if it contains any work content."""
    if current is None:
        return
    if not (
        current.han_lines
        or current.pa_lines
        or current.dn_lines
        or current.dt_lines
        or current.han_title
        or current.pa_title
        or current.dn_title
        or current.sub_poems
    ):
        return
    # Deduplicate source_pages preserving order
    seen_pages: List[int] = []
    for p in current.source_pages:
        if p not in seen_pages:
            seen_pages.append(p)
    current.source_pages = seen_pages
    works.append(current)


def _touch_page(work: WorkRecord, page_num: int) -> None:
    if page_num not in work.source_pages:
        work.source_pages.append(page_num)


def _load_work3_supplement_paragraphs(workspace_root: Optional[Path] = None) -> List[str]:
    """Load all 15 body paragraphs of TVLT2 Work #3 (`Thiền tông chỉ nam tự`) Dịch nghĩa."""
    candidates: List[Path] = []
    if workspace_root is not None:
        candidates.append(
            Path(workspace_root)
            / "deliverables/TVLT2_ThoVanLyTran2/01_nguon/bai_03_thien_tong_chi_nam_tu_dich_nghia.txt"
        )
    repo_root = Path(__file__).resolve().parent.parent
    candidates.append(
        repo_root / "deliverables/TVLT2_ThoVanLyTran2/01_nguon/bai_03_thien_tong_chi_nam_tu_dich_nghia.txt"
    )
    target = next((p for p in candidates if p.is_file()), None)
    if target is None:
        return []
    raw_lines = [
        unicodedata.normalize("NFC", ln.strip())
        for ln in target.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    paragraphs: List[str] = []
    idx = 0
    while idx < len(raw_lines):
        line = raw_lines[idx]
        # Merge standalone speaker label (`Sư bảo:`) with the quoted reply paragraph
        if line.endswith(":") and len(line) <= 20 and idx + 1 < len(raw_lines):
            paragraphs.append(f"{line} {raw_lines[idx + 1]}")
            idx += 2
        else:
            paragraphs.append(line)
            idx += 1
    return paragraphs


# ---------------------------------------------------------------------------
# TVLT2 Cross-Page State Machine
# ---------------------------------------------------------------------------


def _preprocess_tvlt2_page_items(
    page: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], float, float, bool]:
    han_raw = page.get("han_items") or []
    viet_raw = page.get("viet_items") or []
    pw, ph, is_real_scan = _page_geometry(page, list(han_raw) + list(viet_raw))

    def _keep(it: Dict[str, Any], is_han: bool) -> bool:
        txt = _nfc(it.get("text", ""))
        if not txt:
            return False
        x1, y1, _x2, y2 = _box_bounds(it)
        if not is_han and _is_translator_signature(txt, x1, pw):
            return False
        if is_real_scan:
            if y2 <= 40.0:
                return False
            folded = _fold_ascii_header(txt)
            if y1 < 42.0 and y2 <= 72.0:
                if _TVLT2_RUNNING_HEADER_RE.search(folded):
                    return False
                if x1 < 0.18 * pw and _PURE_INT_RE.match(folded):
                    return False
                if len(folded) <= 8 and x1 >= 0.80 * pw and not is_han:
                    return False
        else:
            folded = _fold_ascii_header(txt)
            if _TVLT2_RUNNING_HEADER_RE.search(folded) and y1 < 50.0:
                return False
        return True

    han_filtered = deduplicate_overlapping_items(
        _sort_items_reading_order([it for it in han_raw if _keep(it, True)])
    )
    viet_filtered = deduplicate_overlapping_items(
        _sort_items_reading_order([it for it in viet_raw if _keep(it, False)])
    )
    return han_filtered, viet_filtered, pw, ph, is_real_scan


def _is_tvlt2_work_number(
    item: Dict[str, Any],
    page_width: float,
    is_real_scan: bool,
) -> Optional[int]:
    txt = _nfc(item.get("text", ""))
    if not _PURE_INT_RE.match(txt):
        return None
    val = int(txt)
    if not (1 <= val <= 90):
        return None
    x1, y1, _x2, y2 = _box_bounds(item)
    if is_real_scan:
        # Real work numbers have tall font (h >= 32, y2 > 40) centered in [550..950] at 1590px width
        if y2 <= 40.0 or (y2 - y1) < 32.0:
            return None
        if not (0.34 * page_width <= x1 <= 0.62 * page_width):
            return None
    else:
        if x1 > 0 and y2 > 0 and not (0.25 * page_width <= 0.5 * (x1 + _box_bounds(item)[2]) <= 0.75 * page_width):
            return None
    return val


def _apply_work3_supplement(work: WorkRecord, paragraphs: Sequence[str]) -> None:
    """Attach the 15-paragraph Dịch nghĩa supplement for TVLT2 Work #3 (*Thiền tông chỉ nam tự*)."""
    is_work3 = (
        work.work_id == 3
        or "指南序" in work.han_title
        or "THIEN TONG CHI NAM" in _fold_ascii_header(work.pa_title).upper()
        or any("朕竊謂佛無南北" in ln for ln in work.han_lines)
    )
    if not is_work3:
        return
    work.dn_title = "TỰA THIỀN TÔNG CHỈ NAM"
    if paragraphs:
        work.dn_lines = list(paragraphs)
        work.metadata["dn_source"] = "bai_03_thien_tong_chi_nam_tu_dich_nghia.txt"


def _subsegment_work21(work: WorkRecord) -> None:
    """Split TVLT2 Work #21 (*Niêm tụng kệ*) locally into ~43 `SubPoem` tiết units."""
    is_work21 = (
        work.work_id == 21
        or "拈頌偈" in work.han_title
        or "NIEM TUNG KE" in _fold_ascii_header(work.pa_title).upper()
    )
    if not is_work21:
        return

    han_meta: List[Dict[str, Any]] = work.metadata.get("_han_meta", [])
    pa_meta: List[Dict[str, Any]] = work.metadata.get("_pa_meta", [])
    dn_meta: List[Dict[str, Any]] = work.metadata.get("_dn_meta", [])

    def _split_cues(entries: Sequence[Dict[str, Any]], cue_fn: Any) -> List[List[str]]:
        groups: List[List[str]] = []
        current: List[str] = []
        for entry in entries:
            txt = entry["text"]
            if cue_fn(txt, entry.get("x1", 0.0), entry.get("pw", 1590.0)):
                if current:
                    groups.append(current)
                current = [txt]
            else:
                if current or groups:
                    current.append(txt)
                else:
                    # Capture opening preface before the 1st cue as a leading bucket only if meaningful
                    current.append(txt)
        if current:
            groups.append(current)
        # Drop stray single-line title if already captured as han_title/pa_title
        if groups and len(groups) > 1 and not cue_fn(groups[0][0], 0.0, 1590.0):
            if len(groups[0]) == 1 and (
                groups[0][0] == work.han_title or groups[0][0] == work.pa_title
            ):
                groups = groups[1:]
        return groups

    han_groups = _split_cues(
        han_meta,
        lambda t, _x1, _pw: bool(_TVLT2_WORK21_HAN_CU_RE.match(re.sub(r"\s+", "", t))),
    )
    pa_groups = _split_cues(
        pa_meta,
        lambda t, x1, pw: bool(
            (x1 < 0.25 * pw and _TVLT2_WORK21_PA_CU_RE.match(_fold_ascii_header(t)) and _word_count(t) <= 2)
            or _TVLT2_WORK21_CU_COLON_RE.match(t)
        ),
    )
    dn_groups = _split_cues(
        dn_meta,
        lambda t, x1, pw: bool(
            (x1 < 0.25 * pw and _TVLT2_WORK21_DN_NEU_RE.match(_fold_ascii_header(t)) and _word_count(t) <= 2)
            or _TVLT2_WORK21_NEU_COLON_RE.match(t)
        ),
    )

    n_units = max(len(han_groups), len(pa_groups), len(dn_groups))
    if n_units < 2:
        return
    work.sub_poems = [
        SubPoem(
            sub_id=f"{work.work_id}_{idx + 1:02d}",
            label=f"Tiết {idx + 1}",
            han_lines=han_groups[idx] if idx < len(han_groups) else [],
            pa_lines=pa_groups[idx] if idx < len(pa_groups) else [],
            dn_lines=dn_groups[idx] if idx < len(dn_groups) else [],
        )
        for idx in range(n_units)
    ]


def _append_two_col_zone(
    work: WorkRecord,
    han_zone: Sequence[Dict[str, Any]],
    viet_zone: Sequence[Dict[str, Any]],
    page_num: int,
    page_width: float,
    is_real_scan: bool,
) -> None:
    """Append left-column Hán and right-column Phiên âm (merging wrapped words) to `work`."""
    work.is_two_column = True
    _touch_page(work, page_num)

    # Check if top line of this zone is a horizontally paired Hán + ALL-CAPS PA title
    han_list = list(han_zone)
    viet_list = list(viet_zone)
    if han_list and viet_list and not work.han_title:
        hx1, hy1, hx2, hy2 = _box_bounds(han_list[0])
        vx1, vy1, vx2, vy2 = _box_bounds(viet_list[0])
        h_yc = 0.5 * (hy1 + hy2)
        v_yc = 0.5 * (vy1 + vy2)
        h_txt = _nfc(han_list[0].get("text", ""))
        v_txt = _nfc(viet_list[0].get("text", ""))
        if abs(h_yc - v_yc) <= 45.0 and _is_all_caps_title(v_txt):
            work.han_title = h_txt
            work.pa_title = v_txt
            han_list = han_list[1:]
            viet_list = viet_list[1:]

    for h_it in han_list:
        h_txt = _nfc(h_it.get("text", ""))
        if not h_txt or _TVLT2_SECTION_DIVIDER_RE.match(re.sub(r"\s+", "", h_txt)):
            continue
        hx1, _, _, _ = _box_bounds(h_it)
        work.han_lines.append(h_txt)
        work.metadata.setdefault("_han_meta", []).append(
            {"text": h_txt, "x1": hx1, "pw": page_width, "page": page_num}
        )

    right_v_items = [
        it for it in viet_list
        if 0.5 * (_box_bounds(it)[0] + _box_bounds(it)[2]) >= 0.45 * page_width
        or _box_bounds(it)[0] >= 0.44 * page_width
    ]
    if not right_v_items and viet_list:
        right_v_items = viet_list

    col_left = (
        statistics.median(_box_bounds(it)[0] for it in right_v_items)
        if right_v_items
        else 0.48 * page_width
    )
    wrap_delta = 180.0 * (page_width / 1590.0) if is_real_scan else 180.0
    pa_lines_zone: List[Tuple[str, float]] = []
    for v_it in right_v_items:
        v_txt = _nfc(v_it.get("text", ""))
        if not v_txt:
            continue
        vx1, _, _, _ = _box_bounds(v_it)
        if pa_lines_zone and vx1 > col_left + wrap_delta and _word_count(v_txt) <= 3:
            prev_txt, prev_x1 = pa_lines_zone[-1]
            pa_lines_zone[-1] = (f"{prev_txt} {v_txt}", prev_x1)
        else:
            pa_lines_zone.append((v_txt, vx1))

    for pa_txt, vx1 in pa_lines_zone:
        if _is_all_caps_title(pa_txt) and not work.pa_lines:
            work.pa_title = f"{work.pa_title} {pa_txt}".strip() if work.pa_title else pa_txt
            continue
        work.pa_lines.append(pa_txt)
        work.metadata.setdefault("_pa_meta", []).append(
            {"text": pa_txt, "x1": vx1, "pw": page_width, "page": page_num}
        )


def _segment_tvlt2(
    pages: Sequence[Dict[str, Any]],
    workspace_root: Optional[Path] = None,
) -> List[WorkRecord]:
    works: List[WorkRecord] = []
    current_work: Optional[WorkRecord] = None
    state = "BIO_OR_SKIP"  # BIO_OR_SKIP | HAN_BODY | PA | DICH_NGHIA | DICH_THO | SKIP_APPARATUS
    auto_work_id = 0
    pending_work_id: Optional[int] = None
    work3_paragraphs = _load_work3_supplement_paragraphs(workspace_root)

    def _start_work(explicit_id: Optional[int], pnum: int, han_title: str = "", pa_title: str = "") -> None:
        nonlocal current_work, state, auto_work_id
        _flush_work(works, current_work)
        if explicit_id is not None:
            wid = explicit_id
            auto_work_id = max(auto_work_id, explicit_id)
        else:
            auto_work_id += 1
            wid = auto_work_id
        current_work = WorkRecord(
            work_id=wid,
            book_type="TVLT2",
            han_title=han_title,
            pa_title=pa_title,
            source_pages=[pnum],
        )
        state = "HAN_BODY"

    for page in pages:
        pnum = int(page.get("page_num", 0))
        han_items, viet_items, pw, ph, is_real_scan = _preprocess_tvlt2_page_items(page)

        # If Work #N number was clipped at bottom of previous page (e.g., #58 on p0214 -> p0215)
        if pending_work_id is not None and any(_is_primary_han_line(it.get("text", "")) for it in han_items):
            _start_work(pending_work_id, pnum)
            pending_work_id = None

        # Merge remaining Han and Viet items in top-to-bottom reading order
        tagged: List[Tuple[str, float, float, float, float, Dict[str, Any]]] = []
        for it in han_items:
            txt = _nfc(it.get("text", ""))
            if not _is_primary_han_line(txt):
                continue
            x1, y1, x2, y2 = _box_bounds(it)
            tagged.append(("han", 0.5 * (y1 + y2), x1, y1, y2, it))
        for it in viet_items:
            x1, y1, x2, y2 = _box_bounds(it)
            tagged.append(("viet", 0.5 * (y1 + y2), x1, y1, y2, it))
        tagged.sort(key=lambda t: (round(t[1] / 16.0), t[2]))

        # Partition page items at clear work-transition / section-header boundaries
        idx = 0
        n = len(tagged)
        # Active y-band buffer for detecting 2-column Han + PA zones inside HAN_BODY
        zone_han: List[Dict[str, Any]] = []
        zone_viet: List[Dict[str, Any]] = []

        def _flush_zone() -> None:
            nonlocal zone_han, zone_viet
            if current_work is None or (not zone_han and not zone_viet):
                zone_han = []
                zone_viet = []
                return
            _touch_page(current_work, pnum)
            mid_x = 0.52 * pw
            left_han = all(
                0.5 * (_box_bounds(h)[0] + _box_bounds(h)[2]) < mid_x for h in zone_han
            ) if zone_han else False
            has_right_pa = any(
                0.5 * (_box_bounds(v)[0] + _box_bounds(v)[2]) >= 0.48 * pw
                and not _is_all_caps_title(_nfc(v.get("text", "")))
                for v in zone_viet
            )
            has_paired_title = (
                len(zone_han) >= 1
                and len(zone_viet) >= 1
                and any(_is_all_caps_title(_nfc(v.get("text", ""))) and _box_bounds(v)[0] >= 0.42 * pw for v in zone_viet)
            )
            if zone_han and (left_han and (has_right_pa or has_paired_title)):
                _append_two_col_zone(current_work, zone_han, zone_viet, pnum, pw, is_real_scan)
            else:
                # Sequential prose Han (and stray Han title before prose)
                for h_it in zone_han:
                    h_txt = _nfc(h_it.get("text", ""))
                    if _TVLT2_SECTION_DIVIDER_RE.match(re.sub(r"\s+", "", h_txt)):
                        continue
                    hx1, hy1, hx2, hy2 = _box_bounds(h_it)
                    if not current_work.han_title and not current_work.han_lines and len(zone_han) > 1:
                        # Centered short title above full-width Han prose
                        if (hx2 - hx1) < 0.45 * pw or (hy2 - hy1) >= 58.0:
                            current_work.han_title = h_txt
                            continue
                    current_work.han_lines.append(h_txt)
                    current_work.metadata.setdefault("_han_meta", []).append(
                        {"text": h_txt, "x1": hx1, "pw": pw, "page": pnum}
                    )
                for v_it in zone_viet:
                    v_txt = _nfc(v_it.get("text", ""))
                    vx1, _, _, _ = _box_bounds(v_it)
                    if not current_work.pa_title and _is_all_caps_title(v_txt):
                        current_work.pa_title = v_txt
                        continue
                    current_work.pa_lines.append(v_txt)
                    current_work.metadata.setdefault("_pa_meta", []).append(
                        {"text": v_txt, "x1": vx1, "pw": pw, "page": pnum}
                    )
            zone_han = []
            zone_viet = []

        while idx < n:
            kind, yc, x1, y1, y2, item = tagged[idx]
            txt = _nfc(item.get("text", ""))
            x2 = _box_bounds(item)[2]

            if kind == "viet":
                # 1. Check author bio transition -> flush & enter BIO_OR_SKIP
                if _is_bio_header(txt):
                    _flush_zone()
                    _flush_work(works, current_work)
                    current_work = None
                    state = "BIO_OR_SKIP"
                    idx += 1
                    continue

                # 2. Check standalone work number transition
                wnum = _is_tvlt2_work_number(item, pw, is_real_scan)
                if wnum is not None:
                    has_han_soon = any(
                        tagged[j][0] == "han" and (tagged[j][3] - y2) <= 260.0
                        for j in range(idx + 1, n)
                    )
                    at_page_tail = (
                        is_real_scan
                        and y1 >= 0.60 * ph
                        and all(tagged[j][0] != "viet" for j in range(idx + 1, n))
                    )
                    if has_han_soon:
                        _flush_zone()
                        _start_work(wnum, pnum)
                        idx += 1
                        continue
                    if at_page_tail:
                        _flush_zone()
                        _flush_work(works, current_work)
                        current_work = None
                        pending_work_id = wnum
                        state = "BIO_OR_SKIP"
                        idx += 1
                        continue

                # 3. Check section header transitions
                folded = _fold_ascii_header(txt)
                if _TVLT2_XUAT_XU_RE.match(folded):
                    _flush_zone()
                    state = "SKIP_APPARATUS"
                    idx += 1
                    continue

                hdr = classify_section_header(txt)
                if hdr == "stop":
                    _flush_zone()
                    state = "SKIP_APPARATUS"
                    idx += 1
                    continue

                if hdr == "phien_am":
                    _flush_zone()
                    if current_work is None:
                        _start_work(None, pnum)
                    _touch_page(current_work, pnum)
                    state = "PA"
                    _, rest = _extract_header_remainder(txt, _FOLDED_PHIEN_AM_HEADER_RE)
                    if rest:
                        if not current_work.pa_title and _is_all_caps_title(rest):
                            current_work.pa_title = rest
                        else:
                            current_work.pa_lines.append(rest)
                            current_work.metadata.setdefault("_pa_meta", []).append(
                                {"text": rest, "x1": x1, "pw": pw, "page": pnum}
                            )
                    idx += 1
                    continue

                if hdr == "dich_nghia":
                    _flush_zone()
                    if current_work is None:
                        _start_work(None, pnum)
                    _touch_page(current_work, pnum)
                    state = "DICH_NGHIA"
                    _, rest = _extract_header_remainder(txt, _FOLDED_DICH_NGHIA_HEADER_RE)
                    if rest:
                        if not current_work.dn_title and _is_all_caps_title(rest):
                            current_work.dn_title = rest
                        else:
                            current_work.dn_lines.append(rest)
                            current_work.metadata.setdefault("_dn_meta", []).append(
                                {"text": rest, "x1": x1, "pw": pw, "page": pnum}
                            )
                    idx += 1
                    continue

                if hdr == "dich_tho":
                    _flush_zone()
                    if current_work is None:
                        _start_work(None, pnum)
                    _touch_page(current_work, pnum)
                    state = "DICH_THO"
                    _, rest = _extract_header_remainder(txt, _FOLDED_DICH_THO_HEADER_RE)
                    if rest:
                        current_work.dt_lines.append(rest)
                    idx += 1
                    continue

                # Work #5 Khóa hư lục mixed prose + Kệ transition: DICH_THO -> DICH_NGHIA
                if state == "DICH_THO" and _TVLT2_KHA_HU_NUI_RE.match(folded):
                    _touch_page(current_work, pnum)
                    state = "DICH_NGHIA"
                    if current_work is not None:
                        current_work.dn_lines.append(txt)
                        current_work.metadata.setdefault("_dn_meta", []).append(
                            {"text": txt, "x1": x1, "pw": pw, "page": pnum}
                        )
                    idx += 1
                    continue

                if state in ("BIO_OR_SKIP", "SKIP_APPARATUS") or current_work is None:
                    idx += 1
                    continue

                _touch_page(current_work, pnum)
                if state == "HAN_BODY":
                    zone_viet.append(item)
                elif state == "PA":
                    if not current_work.pa_title and not current_work.pa_lines and _is_all_caps_title(txt):
                        current_work.pa_title = txt
                    else:
                        current_work.pa_lines.append(txt)
                        current_work.metadata.setdefault("_pa_meta", []).append(
                            {"text": txt, "x1": x1, "pw": pw, "page": pnum}
                        )
                elif state == "DICH_NGHIA":
                    if (
                        not current_work.dn_title
                        and not current_work.dn_lines
                        and _is_all_caps_title(txt)
                    ):
                        current_work.dn_title = txt
                    else:
                        current_work.dn_lines.append(txt)
                        current_work.metadata.setdefault("_dn_meta", []).append(
                            {"text": txt, "x1": x1, "pw": pw, "page": pnum}
                        )
                elif state == "DICH_THO":
                    current_work.dt_lines.append(txt)

                idx += 1
                continue

            # kind == "han"
            compact_han = re.sub(r"\s+", "", txt)
            if _TVLT2_SECTION_DIVIDER_RE.match(compact_han):
                idx += 1
                continue

            if state != "HAN_BODY":
                # Check fallback start of a missing-number work out of BIO_OR_SKIP/SKIP_APPARATUS/DICH_*
                can_fallback_start = state in ("BIO_OR_SKIP", "SKIP_APPARATUS", "DICH_NGHIA", "DICH_THO") or current_work is None
                if can_fallback_start:
                    # Fallback A: Paired 2-column Hán + ALL-CAPS Viet title on same line band
                    paired_all_caps = any(
                        tagged[j][0] == "viet"
                        and abs(tagged[j][1] - yc) <= 45.0
                        and tagged[j][2] >= 0.42 * pw
                        and _is_all_caps_title(tagged[j][5].get("text", ""))
                        for j in range(max(0, idx - 2), min(n, idx + 4))
                    )
                    # Fallback B: Centered tall Hán title (h >= 58, concise width <= 0.55*pw)
                    # followed by full-width Hán prose or PHIÊN ÂM (guards against p0028 quoted prose)
                    h_box_h = y2 - y1
                    h_box_w = x2 - x1
                    h_xc = 0.5 * (x1 + x2)
                    is_centered_tall = (
                        is_real_scan
                        and h_box_h >= 58.0
                        and h_box_w <= 0.55 * pw
                        and 0.22 * pw <= h_xc <= 0.78 * pw
                        and any(
                            (
                                (tagged[j][0] == "han" and _box_bounds(tagged[j][5])[2] >= 0.65 * pw)
                                or (
                                    tagged[j][0] == "viet"
                                    and classify_section_header(tagged[j][5].get("text", "")) == "phien_am"
                                )
                            )
                            and (tagged[j][3] - y2) <= 350.0
                            for j in range(idx + 1, n)
                        )
                    )
                    # Fallback C: Synthetic non-real-scan page starting cleanly with primary Han
                    is_synthetic_start = (
                        not is_real_scan
                        and current_work is None
                        and not any(_is_bio_header(t[5].get("text", "")) for t in tagged[:idx])
                    )
                    if paired_all_caps or is_centered_tall or is_synthetic_start:
                        _flush_zone()
                        _start_work(None, pnum)
                        if paired_all_caps or is_synthetic_start:
                            zone_han.append(item)
                        else:
                            current_work.han_title = txt
                        idx += 1
                        continue

                # Otherwise ignore inline/quoted Hán inside BIO_OR_SKIP or CHÚ THÍCH apparatus
                idx += 1
                continue

            # Inside HAN_BODY: check if an inline paired work start shouldn't split ongoing work unless queued
            zone_han.append(item)
            idx += 1

        _flush_zone()

    _flush_work(works, current_work)

    for work in works:
        _apply_work3_supplement(work, work3_paragraphs)
        _subsegment_work21(work)

    return works


# ---------------------------------------------------------------------------
# TLTVN Cross-Page State Machine
# ---------------------------------------------------------------------------


def _parse_tltvn_suite_marker(text: str) -> Tuple[Optional[str], str]:
    """Match Roman/numbered sub-poem cues (`I.`, `II.`, `IIL`, `1.`, `IV.`) returning `(marker, rest)`."""
    nfc = _nfc(text)
    if not nfc:
        return (None, "")
    # Bare lone 'I' without period is noisy OCR artifact (e.g. p0140) unless accompanied by text
    m = _TLTVN_SUITE_MARKER_RE.match(nfc)
    if not m:
        return (None, "")
    marker = m.group(1)
    rest = (m.group(2) or "").strip()
    return (marker, rest)


def _preprocess_tltvn_page_items(
    page: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], float, float, bool]:
    han_raw = deduplicate_overlapping_items(_sort_items_reading_order(page.get("han_items") or []))
    viet_raw = deduplicate_overlapping_items(_sort_items_reading_order(page.get("viet_items") or []))
    pw, ph, is_real_scan = _page_geometry(page, list(han_raw) + list(viet_raw))

    viet_clean: List[Dict[str, Any]] = []
    for i, it in enumerate(viet_raw):
        txt = _nfc(it.get("text", ""))
        if not txt or _TLTVN_NOISE_DIVIDER_RE.match(txt):
            continue
        x1, y1, x2, y2 = _box_bounds(it)
        if is_real_scan:
            # Drop bottom page numbers only
            if y1 >= 1350.0 and _PURE_INT_RE.match(txt):
                continue
            # Preserve y=0..4 short/cropped headers (p0173, 0199, 0210, 0216, 0227, 0229, 0233)
            # while filtering clipped full-width prose wrap (p0237)
            if y1 <= 4.0:
                next_starts_lower = False
                if i + 1 < len(viet_raw):
                    nxt = _nfc(viet_raw[i + 1].get("text", ""))
                    if nxt and nxt[0].islower():
                        next_starts_lower = True
                if len(txt) >= 65 or (
                    (y2 - y1) <= 22.0 and (x2 - x1) >= 0.75 * pw and next_starts_lower
                ):
                    continue
        viet_clean.append(it)

    # Detect fn_sep=None footnote cutoff on Viet items (e.g., p0139)
    cutoff_y: Optional[float] = None
    prev_y2: Optional[float] = None
    for it in viet_clean:
        txt = _nfc(it.get("text", ""))
        x1, y1, x2, y2 = _box_bounds(it)
        if is_real_scan and prev_y2 is not None and (y1 - prev_y2) >= 55.0:
            folded = _fold_ascii_header(txt)
            is_fn_geom = x1 <= 105.0 and x2 >= 960.0 and (y2 - y1) <= 38.0 and len(txt) >= 24
            is_fn_cue = bool(
                _TLTVN_NUMBERED_FOOTNOTE_RE.match(txt) or _TLTVN_FOOTNOTE_CUE_RE.match(folded)
            )
            if (is_fn_geom or is_fn_cue) and classify_section_header(txt) is None and not _is_bio_header(txt):
                cutoff_y = y1
                break
        prev_y2 = y2

    if cutoff_y is not None:
        viet_clean = [it for it in viet_clean if _box_bounds(it)[1] < cutoff_y]
        han_clean = [it for it in han_raw if _box_bounds(it)[1] < cutoff_y]
    else:
        han_clean = list(han_raw)

    return han_clean, viet_clean, pw, ph, is_real_scan


def _segment_tltvn(pages: Sequence[Dict[str, Any]]) -> List[WorkRecord]:
    works: List[WorkRecord] = []
    current_work: Optional[WorkRecord] = None
    state = "BIO_OR_SKIP"  # BIO_OR_SKIP | HAN_BODY | PA | DICH_NGHIA | DICH_THO | SKIP_APPARATUS
    auto_work_id = 0

    # Track suite sub-poems cleanly on active work
    sub_buckets: Dict[str, List[Tuple[str, str]]] = {}

    def _finalize_sub_poems(work: Optional[WorkRecord]) -> None:
        if work is None:
            return
        markers: List[str] = []
        for sec_key in ("han", "pa", "dn", "dt"):
            for lbl, _line in sub_buckets.get(sec_key, []):
                if lbl and lbl not in markers:
                    markers.append(lbl)
        if len(markers) < 2:
            return
        roman_order = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
        orig_pos = {lbl: idx for idx, lbl in enumerate(markers)}
        markers.sort(key=lambda lbl: (roman_order.get(lbl, 999), orig_pos[lbl]))
        grouped: Dict[str, SubPoem] = {
            lbl: SubPoem(sub_id=f"{work.work_id}_{idx + 1:02d}", label=lbl)
            for idx, lbl in enumerate(markers)
        }
        for lbl, ln in sub_buckets.get("han", []):
            if lbl in grouped:
                grouped[lbl].han_lines.append(ln)
        for lbl, ln in sub_buckets.get("pa", []):
            if lbl in grouped:
                grouped[lbl].pa_lines.append(ln)
        for lbl, ln in sub_buckets.get("dn", []):
            if lbl in grouped:
                grouped[lbl].dn_lines.append(ln)
        for lbl, ln in sub_buckets.get("dt", []):
            if lbl in grouped:
                grouped[lbl].dt_lines.append(ln)
        work.sub_poems = [grouped[lbl] for lbl in markers]

    def _start_tltvn_work(pnum: int) -> None:
        nonlocal current_work, state, auto_work_id, sub_buckets
        _finalize_sub_poems(current_work)
        _flush_work(works, current_work)
        auto_work_id += 1
        current_work = WorkRecord(
            work_id=auto_work_id,
            book_type="TLTVN",
            source_pages=[pnum],
        )
        sub_buckets = {"han": [], "pa": [], "dn": [], "dt": []}
        state = "HAN_BODY"

    active_sub_label: Dict[str, str] = {"PA": "", "DICH_NGHIA": "", "DICH_THO": "", "HAN_BODY": ""}

    def _canon_marker(raw: str) -> str:
        norm = raw.strip().rstrip(".")
        if norm.upper() == "IIL":
            return "III"
        # Map 1 -> I, 2 -> II for consistent cross-section pairing when OCR digits replace Romans
        roman_map = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V", "6": "VI"}
        return roman_map.get(norm, norm.upper())

    for page in pages:
        pnum = int(page.get("page_num", 0))
        han_items, viet_items, _pw, _ph, _is_real_scan = _preprocess_tltvn_page_items(page)

        tagged: List[Tuple[str, float, float, Dict[str, Any]]] = []
        for it in han_items:
            txt = _nfc(it.get("text", ""))
            if not _is_primary_han_line(txt):
                continue
            x1, y1, _x2, y2 = _box_bounds(it)
            tagged.append(("han", 0.5 * (y1 + y2), x1, it))
        for it in viet_items:
            x1, y1, _x2, y2 = _box_bounds(it)
            tagged.append(("viet", 0.5 * (y1 + y2), x1, it))
        tagged.sort(key=lambda t: (round(t[1] / 16.0), t[2]))

        for idx, (kind, _yc, _x1, item) in enumerate(tagged):
            txt = _nfc(item.get("text", ""))
            _x1_b, y1, _x2_b, _y2_b = _box_bounds(item)

            if kind == "han":
                if current_work is None or state in ("PA", "DICH_NGHIA", "DICH_THO", "BIO_OR_SKIP", "SKIP_APPARATUS"):
                    # Start new work on primary Han block if prior sections had content or in BIO/SKIP
                    has_non_han_body = current_work is not None and (
                        bool(current_work.pa_lines)
                        or bool(current_work.dn_lines)
                        or bool(current_work.dt_lines)
                        or state in ("BIO_OR_SKIP", "SKIP_APPARATUS")
                    )
                    if current_work is None or has_non_han_body:
                        _start_tltvn_work(pnum)
                        active_sub_label = {"PA": "", "DICH_NGHIA": "", "DICH_THO": "", "HAN_BODY": ""}
                _touch_page(current_work, pnum)
                if not current_work.han_lines and txt.startswith("(") and txt.endswith(")") and len(txt) <= 10:
                    current_work.han_title = txt
                else:
                    current_work.han_lines.append(txt)
                    sub_buckets["han"].append((active_sub_label["HAN_BODY"], txt))
                continue

            # kind == "viet"
            if _is_bio_header(txt):
                _finalize_sub_poems(current_work)
                _flush_work(works, current_work)
                current_work = None
                state = "BIO_OR_SKIP"
                continue

            hdr = classify_section_header(txt)
            if hdr == "stop":
                state = "SKIP_APPARATUS"
                continue

            # Recover cropped y=0..4 section headers (`Phiên âm:` or `Dịch nghĩa:` sliced off above top margin)
            if (
                hdr is None
                and _is_real_scan
                and y1 <= 4.0
                and len(txt) < 65
                and current_work is not None
                and not _is_primary_han_line(txt)
            ):
                folded_top = _fold_ascii_header(txt)
                next_txt = _nfc(tagged[idx + 1][3].get("text", "")) if idx + 1 < len(tagged) else ""
                next_folded = _fold_ascii_header(next_txt)
                next_is_suite_or_tune = bool(
                    _parse_tltvn_suite_marker(next_txt)[0] is not None
                    or _TLTVN_TUNE_TITLE_RE.match(next_folded)
                    or next_folded.startswith("DIEU ")
                    or next_folded.startswith("(DIEU ")
                )
                is_cropped_header_cue = (
                    _is_all_caps_title(txt)
                    or bool(_TLTVN_TUNE_TITLE_RE.match(folded_top))
                    or folded_top.startswith("DIEU ")
                    or folded_top.startswith("(DIEU ")
                    or next_is_suite_or_tune
                )
                if is_cropped_header_cue:
                    if state == "HAN_BODY" and len(current_work.han_lines) >= 1:
                        state = "PA"
                        active_sub_label["PA"] = ""
                    elif state == "PA" and len(current_work.pa_lines) >= 1:
                        state = "DICH_NGHIA"
                        active_sub_label["DICH_NGHIA"] = ""

            if hdr == "phien_am":
                if current_work is None:
                    _start_tltvn_work(pnum)
                _touch_page(current_work, pnum)
                state = "PA"
                active_sub_label["PA"] = ""
                _, rest = _extract_header_remainder(txt, _FOLDED_PHIEN_AM_HEADER_RE)
                if rest:
                    current_work.pa_lines.append(rest)
                    sub_buckets["pa"].append((active_sub_label["PA"], rest))
                continue

            if hdr == "dich_nghia":
                if current_work is None:
                    _start_tltvn_work(pnum)
                _touch_page(current_work, pnum)
                state = "DICH_NGHIA"
                active_sub_label["DICH_NGHIA"] = ""
                _, rest = _extract_header_remainder(txt, _FOLDED_DICH_NGHIA_HEADER_RE)
                if rest:
                    current_work.dn_lines.append(rest)
                    sub_buckets["dn"].append((active_sub_label["DICH_NGHIA"], rest))
                continue

            if hdr == "dich_tho":
                if current_work is None:
                    _start_tltvn_work(pnum)
                _touch_page(current_work, pnum)
                state = "DICH_THO"
                _, rest = _extract_header_remainder(txt, _FOLDED_DICH_THO_HEADER_RE)
                if rest:
                    dt_lbl = active_sub_label["DICH_NGHIA"] or active_sub_label["PA"] or "I"
                    active_sub_label["DICH_THO"] = dt_lbl
                    current_work.dt_lines.append(rest)
                    sub_buckets["dt"].append((dt_lbl, rest))
                continue

            if state in ("BIO_OR_SKIP", "SKIP_APPARATUS") or current_work is None:
                continue

            _touch_page(current_work, pnum)

            # Check suite sub-poem markers (`I.`, `II.`, `III.`, `IV.`, `IIL`, `1.`)
            raw_marker, marker_rest = _parse_tltvn_suite_marker(txt)
            if raw_marker is not None:
                canon = _canon_marker(raw_marker)
                # Transition DICH_THO -> DICH_NGHIA for subsequent sub-poems (e.g., p0201 II., p0210 II.)
                if state == "DICH_THO":
                    state = "DICH_NGHIA"
                sec_key = state if state in ("HAN_BODY", "PA", "DICH_NGHIA") else "DICH_NGHIA"
                active_sub_label[sec_key] = canon
                if marker_rest:
                    if sec_key == "HAN_BODY":
                        current_work.han_lines.append(marker_rest)
                        sub_buckets["han"].append((canon, marker_rest))
                    else:
                        target_list = current_work.pa_lines if sec_key == "PA" else current_work.dn_lines
                        bucket_key = "pa" if sec_key == "PA" else "dn"
                        target_list.append(marker_rest)
                        sub_buckets[bucket_key].append((canon, marker_rest))
                continue

            # Guard against stray p0140 'I' right before `Dịch theo nguyên điệu:`
            if txt == "I" and idx + 1 < len(tagged) and classify_section_header(tagged[idx + 1][3].get("text", "")) == "dich_tho":
                continue

            folded = _fold_ascii_header(txt)
            is_tune = bool(_TLTVN_TUNE_TITLE_RE.match(folded))

            if state == "PA":
                if not current_work.pa_lines and _is_all_caps_title(txt):
                    current_work.pa_title = f"{current_work.pa_title} {txt}".strip() if current_work.pa_title else txt
                elif is_tune and not current_work.pa_lines:
                    current_work.pa_title = f"{current_work.pa_title} {txt}".strip() if current_work.pa_title else txt
                elif is_tune and active_sub_label["PA"]:
                    # Sub-poem tune subtitle (e.g. `II.` followed by `Vọng Giang Nam`)
                    continue
                else:
                    current_work.pa_lines.append(txt)
                    sub_buckets["pa"].append((active_sub_label["PA"], txt))
            elif state == "DICH_NGHIA":
                if not current_work.dn_lines and _is_all_caps_title(txt):
                    current_work.dn_title = f"{current_work.dn_title} {txt}".strip() if current_work.dn_title else txt
                elif is_tune and not current_work.dn_lines:
                    current_work.dn_title = f"{current_work.dn_title} {txt}".strip() if current_work.dn_title else txt
                elif is_tune and active_sub_label["DICH_NGHIA"]:
                    continue
                else:
                    current_work.dn_lines.append(txt)
                    sub_buckets["dn"].append((active_sub_label["DICH_NGHIA"], txt))
            elif state == "DICH_THO":
                dt_lbl = active_sub_label["DICH_THO"] or active_sub_label["DICH_NGHIA"] or "I"
                current_work.dt_lines.append(txt)
                sub_buckets["dt"].append((dt_lbl, txt))
            elif state == "HAN_BODY":
                if _is_all_caps_title(txt) and not current_work.pa_title:
                    current_work.pa_title = txt

    _finalize_sub_poems(current_work)
    _flush_work(works, current_work)
    return works


def segment_book_works(
    book_key: str,
    pages: Sequence[Dict[str, Any]],
    workspace_root: Optional[Path] = None,
) -> List[WorkRecord]:
    """Segment an ordered sequence of OCR pages for `TVLT2` or `TLTVN` into `WorkRecord` objects.

    Each entry in `pages` accepts `{page_num, han_items, viet_items, ...}` (and optional
    `preprocess` / `page_width` / `page_height` metadata). Works across page boundaries and
    degrades cleanly on synthetic unit-test items without full-resolution bounding boxes.
    """
    ordered_pages = sorted(pages, key=lambda p: int(p.get("page_num", 0)))
    key = book_key.upper().strip()
    if key == "TVLT2":
        return _segment_tvlt2(ordered_pages, workspace_root=workspace_root)
    if key == "TLTVN":
        return _segment_tltvn(ordered_pages)
    raise ValueError(f"Unsupported book_key for cross-page segmentation: {book_key!r}")
