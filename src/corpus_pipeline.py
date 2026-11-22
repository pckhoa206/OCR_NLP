"""End-to-End OCR-to-Aligned-Corpus Pipeline (`02_ocr_tho` -> `03_text_sach` -> `04_dong_hang`).

Reads raw page OCR bounding-box JSONs (`deliverables/<BOOK>/02_ocr_tho/{han,viet}/*.json`),
applies layout grouping, visual confusion disambiguation, Sino-Vietnamese phonetic verification,
text cleaning, work-bounded Plateau DP alignment, word coverage diagnostics, QA validation,
and exports synchronized `.tsv`, 2-sheet OpenXML `.xlsx`, and `.json` reports.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from kaggle_ocr.ocr_pipeline_kaggle import (
    BOOK_DELIVERABLE_DIRS,
    group_layout_blocks,
)
from src.aligner import (
    align_hvtt_facing_dich_tho,
    align_interlinear_4col_blocks,
    align_phien_am_to_han_chunks,
    align_work_sentences,
    count_han_chars,
    count_viet_words,
)
from src.exporter_and_qa import (
    export_tsv,
    export_xlsx_zero_dep,
    read_tsv,
    read_xlsx_zero_dep,
    validate_pairs,
)
from src.ocr_disambiguator import correct_han_line_with_phien_am
from src.phonetic_verifier import project_punctuation_from_phien_am, verify_han_phien_am_pair
from src.text_cleaner import (
    clean_han_text,
    clean_viet_text,
    split_han_sentences,
    split_viet_sentences,
)
from src.word_aligner import batch_evaluate_word_coverage
from src.work_segmenter import SubPoem, WorkRecord, segment_book_works

DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parent.parent / "config" / "book_manifest.json"
DEFAULT_WORK03_SUPPLEMENT = (
    Path("deliverables")
    / "TVLT2_ThoVanLyTran2"
    / "01_nguon"
    / "bai_03_thien_tong_chi_nam_tu_dich_nghia.txt"
)


def load_book_manifest(manifest_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load `config/book_manifest.json` or return sensible defaults if missing."""
    path = manifest_path or DEFAULT_MANIFEST_PATH
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "books": {
            "HVTT": {
                "book_id": "HVTT",
                "code": "HVTT_HanVanTinhTuy",
                "deliverable_dir": "deliverables/HVTT_HanVanTinhTuy",
                "clean_text_dir": "deliverables/HVTT_HanVanTinhTuy/03_text_sach",
                "alignment_dir": "deliverables/HVTT_HanVanTinhTuy/04_dong_hang",
                "columns": ["Hán", "Dịch âm", "Dịch nghĩa", "Dịch thơ"],
                "valid_range": {"pdf_page_start": 7, "pdf_page_end": 381},
                "excluded_pdf_pages_in_valid_range": [],
                "pilot_pages": [7, 8, 9, 10, 12, 367, 368, 369],
            },
            "TVLT2": {
                "book_id": "TVLT2",
                "code": "TVLT2_ThoVanLyTran2",
                "deliverable_dir": "deliverables/TVLT2_ThoVanLyTran2",
                "clean_text_dir": "deliverables/TVLT2_ThoVanLyTran2/03_text_sach",
                "alignment_dir": "deliverables/TVLT2_ThoVanLyTran2/04_dong_hang",
                "columns": ["Hán", "Dịch âm", "Dịch nghĩa", "Dịch thơ"],
                "valid_range": {"pdf_page_start": 17, "pdf_page_end": 861},
                "excluded_pdf_pages_in_valid_range": [25],
                "pilot_pages": [19, 20, 22, 23, 24, 26],
            },
            "TLTVN": {
                "book_id": "TLTVN",
                "code": "TLTVN_TheLoaiTuVN",
                "deliverable_dir": "deliverables/TLTVN_TheLoaiTuVN",
                "clean_text_dir": "deliverables/TLTVN_TheLoaiTuVN/03_text_sach",
                "alignment_dir": "deliverables/TLTVN_TheLoaiTuVN/04_dong_hang",
                "columns": ["Hán", "Dịch âm", "Dịch nghĩa", "Dịch thơ"],
                "valid_range": {"pdf_page_start": 134, "pdf_page_end": 547},
                "excluded_pdf_pages_in_valid_range": [378, 379, 380],
                "pilot_pages": [134, 135, 136, 137],
            },
        }
    }


def _extract_page_num(stem: str, payload: Optional[Dict[str, Any]] = None) -> int:
    if payload and isinstance(payload.get("page_num"), int):
        return int(payload["page_num"])
    matches = re.findall(r"(\d+)", stem)
    return int(matches[-1]) if matches else 0


def _is_page_in_scope(page_num: int, book_cfg: Dict[str, Any]) -> bool:
    valid_range = book_cfg.get("valid_range", {})
    start_p = int(valid_range.get("pdf_page_start", 1))
    end_p = int(valid_range.get("pdf_page_end", 10_000))
    if page_num < start_p or page_num > end_p:
        return False
    excluded = set(int(p) for p in book_cfg.get("excluded_pdf_pages_in_valid_range", []))
    return page_num not in excluded


def _load_book_ocr_pages(
    ocr_dir: Path,
    book_key: str,
    book_cfg: Dict[str, Any],
    pilot_only: bool = False,
) -> List[Dict[str, Any]]:
    """Load paired `02_ocr_tho/han/*.json` and `viet/*.json` sorted by page number."""
    han_dir = ocr_dir / "han"
    viet_dir = ocr_dir / "viet"
    if not han_dir.is_dir():
        return []

    pilot_set: Optional[Set[int]] = None
    if pilot_only and book_cfg.get("pilot_pages"):
        pilot_set = {int(p) for p in book_cfg["pilot_pages"]}

    pages: List[Dict[str, Any]] = []
    seen_pages: Set[int] = set()

    for han_file in sorted(han_dir.glob("*.json")):
        han_payload = json.loads(han_file.read_text(encoding="utf-8"))
        page_num = _extract_page_num(han_file.stem, han_payload)
        if page_num in seen_pages:
            continue
        if not _is_page_in_scope(page_num, book_cfg):
            continue
        if pilot_set is not None and page_num not in pilot_set:
            continue

        viet_file = viet_dir / han_file.name
        viet_payload = (
            json.loads(viet_file.read_text(encoding="utf-8"))
            if viet_file.is_file()
            else {"items": []}
        )

        preprocess = han_payload.get("preprocess", {})
        page_w = int(preprocess.get("effective_width") or preprocess.get("original_width") or 2000)

        layout = group_layout_blocks(
            han_items=han_payload.get("items", []),
            viet_items=viet_payload.get("items", []),
            book_type=book_key,
            page_num=page_num,
            page_width=page_w,
        )

        seen_pages.add(page_num)
        pages.append({
            "page_id": han_file.stem,
            "page_num": page_num,
            "layout": layout,
            "han_items": han_payload.get("items", []),
            "viet_items": viet_payload.get("items", []),
            "preprocess": preprocess,
        })

    pages.sort(key=lambda item: item["page_num"])
    return pages


def _deduplicate_mock_repeats(
    pages: List[Dict[str, Any]],
    is_mock_run: bool,
) -> List[Dict[str, Any]]:
    """Avoid duplicating identical synthetic mock pages when local OCR ran in mock mode."""
    if not is_mock_run:
        return pages
    deduped: List[Dict[str, Any]] = []
    seen_signatures: Set[Tuple[Any, ...]] = set()
    for p in pages:
        lay = p["layout"]
        tb = lay.get("title_block") or {}
        sig = (
            lay.get("layout_mode", ""),
            tuple(lay.get("chu_han_lines", [])),
            tuple(lay.get("phien_am_lines", [])),
            tuple(lay.get("dich_nghia_lines", [])),
            (tb.get("chu_han", ""), tb.get("phien_am", ""), tb.get("dich_nghia", "")),
        )
        if (
            not any(sig[1:4])
            and not any(sig[4])
            and not lay.get("dich_tho_lines")
        ):
            continue
        if sig in seen_signatures and (any(sig[1:4]) or any(sig[4])):
            continue
        if any(sig[1:4]) or any(sig[4]):
            seen_signatures.add(sig)
        deduped.append(p)
    return deduped


def _extract_box_y_center(item: Dict[str, Any]) -> float:
    if "box_xyxy" in item and len(item["box_xyxy"]) == 4:
        return 0.5 * (float(item["box_xyxy"][1]) + float(item["box_xyxy"][3]))
    bbox = item.get("bbox") or []
    if bbox:
        ys = [float(pt[1]) for pt in bbox]
        return 0.5 * (min(ys) + max(ys))
    return 0.0


def _align_hvtt_from_ocr(
    pages: List[Dict[str, Any]],
    stats_out: Optional[Dict[str, int]] = None,
) -> Tuple[List[Tuple[str, ...]], List[Dict[str, Any]]]:
    """Align HVTT 4-column records (`Hán`, `Dịch âm`, `Dịch nghĩa`, `Dịch thơ`) from OCR pages."""
    ordered_pages = sorted(pages, key=lambda p: int(p["page_num"]))

    # Identify even pages that actually carry Hán body triplets/lines
    even_pages_with_han: Set[int] = set()
    for p in ordered_pages:
        pnum = int(p["page_num"])
        if pnum % 2 != 0:
            continue
        lay = p["layout"]
        if lay.get("layout_mode") == "even_page_non_han_skipped":
            continue
        if lay.get("interlinear_triplets") or lay.get("chu_han_lines"):
            even_pages_with_han.add(pnum)

    # Attach odd-page facing Dịch thơ ONLY when page (p - 1) exists and has Hán rows
    odd_dich_tho_by_even_page: Dict[int, Tuple[List[str], List[float]]] = {}
    for p in ordered_pages:
        pnum = int(p["page_num"])
        if pnum % 2 != 1:
            continue
        lay = p["layout"]
        if lay.get("layout_mode") != "odd_page_dich_tho":
            continue
        if (pnum - 1) not in even_pages_with_han:
            continue
        raw_dt = lay.get("dich_tho_lines", [])
        raw_ys = lay.get("dich_tho_y_centers", [])
        cleaned_dt: List[str] = []
        cleaned_ys: List[float] = []
        for idx, line in enumerate(raw_dt):
            c_line = clean_viet_text(line)
            if not c_line:
                continue
            cleaned_dt.append(c_line)
            if idx < len(raw_ys):
                cleaned_ys.append(float(raw_ys[idx]))
        if cleaned_dt:
            odd_dich_tho_by_even_page[pnum - 1] = (cleaned_dt, cleaned_ys)

    projected_blocks: List[Dict[str, Any]] = []
    phonetic_checks: List[Dict[str, Any]] = []
    title_row_count = 0

    for p in ordered_pages:
        pnum = int(p["page_num"])
        lay = p["layout"]
        mode = lay.get("layout_mode", "")

        # Emit dedicated 4-col title row for odd title pages (pages 7, 17, 29, ..., 367)
        if pnum % 2 == 1 and mode == "odd_title_page":
            tb = lay.get("title_block") or {}
            title_han = clean_han_text(tb.get("chu_han", ""))
            title_pa = clean_viet_text(tb.get("phien_am", ""))
            title_dn = clean_viet_text(tb.get("dich_nghia", ""))
            if title_han and (title_pa or title_dn):
                projected_blocks.append({
                    "han": title_han,
                    "dich_am": title_pa,
                    "dich_nghia": title_dn,
                    "dich_tho": "",
                    "is_title": True,
                })
                title_row_count += 1
            continue

        if pnum % 2 != 0 or pnum not in even_pages_with_han:
            continue

        triplets = lay.get("interlinear_triplets", [])
        han_lines = lay.get("chu_han_lines", [])
        phien_am_lines = lay.get("phien_am_lines", [])
        dich_nghia_lines = lay.get("dich_nghia_lines", [])

        # Honor has_dich_nghia == False (e.g. p0100 Thạch Hào Lại) and final poem (p >= 367)
        has_dich_nghia = bool(lay.get("has_dich_nghia", True)) and pnum < 367

        raw_han_list: List[str] = []
        raw_pa_list: List[str] = []
        raw_dn_list: List[str] = []

        if triplets:
            for idx, tr in enumerate(triplets):
                h_txt = tr.get("chu_han", "").strip()
                if not h_txt:
                    continue
                pa_txt = tr.get("phien_am", "").strip()
                dn_txt = "" if not has_dich_nghia else (
                    tr.get("dich_nghia_gloss", "").strip()
                    or (dich_nghia_lines[idx].strip() if idx < len(dich_nghia_lines) else "")
                )
                raw_han_list.append(h_txt)
                raw_pa_list.append(pa_txt)
                raw_dn_list.append(dn_txt)
        else:
            for idx, h_txt in enumerate(han_lines):
                raw_han_list.append(h_txt)
                raw_pa_list.append(phien_am_lines[idx] if idx < len(phien_am_lines) else "")
                raw_dn_list.append(
                    "" if not has_dich_nghia else (dich_nghia_lines[idx] if idx < len(dich_nghia_lines) else "")
                )

        if not raw_han_list:
            continue

        page_rows: List[Dict[str, Any]] = []
        for h_raw, pa_raw, dn_raw in zip(raw_han_list, raw_pa_list, raw_dn_list):
            corrected_han, _ = correct_han_line_with_phien_am(h_raw, pa_raw)
            if pa_raw:
                phonetic_checks.append(verify_han_phien_am_pair(corrected_han, pa_raw))
                punct_han = project_punctuation_from_phien_am(corrected_han, pa_raw)
            else:
                punct_han = clean_han_text(corrected_han)

            page_rows.append({
                "han": punct_han,
                "dich_am": clean_viet_text(pa_raw),
                "dich_nghia": "" if not has_dich_nghia else clean_viet_text(dn_raw),
                "dich_tho": "",
                "is_title": False,
            })

        # Extract Hán y-centers for facing Dịch thơ vertical DP alignment
        han_y_centers: Optional[List[float]] = None
        primary_han_ys = [
            _extract_box_y_center(it)
            for it in p.get("han_items", [])
            if any("\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf" for ch in str(it.get("text", "")))
        ]
        if len(primary_han_ys) == len(page_rows):
            han_y_centers = primary_han_ys

        inline_dt = [clean_viet_text(x) for x in lay.get("dich_tho_lines", []) if clean_viet_text(x)]
        facing_dt, facing_dt_ys = odd_dich_tho_by_even_page.get(pnum, ([], []))

        if facing_dt:
            aligned_dt = align_hvtt_facing_dich_tho(
                page_rows,
                facing_dt,
                han_y_centers=han_y_centers,
                dt_y_centers=facing_dt_ys if len(facing_dt_ys) == len(facing_dt) else None,
            )
        elif inline_dt:
            if len(inline_dt) == len(page_rows):
                aligned_dt = inline_dt
            else:
                aligned_dt = align_hvtt_facing_dich_tho(
                    page_rows,
                    inline_dt,
                    han_y_centers=han_y_centers,
                )
        else:
            aligned_dt = [""] * len(page_rows)

        for row_dict, dt_val in zip(page_rows, aligned_dt):
            row_dict["dich_tho"] = dt_val
            projected_blocks.append(row_dict)

    pairs = align_interlinear_4col_blocks(projected_blocks)
    if stats_out is not None:
        stats_out["title_rows"] = title_row_count
    return pairs, phonetic_checks


# ---------------------------------------------------------------------------
# Sequential Book (TVLT2 & TLTVN) 4-Column Title + Body Alignment Helpers
# ---------------------------------------------------------------------------

_HAN_SENT_PUNCT_RE = re.compile(r"[，。！？；：.,?!;:]")
_VIET_SENT_PUNCT_RE = re.compile(r"[.,;:?!]")
_KNOWN_TUNE_HAN_TITLES = frozenset({
    "阮郎歸", "西江月", "鷓鴣天", "鹧鴣天", "沁園春", "春光好", "隔浦蓮",
    "步步蟾", "一剪梅", "風雨恨", "憶秦娥", "畫堂春", "賀聖朝", "宮中調笑",
    "蟾宮閨怨", "雨中花", "滿庭芳", "望江南", "長相思", "南鄉子", "謁金門",
    "桂枝香", "清平樂", "菩薩蠻", "漁家傲", "小重山", "感皇恩",
})
_KE_MARKER_HAN_RE = re.compile(r"偈[曰日云雲]")
_KE_MARKER_VIET_RE = re.compile(
    r"^\s*(?:K[EỆÊ]\s*(?:VI[EÊ]T|R[AẰ]NG)|B[AÀ]I\s*K[EỆ]|V[AẬ]Y\s*C[OÓ]\s*K[EỆ]|C[OÓ]\s*K[EỆ]|L[AẠ]I\s*C[OÓ]\s*K[EỆ])\b",
    flags=re.IGNORECASE,
)
_TRANSLATOR_SIG_LINE_RE = re.compile(
    r"(?:DAO\s*PHUONG\s*BINH|BANG\s*THANH|NGUYEN\s*DONG\s*CHI|HUE\s*CHI|"
    r"DO\s*VAN\s*HY|DU\s*VAN\s*HY|NGUYEN\s*DUC\s*VAN|TRAN\s*LE\s*SANG|HOANG\s*LE)",
    flags=re.IGNORECASE,
)


def _fold_ascii_simple(text: str) -> str:
    import unicodedata

    decomposed = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn").strip()


def _is_tltvn_han_title_line(text: str) -> bool:
    s = text.strip()
    if not s:
        return False
    if (s.startswith("(") and s.endswith(")")) or (s.startswith("（") and s.endswith("）")):
        return count_han_chars(s) <= 10
    if _HAN_SENT_PUNCT_RE.search(s):
        return False
    return 1 <= count_han_chars(s) <= 12


def _is_tltvn_viet_title_line(text: str, max_words: int = 10) -> bool:
    s = clean_viet_text(text)
    if not s or _VIET_SENT_PUNCT_RE.search(s):
        return False
    return 1 <= count_viet_words(s) <= max_words


def _extract_tltvn_sub_titles(
    work: WorkRecord,
    pages_by_num: Dict[int, Dict[str, Any]],
) -> Dict[str, Tuple[str, str]]:
    """Extract authentic printed `(pa_tune_title, dn_tune_title)` for `I, II, III, IV` from work pages."""
    from src.work_segmenter import _parse_tltvn_suite_marker
    from kaggle_ocr.ocr_pipeline_kaggle import classify_section_header

    canon_map = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V", "6": "VI", "IIL": "III"}
    found: Dict[str, Dict[str, str]] = {}
    section = "PA"
    for pnum in work.source_pages:
        page = pages_by_num.get(pnum)
        if not page:
            continue
        viet_items = page.get("viet_items") or []
        for idx, it in enumerate(viet_items):
            txt = str(it.get("text", "")).strip()
            if not txt:
                continue
            hdr = classify_section_header(txt)
            if hdr == "phien_am":
                section = "PA"
                continue
            if hdr == "dich_nghia":
                section = "DN"
                continue
            if hdr == "dich_tho":
                section = "DT"
                continue
            if hdr == "stop":
                section = "STOP"
                continue

            marker, rest = _parse_tltvn_suite_marker(txt)
            if marker is None:
                continue
            lbl = marker.strip().rstrip(".").upper()
            lbl = canon_map.get(lbl, lbl)
            if section == "DT":
                section = "DN"
            cand = rest
            if not cand and idx + 1 < len(viet_items):
                nxt = str(viet_items[idx + 1].get("text", "")).strip()
                if nxt and classify_section_header(nxt) is None and not nxt.isdigit() and count_viet_words(nxt) <= 7:
                    cand = nxt
            if not cand:
                continue
            cand_clean = clean_viet_text(cand)
            if not cand_clean:
                continue
            folded = _fold_ascii_simple(cand_clean).upper()
            is_tune_like = (
                "DIEU" in folded
                or any(kw in folded for kw in (
                    "THIEM CUNG", "VU TRUNG", "MAN DINH", "VONG GIANG", "VONG GTANG",
                    "TRUONG TUONG", "TRUONG TRUONG",
                ))
                or count_viet_words(cand_clean) <= 5
            )
            if is_tune_like:
                bucket = found.setdefault(lbl, {})
                if section == "PA" and "pa" not in bucket:
                    bucket["pa"] = cand_clean
                elif section == "DN" and "dn" not in bucket:
                    bucket["dn"] = cand_clean
    return {lbl: (d.get("pa", ""), d.get("dn", "")) for lbl, d in found.items()}


def _split_tltvn_incomplete_suite_han(work: WorkRecord) -> None:
    """Recover missing `SubPoem.han_lines` (e.g. TLTVN W18/W24) by splitting at inline Hán tune titles."""
    if not work.sub_poems or all(sp.han_lines for sp in work.sub_poems):
        return
    all_han = list(work.han_lines)
    if not all_han:
        return
    # Skip leading suite main title if present
    start_idx = 0
    if len(all_han) >= 2 and _is_tltvn_han_title_line(all_han[0]) and _is_tltvn_han_title_line(all_han[1]):
        start_idx = 1
    chunks: List[List[str]] = []
    cur: List[str] = []
    for ln in all_han[start_idx:]:
        compact = re.sub(r"[\s()（）]", "", ln)
        if compact in _KNOWN_TUNE_HAN_TITLES and cur:
            chunks.append(cur)
            cur = [ln]
        else:
            cur.append(ln)
    if cur:
        chunks.append(cur)
    if len(chunks) == len(work.sub_poems):
        for sp, ch in zip(work.sub_poems, chunks):
            sp.han_lines = ch


def _repair_w21_subpoems(sub_poems: List[SubPoem]) -> List[SubPoem]:
    """Repair TVLT2 Work #21 (*Niêm tụng kệ*) when OCR misses a `Cử`/`Nêu` cue and merges 2 tiết."""
    if not sub_poems or not any(not sp.pa_lines or not sp.dn_lines for sp in sub_poems):
        return sub_poems

    def _split_double_viet_group(lines: List[str]) -> Optional[Tuple[List[str], List[str]]]:
        if len(lines) < 16:
            return None
        tung_indices: List[int] = []
        for idx, ln in enumerate(lines):
            folded = _fold_ascii_simple(ln).upper()
            if re.match(r"^(?:TUNG|TỤNG|TUG)\b", folded) and count_viet_words(ln) <= 2:
                tung_indices.append(idx)
        if len(tung_indices) >= 2:
            # First Tụng stanza typically has 4 verse lines following the marker
            first_t = tung_indices[0]
            split_idx = min(len(lines) - 1, first_t + 5)
            # Ensure split_idx stops before second Niêm/Tụng cycle
            if split_idx < tung_indices[1]:
                return lines[:split_idx], lines[split_idx:]
        return None

    han_groups = [list(sp.han_lines) for sp in sub_poems if sp.han_lines]
    pa_groups: List[List[str]] = []
    for sp in sub_poems:
        if not sp.pa_lines:
            continue
        split_res = _split_double_viet_group(sp.pa_lines) if len(sub_poems) > 10 else None
        if split_res is not None and len(pa_groups) + 2 <= len(han_groups):
            pa_groups.extend([split_res[0], split_res[1]])
        else:
            pa_groups.append(list(sp.pa_lines))

    dn_groups: List[List[str]] = []
    for sp in sub_poems:
        if not sp.dn_lines:
            continue
        split_res = _split_double_viet_group(sp.dn_lines) if len(sub_poems) > 10 else None
        if split_res is not None and len(dn_groups) + 2 <= len(han_groups):
            dn_groups.extend([split_res[0], split_res[1]])
        else:
            dn_groups.append(list(sp.dn_lines))

    if len(pa_groups) == len(han_groups) and len(dn_groups) == len(han_groups):
        repaired: List[SubPoem] = []
        for idx, (h_g, p_g, d_g) in enumerate(zip(han_groups, pa_groups, dn_groups)):
            repaired.append(
                SubPoem(
                    sub_id=sub_poems[idx].sub_id if idx < len(sub_poems) else f"21_{idx + 1:02d}",
                    label=sub_poems[idx].label if idx < len(sub_poems) else f"Tiết {idx + 1}",
                    han_lines=h_g,
                    pa_lines=p_g,
                    dn_lines=d_g,
                )
            )
        return repaired
    return sub_poems


def _align_verse_unit(
    han_lines: List[str],
    pa_lines: List[str],
    dn_lines: List[str],
    dt_lines: List[str],
    phonetic_checks: List[Dict[str, Any]],
) -> List[Tuple[str, str, str, str]]:
    """Align a poem, từ, or kệ unit into 4-column `(Hán, Dịch âm, Dịch nghĩa, Dịch thơ)` rows."""
    h_clean = [clean_han_text(ln) for ln in han_lines if clean_han_text(ln)]
    pa_clean = [clean_viet_text(ln) for ln in pa_lines if clean_viet_text(ln) and re.search(r"[A-Za-zÀ-ỹà-ỹ]", ln)]
    dn_clean = [clean_viet_text(ln) for ln in dn_lines if clean_viet_text(ln) and re.search(r"[A-Za-zÀ-ỹà-ỹ]", ln)]
    dt_clean = [clean_viet_text(ln) for ln in dt_lines if clean_viet_text(ln) and re.search(r"[A-Za-zÀ-ỹà-ỹ]", ln)]

    if not h_clean or (not pa_clean and not dn_clean and not dt_clean):
        return []

    # Run phonetic correction / verification when line counts match 1:1
    if len(h_clean) == len(pa_clean):
        corrected_h: List[str] = []
        for h_ln, pa_ln in zip(h_clean, pa_clean):
            corr, _ = correct_han_line_with_phien_am(h_ln, pa_ln)
            phonetic_checks.append(verify_han_phien_am_pair(corr, pa_ln))
            corrected_h.append(clean_han_text(corr) or h_ln)
        h_clean = corrected_h

    # Fast exact 1:1 line alignment when Hán and Dịch nghĩa match line-for-line
    if dn_clean and len(h_clean) == len(dn_clean):
        if len(pa_clean) == len(h_clean):
            pa_aligned = pa_clean
        elif pa_clean:
            pa_aligned = align_phien_am_to_han_chunks(h_clean, pa_clean)
        else:
            pa_aligned = [""] * len(h_clean)

        if not dt_clean:
            dt_aligned = [""] * len(h_clean)
        elif len(dt_clean) == len(h_clean):
            dt_aligned = dt_clean
        elif len(dt_clean) == 2 * len(h_clean) and len(h_clean) >= 4:
            dt_aligned = [f"{dt_clean[i]} / {dt_clean[i + len(h_clean)]}" for i in range(len(h_clean))]
        else:
            backbone = [
                {"han": h, "dich_am": pa, "dich_nghia": dn}
                for h, pa, dn in zip(h_clean, pa_aligned, dn_clean)
            ]
            dt_aligned = align_hvtt_facing_dich_tho(backbone, dt_clean)

        return list(zip(h_clean, pa_aligned, dn_clean, dt_aligned))

    # No Dịch nghĩa at all -> align against Dịch thơ or Phiên âm
    target_viet = dn_clean if dn_clean else (dt_clean if dt_clean else pa_clean)
    aligned = align_work_sentences(h_clean, target_viet)
    if not aligned:
        return []

    h_chunks = [it["han"] for it in aligned]
    if not dn_clean:
        dn_aligned = [""] * len(aligned)
    else:
        dn_aligned = [it["viet"] for it in aligned]

    if not pa_clean:
        pa_aligned = [""] * len(aligned)
    elif len(pa_clean) == len(h_clean):
        pa_aligned = [
            clean_viet_text(" ".join(pa_clean[i] for i in it["han_indices"] if i < len(pa_clean)))
            for it in aligned
        ]
    elif dn_clean and len(pa_clean) == len(dn_clean):
        pa_aligned = [
            clean_viet_text(" ".join(pa_clean[j] for j in it["viet_indices"] if j < len(pa_clean)))
            for it in aligned
        ]
    else:
        pa_aligned = align_phien_am_to_han_chunks(h_chunks, pa_clean)

    if not dt_clean:
        dt_aligned = [""] * len(aligned)
    elif not dn_clean and target_viet is dt_clean:
        dt_aligned = [it["viet"] for it in aligned]
    elif len(dt_clean) == len(aligned):
        dt_aligned = dt_clean
    elif dn_clean and len(dt_clean) == len(dn_clean):
        dt_aligned = [
            " / ".join(dt_clean[j] for j in it["viet_indices"] if j < len(dt_clean))
            for it in aligned
        ]
    elif len(dt_clean) == 2 * len(aligned) and len(aligned) >= 4:
        dt_aligned = [f"{dt_clean[i]} / {dt_clean[i + len(aligned)]}" for i in range(len(aligned))]
    else:
        backbone = [
            {"han": h, "dich_am": pa, "dich_nghia": dn}
            for h, pa, dn in zip(h_chunks, pa_aligned, dn_aligned)
        ]
        dt_aligned = align_hvtt_facing_dich_tho(backbone, dt_clean)

    return list(zip(h_chunks, pa_aligned, dn_aligned, dt_aligned))


def _align_prose_unit(
    han_lines: List[str],
    pa_lines: List[str],
    dn_lines: List[str],
    phonetic_checks: List[Dict[str, Any]],
) -> List[Tuple[str, str, str, str]]:
    """Align a Classical Chinese prose unit with `Dịch nghĩa` sentence DP and `Phiên âm` projection."""
    h_cleaned_lines = [clean_han_text(ln) for ln in han_lines if clean_han_text(ln)]
    if not h_cleaned_lines:
        return []
    han_joined = "".join(h_cleaned_lines)
    han_sents = split_han_sentences(han_joined, mode="clause_or_sent")
    if not han_sents:
        han_sents = [han_joined]

    pa_cleaned_lines = [clean_viet_text(ln) for ln in pa_lines if clean_viet_text(ln) and re.search(r"[A-Za-zÀ-ỹà-ỹ]", ln)]
    dn_joined = clean_viet_text("\n".join(dn_lines)) if dn_lines else ""

    dn_sents = split_viet_sentences(dn_joined, mode="sent") if dn_joined else []
    dn_sents = [s for s in dn_sents if re.search(r"[A-Za-zÀ-ỹà-ỹ]", s)]
    if not dn_sents and dn_joined and re.search(r"[A-Za-zÀ-ỹà-ỹ]", dn_joined):
        dn_sents = [dn_joined]

    if not dn_sents:
        if not pa_cleaned_lines:
            return []
        pa_aligned = align_phien_am_to_han_chunks(han_sents, pa_cleaned_lines)
        return [(h, pa, "", "") for h, pa in zip(han_sents, pa_aligned) if pa]

    # Recover VietOCR `,` -> `.` sentence runs when sentence count is far below Hán clause count
    if len(han_sents) >= 4 and len(dn_sents) < 0.65 * len(han_sents):
        dn_clause = split_viet_sentences(dn_joined, mode="clause_or_sent")
        if len(dn_clause) > len(dn_sents):
            dn_sents = dn_clause
        if len(dn_sents) < 0.60 * len(han_sents):
            expanded: List[str] = []
            cap_split_re = re.compile(r",\s+(?=[A-ZĐÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ])")
            for seg in dn_sents:
                parts = [clean_viet_text(p) for p in cap_split_re.split(seg) if clean_viet_text(p)]
                expanded.extend(parts if parts else [seg])
            if len(expanded) > len(dn_sents):
                dn_sents = expanded

    # If Hán sentences are still >3x Vietnamese sentences, group ultra-short Hán clauses with neighbors
    if len(han_sents) > 3 * len(dn_sents) and len(han_sents) >= 6:
        grouped_h: List[str] = []
        buf_h = ""
        for hs in han_sents:
            buf_h = f"{buf_h}{hs}" if buf_h else hs
            if count_han_chars(buf_h) >= 12 or len(grouped_h) + (len(han_sents) - 1) < len(dn_sents):
                grouped_h.append(buf_h)
                buf_h = ""
        if buf_h:
            if grouped_h:
                grouped_h[-1] = f"{grouped_h[-1]}{buf_h}"
            else:
                grouped_h.append(buf_h)
        if len(grouped_h) >= len(dn_sents):
            han_sents = grouped_h

    aligned = align_work_sentences(han_sents, dn_sents)
    if not aligned:
        return []

    h_chunks = [it["han"] for it in aligned]
    dn_chunks = [it["viet"] for it in aligned]
    pa_aligned = align_phien_am_to_han_chunks(h_chunks, pa_cleaned_lines) if pa_cleaned_lines else [""] * len(h_chunks)

    for h_c, pa_c in zip(h_chunks, pa_aligned):
        if pa_c:
            phonetic_checks.append(verify_han_phien_am_pair(h_c, pa_c))

    return [(h, pa, dn, "") for h, pa, dn in zip(h_chunks, pa_aligned, dn_chunks)]


def _split_at_ke_marker(lines: List[str], pattern: re.Pattern[str]) -> Optional[Tuple[List[str], List[str]]]:
    for idx, ln in enumerate(lines):
        if pattern.search(ln):
            # Include the cue line if inline verse follows, or skip standalone cue
            after = lines[idx + 1 :]
            if after:
                return lines[:idx], after
    return None


def _align_mixed_prose_and_ke(
    work: WorkRecord,
    han_lines: List[str],
    pa_lines: List[str],
    dn_lines: List[str],
    dt_lines: List[str],
    phonetic_checks: List[Dict[str, Any]],
) -> List[Tuple[str, str, str, str]]:
    """Align TVLT2 prose works that contain embedded or trailing `Kệ` verse sections."""
    clean_dt = [
        clean_viet_text(ln)
        for ln in dt_lines
        if clean_viet_text(ln) and not _TRANSLATOR_SIG_LINE_RE.search(_fold_ascii_simple(ln))
    ]
    if not clean_dt:
        return _align_prose_unit(han_lines, pa_lines, dn_lines, phonetic_checks)

    # Case A: Work #5 Phổ thuyết tứ sơn (5 Kệ stanzas: 4 + 8 + 8 + 8 + 8 = 36 DT lines)
    if work.work_id == 5 or ("四山" in work.han_title and len(clean_dt) >= 24):
        h_ke_indices = [i for i, ln in enumerate(han_lines) if _KE_MARKER_HAN_RE.search(ln)]
        pa_ke_indices = [i for i, ln in enumerate(pa_lines) if re.search(r"\b(?:KE|IỆS)\b", _fold_ascii_simple(ln).upper())]
        dn_ke_indices = [i for i, ln in enumerate(dn_lines) if re.search(r"\bKE\s*(?:RANG|VE)\b", _fold_ascii_simple(ln).upper())]
        if len(h_ke_indices) == 5 and len(pa_ke_indices) >= 4 and len(dn_ke_indices) == 5 and len(clean_dt) >= 32:
            # Known stanza lengths for Phổ thuyết tứ sơn: 4, 8, 8, 8, 8 (36 lines)
            dt_slices = [clean_dt[0:4], clean_dt[4:12], clean_dt[12:20], clean_dt[20:28], clean_dt[28:]]
            h_end_cues = [
                next((j for j in range(h_ke_indices[0] + 1, len(han_lines)) if han_lines[j].strip() == "山"), h_ke_indices[0] + 3),
                next((j for j in range(h_ke_indices[1] + 1, len(han_lines)) if "二山" in han_lines[j]), h_ke_indices[1] + 9),
                next((j for j in range(h_ke_indices[2] + 1, len(han_lines)) if "三山" in han_lines[j]), h_ke_indices[2] + 7),
                next((j for j in range(h_ke_indices[3] + 1, len(han_lines)) if "四山" in han_lines[j]), h_ke_indices[3] + 8),
                len(han_lines),
            ]
            dn_end_cues = [
                next((j for j in range(dn_ke_indices[0] + 1, len(dn_lines)) if "NÚI THỨ HAI" in _fold_ascii_simple(dn_lines[j]).upper().replace("U", "U")), dn_ke_indices[0] + 5),
                next((j for j in range(dn_ke_indices[1] + 1, len(dn_lines)) if "NUI THU HAI" in _fold_ascii_simple(dn_lines[j]).upper()), dn_ke_indices[1] + 9),
                next((j for j in range(dn_ke_indices[2] + 1, len(dn_lines)) if "NUI THU BA" in _fold_ascii_simple(dn_lines[j]).upper()), dn_ke_indices[2] + 9),
                next((j for j in range(dn_ke_indices[3] + 1, len(dn_lines)) if "NUI THU TU" in _fold_ascii_simple(dn_lines[j]).upper()), dn_ke_indices[3] + 9),
                len(dn_lines),
            ]
            # Approximate PA breaks around Nhị sơn / Tam sơn / Tứ sơn if needed
            pa_n1 = next((i for i, ln in enumerate(pa_lines) if "NHAT SON" in _fold_ascii_simple(ln).upper()), h_end_cues[0])
            pa_n2 = next((i for i, ln in enumerate(pa_lines) if "NHI SON" in _fold_ascii_simple(ln).upper()), pa_n1 + 10)
            pa_n3 = next((i for i, ln in enumerate(pa_lines) if "TAM SON" in _fold_ascii_simple(ln).upper()), pa_n2 + 10)
            pa_n4 = next((i for i, ln in enumerate(pa_lines) if "TU SON" in _fold_ascii_simple(ln).upper() and i > pa_n3), pa_n3 + 10)
            pa_k_starts = [
                pa_ke_indices[0] + 1,
                next((i + 1 for i in range(pa_n1, pa_n2) if "KE" in _fold_ascii_simple(pa_lines[i]).upper()), max(pa_n1, pa_n2 - 8)),
                next((i + 1 for i in range(pa_n2, pa_n3) if "KE" in _fold_ascii_simple(pa_lines[i]).upper()), max(pa_n2, pa_n3 - 8)),
                next((i + 1 for i in range(pa_n3, pa_n4) if "KE" in _fold_ascii_simple(pa_lines[i]).upper()), max(pa_n3, pa_n4 - 8)),
                next((i + 1 for i in range(pa_n4, len(pa_lines)) if "KE" in _fold_ascii_simple(pa_lines[i]).upper()), max(pa_n4, len(pa_lines) - 8)),
            ]
            pa_ends = [pa_n1, pa_n2, pa_n3, pa_n4, len(pa_lines)]

            rows_w5: List[Tuple[str, str, str, str]] = []
            h_cur = 0
            pa_cur = 0
            dn_cur = 0
            for idx_k in range(5):
                hk_s = h_ke_indices[idx_k] + 1
                hk_e = h_end_cues[idx_k]
                pk_s = pa_k_starts[idx_k]
                pk_e = pa_ends[idx_k]
                dk_s = dn_ke_indices[idx_k] + 1
                dk_e = dn_end_cues[idx_k]

                rows_w5.extend(_align_prose_unit(han_lines[h_cur:hk_s], pa_lines[pa_cur:pk_s], dn_lines[dn_cur:dk_s], phonetic_checks))
                rows_w5.extend(_align_verse_unit(han_lines[hk_s:hk_e], pa_lines[pk_s:pk_e], dn_lines[dk_s:dk_e], dt_slices[idx_k], phonetic_checks))
                h_cur, pa_cur, dn_cur = hk_e, pk_e, dk_e
            if rows_w5:
                return rows_w5

    # Case B: Single trailing Kệ (`偈曰`/`Kệ viết`/`Kệ rằng`) or trailing 4-line verse matching DT
    h_split = _split_at_ke_marker(han_lines, _KE_MARKER_HAN_RE)
    pa_split = _split_at_ke_marker(pa_lines, re.compile(r"^\s*K[ệêeế]\s*(?:viết|viêt|vân)\b", re.IGNORECASE))
    dn_split = _split_at_ke_marker(dn_lines, _KE_MARKER_VIET_RE)

    if h_split and pa_split and dn_split:
        h_prose, h_ke = h_split
        pa_prose, pa_ke = pa_split
        dn_prose, dn_ke = dn_split
        rows = _align_prose_unit(h_prose, pa_prose, dn_prose, phonetic_checks)
        rows.extend(_align_verse_unit(h_ke, pa_ke, dn_ke, clean_dt, phonetic_checks))
        return rows

    if len(clean_dt) <= 8 and len(han_lines) > len(clean_dt) and len(pa_lines) > len(clean_dt) and len(dn_lines) > len(clean_dt):
        k_n = len(clean_dt)
        h_ke_tail = han_lines[-k_n:]
        if all(count_han_chars(ln) <= 10 for ln in h_ke_tail):
            rows = _align_prose_unit(han_lines[:-k_n], pa_lines[:-k_n], dn_lines[:-k_n], phonetic_checks)
            rows.extend(_align_verse_unit(h_ke_tail, pa_lines[-k_n:], dn_lines[-k_n:], clean_dt, phonetic_checks))
            return rows

    # Fallback: align prose and attach DT onto trailing verse rows
    prose_rows = _align_prose_unit(han_lines, pa_lines, dn_lines, phonetic_checks)
    if prose_rows and clean_dt:
        k_tail = min(len(prose_rows), len(clean_dt))
        tail_dicts = [{"han": r[0], "dich_am": r[1], "dich_nghia": r[2]} for r in prose_rows[-k_tail:]]
        dt_tail = align_hvtt_facing_dich_tho(tail_dicts, clean_dt)
        for offset in range(k_tail):
            r_idx = len(prose_rows) - k_tail + offset
            h_v, pa_v, dn_v, _ = prose_rows[r_idx]
            prose_rows[r_idx] = (h_v, pa_v, dn_v, dt_tail[offset])
    return prose_rows


def _align_sequential_book_from_ocr(
    book_key: str,
    pages: List[Dict[str, Any]],
    workspace_root: Path,
    stats_out: Optional[Dict[str, int]] = None,
) -> Tuple[List[Tuple[str, ...]], List[Dict[str, Any]]]:
    """Align TVLT2 / TLTVN works into 4-column rows with dedicated work/sub-poem title rows."""
    works = segment_book_works(book_key, pages, workspace_root=workspace_root)
    pages_by_num = {int(p["page_num"]): p for p in pages}
    all_pairs: List[Tuple[str, ...]] = []
    phonetic_checks: List[Dict[str, Any]] = []
    title_rows_count = 0

    for work in works:
        # Skip incomplete trailing fragment (e.g. TLTVN W36 at member split p.237 with zero Viet text)
        if not work.pa_lines and not work.dn_lines and not work.dt_lines and not work.sub_poems:
            continue

        if book_key == "TVLT2":
            han_title = clean_han_text(work.han_title)
            pa_title = clean_viet_text(work.pa_title)
            dn_title = clean_viet_text(work.dn_title)
            han_lines = list(work.han_lines)
            pa_lines = list(work.pa_lines)
            dn_lines = list(work.dn_lines)
            dt_lines = list(work.dt_lines)

            # Fix Work #3: filter out p.26-27 Dịch nghĩa lines that leaked into pa_lines across blank p.25
            if work.metadata.get("dn_source") == "bai_03_thien_tong_chi_nam_tu_dich_nghia.txt":
                pa_meta = work.metadata.get("_pa_meta") or []
                if pa_meta:
                    pa_lines = [m["text"] for m in pa_meta if int(m.get("page", 0)) <= 24]

            # Recover unextracted work number + ALL-CAPS pa_title on prose works (e.g. W06, W07, W11)
            if not pa_title and pa_lines:
                if re.match(r"^\d{1,2}$", pa_lines[0].strip()):
                    pa_lines = pa_lines[1:]
                if pa_lines and _fold_ascii_simple(pa_lines[0]).isupper() and count_viet_words(pa_lines[0]) <= 10:
                    pa_title = clean_viet_text(re.sub(r"\s+\d{1,2}$", "", pa_lines[0].strip()))
                    pa_lines = pa_lines[1:]

            if han_title and (pa_title or dn_title):
                all_pairs.append((han_title, pa_title, dn_title, ""))
                title_rows_count += 1

            # Work #21: Niêm tụng kệ (43 tiết)
            if work.sub_poems:
                repaired_subs = _repair_w21_subpoems(list(work.sub_poems))
                for sp in repaired_subs:
                    if not sp.han_lines or (not sp.pa_lines and not sp.dn_lines):
                        continue
                    sp_rows = _align_verse_unit(sp.han_lines, sp.pa_lines, sp.dn_lines, sp.dt_lines, phonetic_checks)
                    all_pairs.extend(sp_rows)
                continue

            if work.is_two_column:
                all_pairs.extend(_align_verse_unit(han_lines, pa_lines, dn_lines, dt_lines, phonetic_checks))
            elif dt_lines:
                all_pairs.extend(_align_mixed_prose_and_ke(work, han_lines, pa_lines, dn_lines, dt_lines, phonetic_checks))
            else:
                all_pairs.extend(_align_prose_unit(han_lines, pa_lines, dn_lines, phonetic_checks))
            continue

        # TLTVN: Từ khúc & multi-poem suites
        han_title_raw = work.han_title.strip()
        pa_title = clean_viet_text(work.pa_title)
        dn_title = clean_viet_text(work.dn_title)
        han_lines = list(work.han_lines)
        pa_lines = list(work.pa_lines)
        dn_lines = list(work.dn_lines)
        dt_lines = list(work.dt_lines)

        if work.sub_poems:
            _split_tltvn_incomplete_suite_han(work)
            # Extract suite-level Hán title (`春夜懷情人`, `戎婦寄征夫`, `征夫寄還`)
            if not han_title_raw and han_lines and _is_tltvn_han_title_line(han_lines[0]):
                han_title_raw = han_lines[0]
                if (
                    len(han_lines) >= 3
                    and _is_tltvn_han_title_line(han_lines[1])
                    and re.sub(r"[\s()（）]", "", han_lines[1]) in _KNOWN_TUNE_HAN_TITLES
                    and not work.sub_poems
                ):
                    han_title_raw = f"{han_title_raw} {han_lines[1]}"

            han_title = clean_han_text(han_title_raw)
            if han_title and (pa_title or dn_title):
                all_pairs.append((han_title, pa_title, dn_title, ""))
                title_rows_count += 1

            sub_viet_titles = _extract_tltvn_sub_titles(work, pages_by_num)
            for sp in work.sub_poems:
                sp_h = list(sp.han_lines)
                sp_pa = list(sp.pa_lines)
                sp_dn = list(sp.dn_lines)
                sp_dt = list(sp.dt_lines)
                if not sp_h or (not sp_pa and not sp_dn and not sp_dt):
                    continue

                sub_h_title = ""
                if sp_h and _is_tltvn_han_title_line(sp_h[0]):
                    sub_h_title = clean_han_text(sp_h[0])
                    sp_h = sp_h[1:]

                sub_pa_title, sub_dn_title = sub_viet_titles.get(sp.label, ("", ""))
                if sp_pa and _is_tltvn_viet_title_line(sp_pa[0], max_words=6):
                    folded_pa0 = _fold_ascii_simple(sp_pa[0]).lower()
                    if any(k in folded_pa0 for k in ("truong", "vong", "man", "thiem", "vu trung")):
                        if not sub_pa_title:
                            sub_pa_title = clean_viet_text(sp_pa[0])
                        sp_pa = sp_pa[1:]

                if sub_h_title and (sub_pa_title or sub_dn_title):
                    all_pairs.append((sub_h_title, sub_pa_title, sub_dn_title, ""))
                    title_rows_count += 1

                all_pairs.extend(_align_verse_unit(sp_h, sp_pa, sp_dn, sp_dt, phonetic_checks))
            continue

        # Single-work TLTVN
        if not han_title_raw and han_lines and _is_tltvn_han_title_line(han_lines[0]):
            first_h = han_lines.pop(0).strip()
            if han_lines and len(han_lines) >= 2 and _is_tltvn_han_title_line(han_lines[0]):
                second_h = han_lines.pop(0).strip()
                second_inner = second_h.strip("()（） ")
                han_title_raw = f"{first_h}（{second_inner}）"
            else:
                han_title_raw = first_h

        if not pa_title and pa_lines and len(pa_lines) >= 2 and _is_tltvn_viet_title_line(pa_lines[0], max_words=9):
            pa_title = clean_viet_text(pa_lines.pop(0))
        if not dn_title and dn_lines and len(dn_lines) >= 2 and _is_tltvn_viet_title_line(dn_lines[0], max_words=12):
            dn_title = clean_viet_text(dn_lines.pop(0))

        han_title = clean_han_text(han_title_raw)
        if han_title and (pa_title or dn_title):
            all_pairs.append((han_title, pa_title, dn_title, ""))
            title_rows_count += 1

        # Detect prose-heavy TLTVN intro (e.g. W35 Quan lan thập cảnh từ tính dẫn)
        is_prose_intro = (
            not dt_lines
            and han_lines
            and dn_lines
            and len(dn_lines) >= 2 * len(han_lines)
            and any(count_han_chars(ln) >= 22 for ln in han_lines)
        )
        if is_prose_intro:
            all_pairs.extend(_align_prose_unit(han_lines, pa_lines, dn_lines, phonetic_checks))
        else:
            all_pairs.extend(_align_verse_unit(han_lines, pa_lines, dn_lines, dt_lines, phonetic_checks))

    # Fallback for mock or partial page slices where work boundaries were absent
    if not all_pairs and pages:
        for page in pages:
            layout = page.get("layout", {})
            h_p = list(layout.get("chu_han_lines", [])) or [
                clean_han_text(it.get("text", ""))
                for it in page.get("han_items", [])
                if clean_han_text(it.get("text", ""))
            ]
            pa_p = list(layout.get("phien_am_lines", []))
            dn_p = list(layout.get("dich_nghia_lines", []))
            dt_p = list(layout.get("dich_tho_lines", []))
            if not h_p or (not pa_p and not dn_p and not dt_p):
                continue
            if layout.get("layout_mode") == "sequential_prose":
                all_pairs.extend(_align_prose_unit(h_p, pa_p, dn_p, phonetic_checks))
            else:
                all_pairs.extend(_align_verse_unit(h_p, pa_p, dn_p, dt_p, phonetic_checks))

    if stats_out is not None:
        stats_out["title_rows"] = title_rows_count
    return all_pairs, phonetic_checks


def _write_book_deliverables(
    book_key: str,
    book_cfg: Dict[str, Any],
    pairs: List[Tuple[str, ...]],
    phonetic_checks: List[Dict[str, Any]],
    workspace_root: Path,
    title_rows: int = 0,
) -> Dict[str, Any]:
    """Write `03_text_sach` and `04_dong_hang` files and verify TSV == XLSX."""
    code = book_cfg.get("code") or BOOK_DELIVERABLE_DIRS[book_key]
    clean_dir = workspace_root / book_cfg.get("clean_text_dir", f"deliverables/{code}/03_text_sach")
    align_dir = workspace_root / book_cfg.get("alignment_dir", f"deliverables/{code}/04_dong_hang")
    clean_dir.mkdir(parents=True, exist_ok=True)
    align_dir.mkdir(parents=True, exist_ok=True)

    # Remove stale duplicate short filenames (HVTT_parallel.*, TVLT2_parallel.*, TLTVN_parallel.*)
    for ext in ("tsv", "xlsx"):
        stale_short = align_dir / f"{book_key}_parallel.{ext}"
        canonical_target = align_dir / f"{code}_parallel.{ext}"
        if stale_short != canonical_target and (stale_short.exists() or stale_short.is_symlink()):
            stale_short.unlink()

    han_txt = clean_dir / "han.txt"
    viet_txt = clean_dir / "viet.txt"
    han_lines: List[str] = []
    viet_lines: List[str] = []
    for row in pairs:
        han_lines.append(row[0])
        if len(row) >= 4:
            viet_lines.append(
                row[2] if row[2].strip() else (row[3] if row[3].strip() else row[1])
            )
        else:
            viet_lines.append(row[1])
    han_txt.write_text(("\n".join(han_lines) + "\n") if han_lines else "", encoding="utf-8")
    viet_txt.write_text(("\n".join(viet_lines) + "\n") if viet_lines else "", encoding="utf-8")

    qa_report = validate_pairs(pairs)
    word_cov = batch_evaluate_word_coverage(pairs) if pairs else {}

    tsv_path = align_dir / f"{code}_parallel.tsv"
    xlsx_path = align_dir / f"{code}_parallel.xlsx"
    qa_json_path = align_dir / "qa_report.json"
    cov_json_path = align_dir / "word_coverage_report.json"

    explicit_headers = ("Hán", "Dịch âm", "Dịch nghĩa", "Dịch thơ")
    export_tsv(pairs, str(tsv_path))
    export_xlsx_zero_dep(
        pairs,
        str(xlsx_path),
        headers=explicit_headers,
        stats={
            "Mã tài liệu": code,
            "Tổng số cặp câu": qa_report["total_pairs"],
            "Số dòng tiêu đề": title_rows,
            "Số dòng có Dịch thơ": sum(1 for r in pairs if len(r) >= 4 and r[3].strip()),
            "Số cặp hợp lệ": qa_report["valid_pairs"],
            "Số cặp lỗi": qa_report["error_pairs"],
            "Tỷ lệ lỗi": qa_report["error_rate"],
            "Đạt ngưỡng <= 20%": qa_report["passes_target_20pct"],
            "Đạt ngưỡng nghiệm thu <= 30%": qa_report["passes_threshold_30pct"],
        },
    )
    qa_json_path.write_text(json.dumps(qa_report, ensure_ascii=False, indent=2), encoding="utf-8")
    cov_json_path.write_text(json.dumps(word_cov, ensure_ascii=False, indent=2), encoding="utf-8")

    tsv_roundtrip = read_tsv(str(tsv_path))
    xlsx_roundtrip = read_xlsx_zero_dep(str(xlsx_path), sheet_name="DONG_HANG")
    if tsv_roundtrip != xlsx_roundtrip:
        raise AssertionError(f"TSV vs XLSX mismatch for {code}: {len(tsv_roundtrip)} != {len(xlsx_roundtrip)}")

    dich_tho_populated = sum(1 for r in pairs if len(r) >= 4 and r[3].strip())

    return {
        "book_id": book_key,
        "code": code,
        "pair_count": len(pairs),
        "title_rows": title_rows,
        "dich_tho_populated": dich_tho_populated,
        "missing_count": qa_report["missing_count"],
        "error_rate": qa_report["error_rate"],
        "is_valid": qa_report["is_valid"],
        "avg_han_coverage_pct": word_cov.get("avg_han_coverage_pct", 0.0),
        "avg_confidence": word_cov.get("avg_confidence", 0.0),
        "phonetic_all_matched": all(
            c.get("length_match", True) and len(c.get("phonetic_mismatches", [])) == 0
            for c in phonetic_checks
        ),
        "tsv_xlsx_identical": True,
        "tsv_path": str(tsv_path),
        "xlsx_path": str(xlsx_path),
    }


def run_corpus_from_ocr(
    workspace_root: Path,
    ocr_root: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    book_filter: Optional[str] = None,
    pilot_only: bool = False,
) -> Dict[str, Any]:
    """Run complete alignment, QA, and export reading strictly from `02_ocr_tho` JSON outputs."""
    manifest = load_book_manifest(manifest_path)
    books_cfg = manifest.get("books", {})
    ocr_base = ocr_root or workspace_root

    target_books = [book_filter] if book_filter else ["HVTT", "TVLT2", "TLTVN"]
    summary: Dict[str, Any] = {"books": {}, "source_mode": "ocr_json"}

    for book_key in target_books:
        if book_key not in books_cfg:
            continue
        cfg = books_cfg[book_key]
        code = cfg.get("code") or BOOK_DELIVERABLE_DIRS[book_key]

        candidate_ocr_dir = ocr_base / "deliverables" / code / "02_ocr_tho"
        if not candidate_ocr_dir.is_dir():
            candidate_ocr_dir = ocr_base / "02_ocr_tho"

        summary_meta_file = candidate_ocr_dir / "ocr_run_summary.json"
        if not summary_meta_file.is_file():
            global_summary_file = ocr_base / "02_ocr_tho" / "ocr_run_summary.json"
            if global_summary_file.is_file():
                summary_meta_file = global_summary_file

        is_mock_run = True
        if summary_meta_file.is_file():
            try:
                meta_obj = json.loads(summary_meta_file.read_text(encoding="utf-8"))
                is_mock_run = meta_obj.get("mode", "mock") == "mock"
            except Exception:
                is_mock_run = True
        else:
            han_subdir = candidate_ocr_dir / "han"
            first_han = next(iter(sorted(han_subdir.glob("*.json"))), None) if han_subdir.is_dir() else None
            if first_han is not None:
                try:
                    han_meta = json.loads(first_han.read_text(encoding="utf-8"))
                    engine_name = str(han_meta.get("engine") or "").strip()
                    if engine_name and "mock" not in engine_name.lower():
                        is_mock_run = False
                except Exception:
                    pass

        pages = _load_book_ocr_pages(
            ocr_dir=candidate_ocr_dir,
            book_key=book_key,
            book_cfg=cfg,
            pilot_only=pilot_only,
        )
        pages = _deduplicate_mock_repeats(pages, is_mock_run=is_mock_run)

        align_stats: Dict[str, int] = {}
        if book_key == "HVTT":
            pairs, phonetic_checks = _align_hvtt_from_ocr(pages, stats_out=align_stats)
        else:
            pairs, phonetic_checks = _align_sequential_book_from_ocr(
                book_key=book_key,
                pages=pages,
                workspace_root=workspace_root,
                stats_out=align_stats,
            )

        book_summary = _write_book_deliverables(
            book_key=book_key,
            book_cfg=cfg,
            pairs=pairs,
            phonetic_checks=phonetic_checks,
            workspace_root=workspace_root,
            title_rows=align_stats.get("title_rows", 0),
        )
        book_summary["ocr_pages_loaded"] = len(pages)
        book_summary["ocr_mode"] = "mock" if is_mock_run else "kaggle_gpu"
        summary["books"][book_key] = book_summary

    summary["total_pairs"] = sum(b["pair_count"] for b in summary["books"].values())
    return summary
