#!/usr/bin/env python3
"""Dual-Engine OCR & Layout Preprocessing Pipeline for Hán-Việt Parallel Corpus.

Designed to run both:
1. On Kaggle GPU (`PaddleOCR` `chinese_cht` + `VietOCR` `vgg_transformer` + `cv2`), and
2. Locally in `--dry-run` / `--mock` mode (or imported in unit tests) using pure Python 3
   without requiring GPU packages installed locally.

Implements:
- Top 7% running header crop (`THƠ VĂN LÝ - TRẦN`, page numbers, book headers).
- Horizontal footnote separator line detection in the lower half of the page (for `TLTVN`
  *Thể loại từ Việt Nam thời trung đại*) to crop out footnotes before OCR.
- Book-specific layout grouping:
  * `HVTT` (*Hán Văn Tinh Túy*): 3-line interlinear blocks on even pages (`Chữ Hán`,
    `Phiên âm`, `Dịch nghĩa` gloss) + bottom `Dịch nghĩa` block; odd pages flagged as commentary.
  * `TLTVN` (*Thể loại từ VN thời trung đại*): sequential `Chữ Hán` -> `Phiên âm:` ->
    `Dịch nghĩa:` blocks.
  * `TVLT2` (*Thơ văn Lý – Trần Tập II*): 2-column side-by-side poetry (`Chữ Hán` left,
    `Phiên âm` right, `DỊCH NGHĨA :` below) or sequential prose blocks, stopping at
    `DỊCH THƠ :`, `KHẢO ĐÍNH :`, or `CHÚ THÍCH :`.
- Raw OCR traceability output saved per page into `02_ocr_tho/han/<page>.json` and
  `02_ocr_tho/viet/<page>.json` preserving bounding boxes and raw text (Guideline Step 4).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

# Optional imports for GPU / OpenCV runtime (gracefully fallback when running locally)
try:
    import cv2  # type: ignore
except ImportError:
    cv2 = None  # type: ignore

try:
    import numpy as np  # type: ignore
except ImportError:
    np = None  # type: ignore

try:
    from PIL import Image  # type: ignore
except ImportError:
    Image = None  # type: ignore


# Supported book types and default configuration
BOOK_TYPES = ("HVTT", "TLTVN", "TVLT2")
BOOK_ALIAS_TO_LAYOUT: Dict[str, str] = {
    "VPO_01": "HVTT",
    "CV04_VPO_01": "HVTT",
    "HVTT": "HVTT",
    "VPO_02": "TLTVN",
    "CV04_VPO_02": "TLTVN",
    "TLTVN": "TLTVN",
    "VPO_03": "TVLT2",
    "CV04_VPO_03": "TVLT2",
    "TVLT2": "TVLT2",
}
BOOK_DELIVERABLE_DIRS: Dict[str, str] = {
    "HVTT": "CV04_VPO_01",
    "TLTVN": "CV04_VPO_02",
    "TVLT2": "CV04_VPO_03",
    "VPO_01": "CV04_VPO_01",
    "VPO_02": "CV04_VPO_02",
    "VPO_03": "CV04_VPO_03",
}
DELIVERABLE_DIR_TO_BOOK: Dict[str, str] = {
    "CV04_VPO_01": "HVTT",
    "CV04_VPO_02": "TLTVN",
    "CV04_VPO_03": "TVLT2",
    "HVTT_HANVANTINHTUY": "HVTT",
    "TLTVN_THELOAITUVN": "TLTVN",
    "TVLT2_THOVANLYTRAN2": "TVLT2",
}
DEFAULT_HEADER_CROP_RATIO = 0.07
DEFAULT_LOWER_HALF_START_RATIO = 0.50
DEFAULT_FOOTNOTE_MAX_Y_RATIO = 0.94
DEFAULT_MIN_SEPARATOR_WIDTH_RATIO = 0.15

# Regex patterns for section headers in TVLT2 / TLTVN / HVTT
_STOP_HEADER_RE = re.compile(
    r"^\s*(?:KHẢO\s*ĐÍNH|Khảo\s*đính|VĂN\s*BẢN\s*KHẢO\s*ĐÍNH|Văn\s*bản\s*khảo\s*đính|"
    r"CÁC\s*DỊ\s*BẢN|Các\s*dị\s*bản|CHÚ\s*:?\s*THÍCH|Chú\s*:?\s*thích|"
    r"CÁC\s*THÍCH|Các\s*thích|LỜI\s*BÀN|Lời\s*bàn|BÌNH\s*CHÚ|Bình\s*chú)\b\s*[:：.]?",
    flags=re.IGNORECASE,
)
_DICH_THO_HEADER_RE = re.compile(
    r"^\s*(?:DỊCH\s*THƠ|Dịch\s*thơ|DỊCH\s*THEO\s*NGUYÊN\s*ĐIỆU|Dịch\s*theo\s*nguyên\s*điệu)\s*[:：.]?\s*(.*)$",
    flags=re.IGNORECASE,
)
_PHIEN_AM_HEADER_RE = re.compile(
    r"^\s*(?:PHIÊN\s*ÂM|Phiên\s*âm)\s*[:：.]?\s*(.*)$",
    flags=re.IGNORECASE,
)
_DICH_NGHIA_HEADER_RE = re.compile(
    r"^\s*(?:DỊCH\s*NGHĨA|Dịch\s*nghĩa|DỊCH\s*XUÔI|Dịch\s*xuôi)\s*[:：.]?\s*(.*)$",
    flags=re.IGNORECASE,
)

# Diacritic-folded regexes to tolerate noisy OCR section headers
_FOLDED_STOP_HEADER_RE = re.compile(
    r"^\s*(?:KHAO\s*(?:DINH|HINH|DI)|KI\s*AO\s*DINH|VAN\s*BAN\s*KHAO|CAC\s*DI\s*BAN|"
    r"CHU\s*:?\s*TH[IA]CH|[CG][HI]U\s*TH[IA]CH|CAC\s*THICH|LOI\s*BAN|BINH\s*CHU)\b\s*[:：.]?\s*(.*)$",
    flags=re.IGNORECASE,
)
_FOLDED_DICH_THO_HEADER_RE = re.compile(
    r"^\s*DI[CG]H\s*(?:TH[O0G]|TR[OY]|THEO\s*NGUYEN\s*DIEU)\b\s*[:：.]?\s*(.*)$",
    flags=re.IGNORECASE,
)
_FOLDED_PHIEN_AM_HEADER_RE = re.compile(
    r"^\s*PH[I1]EN\s*(?:AM|ANH)\b\s*[:：.]?\s*(.*)$",
    flags=re.IGNORECASE,
)
_FOLDED_DICH_NGHIA_HEADER_RE = re.compile(
    r"^\s*D[I1]CH\s*(?:NGH[I1]A|NG[I1]TA|XU[O0][I1])\b\s*[:：.]?\s*(.*)$",
    flags=re.IGNORECASE,
)
_FOLDED_TIEU_DAN_RE = re.compile(r"^\s*TIEU[\s\-]*(?:DAN|TRUYEN)\b", flags=re.IGNORECASE)
_HVTT_RUNNING_HEADER_RE = re.compile(r"HAN[\s\-]*VAN\s+TINH[\s\-]*TUY", flags=re.IGNORECASE)
_PAGE_NUM_RE = re.compile(r"^\d{1,3}$")
_TLTVN_NUMBERED_FOOTNOTE_RE = re.compile(r"^\d{1,2}\s+[A-Z\u00C0-\u024F\u1E00-\u1EFF]")

# CJK & Latin detection regexes for distinguishing Han lines from Vietnamese lines
_CJK_CHAR_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_LATIN_CHAR_RE = re.compile(r"[A-Za-z\u00C0-\u024F\u1E00-\u1EFF]")


def _fold_ascii_header(text: str) -> str:
    """Fold Vietnamese diacritics (including `đ`/`Đ`) to ASCII for tolerant header matching."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", stripped).strip()


def _count_cjk_and_latin(text: str) -> Tuple[int, int]:
    """Return `(cjk_char_count, latin_char_count)` for a text line."""
    if not text:
        return (0, 0)
    return len(_CJK_CHAR_RE.findall(text)), len(_LATIN_CHAR_RE.findall(text))


def _is_primary_han_line(text: str) -> bool:
    """Return True if a line is predominantly Classical Chinese rather than Vietnamese prose with inline CJK."""
    cjk_cnt, latin_cnt = _count_cjk_and_latin(text)
    return cjk_cnt >= 1 and (latin_cnt == 0 or cjk_cnt >= latin_cnt)


def _is_hvtt_running_header(text: str, y1: float) -> bool:
    """Return True if an HVTT OCR line is a running page title or page number at the top margin."""
    folded = _fold_ascii_header(text)
    if not folded:
        return True
    if _HVTT_RUNNING_HEADER_RE.search(folded):
        return True
    if y1 < 90.0 and _PAGE_NUM_RE.match(folded):
        return True
    return False


# ---------------------------------------------------------------------------
# Image Preprocessing: Header Cropping & Footnote Separator Detection
# ---------------------------------------------------------------------------


def get_image_dimensions(image: Any) -> Tuple[int, int]:
    """Return `(height, width)` of `image` (supports numpy array, PIL Image, 2D list, or dict)."""
    if image is None:
        return (0, 0)
    if isinstance(image, dict):
        return int(image.get("height", 0)), int(image.get("width", 0))
    if hasattr(image, "shape") and len(image.shape) >= 2:
        return int(image.shape[0]), int(image.shape[1])
    if hasattr(image, "size") and isinstance(image.size, tuple) and len(image.size) == 2:
        # PIL Image.size is (width, height)
        return int(image.size[1]), int(image.size[0])
    if isinstance(image, (list, tuple)) and len(image) > 0 and isinstance(image[0], (list, tuple)):
        return len(image), len(image[0])
    return (0, 0)


def slice_image_vertical(image: Any, y_start: int, y_end: Optional[int] = None) -> Any:
    """Vertically slice `image[y_start:y_end]` across numpy, PIL, 2D list, or metadata dict."""
    height, width = get_image_dimensions(image)
    if height == 0:
        return image
    y0 = max(0, min(height, int(y_start)))
    y1 = height if y_end is None else max(y0, min(height, int(y_end)))

    if isinstance(image, dict):
        updated = dict(image)
        updated["height"] = y1 - y0
        updated["crop_y_offset"] = int(image.get("crop_y_offset", 0)) + y0
        return updated
    if hasattr(image, "shape"):
        return image[y0:y1]
    if hasattr(image, "crop") and hasattr(image, "size"):
        return image.crop((0, y0, width, y1))
    if isinstance(image, list):
        return image[y0:y1]
    return image


def crop_running_header(
    image: Any,
    header_ratio: float = DEFAULT_HEADER_CROP_RATIO,
) -> Tuple[Any, int]:
    """Crop the top `header_ratio` (default 7%) running header (`THƠ VĂN LÝ - TRẦN`, page numbers).

    Args:
        image: Page image (numpy array, PIL Image, 2D pixel list, or metadata dict).
        header_ratio: Fraction of page height to crop from the top (default `0.07`).

    Returns:
        Tuple `(cropped_image, crop_top_px)` where `crop_top_px` is the number of pixels
        removed from the top of the page.
    """
    height, _width = get_image_dimensions(image)
    if height <= 0 or header_ratio <= 0.0:
        return image, 0
    crop_top_px = int(round(height * header_ratio))
    cropped = slice_image_vertical(image, crop_top_px, height)
    return cropped, crop_top_px


def _longest_dark_run_in_row(row_pixels: Sequence[Any], dark_threshold: int = 180) -> int:
    """Compute the longest contiguous horizontal run of dark pixels (`< dark_threshold`) in a row."""
    best_run = 0
    current_run = 0
    for px in row_pixels:
        if isinstance(px, (list, tuple)):
            val = sum(px[:3]) / max(1, min(3, len(px)))
        else:
            val = float(px)
        if val < dark_threshold:
            current_run += 1
            if current_run > best_run:
                best_run = current_run
        else:
            current_run = 0
    return best_run


def detect_footnote_separator(
    image: Any,
    lower_half_start: float = DEFAULT_LOWER_HALF_START_RATIO,
    max_y_ratio: float = DEFAULT_FOOTNOTE_MAX_Y_RATIO,
    min_line_width_ratio: float = DEFAULT_MIN_SEPARATOR_WIDTH_RATIO,
    dark_threshold: int = 180,
) -> Optional[int]:
    """Detect the horizontal footnote separator rule in the lower half of a page image.

    Used especially for *Thể loại từ Việt Nam thời trung đại* (`TLTVN`), where footnotes
    at the bottom of the page are separated from the main text by a thin horizontal line.

    Args:
        image: Page image (already header-cropped or full page).
        lower_half_start: Minimum vertical fraction (`0.50` = lower half) to begin searching.
        max_y_ratio: Maximum vertical fraction (`0.94`) to avoid page-bottom scan borders.
        min_line_width_ratio: Minimum contiguous horizontal dark line length as a fraction
            of page width (default `0.15`).
        dark_threshold: Grayscale pixel intensity threshold (`0..255`) for dark ink.

    Returns:
        Y-coordinate (row index in `image`) of the detected horizontal separator line,
        or `None` if no separator line is present.
    """
    if isinstance(image, dict):
        sep = image.get("footnote_separator_y")
        return int(sep) if sep is not None else None

    height, width = get_image_dimensions(image)
    if height < 10 or width < 10:
        return None

    y_min = max(0, int(height * lower_half_start))
    y_max = min(height, int(height * max_y_ratio))
    if y_min >= y_max:
        return None

    min_run_px = max(8, int(round(width * min_line_width_ratio)))

    # Convert PIL Image to NumPy array when NumPy is available for 100x faster scanning
    if np is not None and hasattr(image, "convert") and not hasattr(image, "shape"):
        image = np.asarray(image.convert("L"))

    # Fast path with OpenCV / NumPy when available
    if np is not None and hasattr(image, "shape"):
        arr = image
        if len(arr.shape) == 3:
            if cv2 is not None:
                gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
            else:
                gray = arr[:, :, :3].mean(axis=2)
        else:
            gray = arr

        roi = gray[y_min:y_max, :]
        binary = (roi < dark_threshold).astype(np.uint8)

        if cv2 is not None:
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_run_px, 1))
            horiz = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
            row_counts = horiz.sum(axis=1)
            candidate_rows = np.where(row_counts >= min_run_px)[0]
            if len(candidate_rows) > 0:
                return int(y_min + candidate_rows[0])

        # Pure NumPy row scan fallback
        for r_idx in range(binary.shape[0]):
            row = binary[r_idx]
            if int(row.sum()) < min_run_px:
                continue
            # Compute longest contiguous run of 1s in row
            padded = np.concatenate(([0], row, [0]))
            diffs = np.diff(padded)
            starts = np.where(diffs == 1)[0]
            ends = np.where(diffs == -1)[0]
            if len(starts) > 0 and int((ends - starts).max()) >= min_run_px:
                return int(y_min + r_idx)
        return None

    # Pure Python fallback for PIL Image or 2D list
    if hasattr(image, "convert") and hasattr(image, "load"):
        gray_img = image.convert("L")
        px_access = gray_img.load()
        for y in range(y_min, y_max):
            row_vals = [px_access[x, y] for x in range(width)]
            if _longest_dark_run_in_row(row_vals, dark_threshold) >= min_run_px:
                return y
        return None

    if isinstance(image, (list, tuple)):
        for y in range(y_min, y_max):
            if _longest_dark_run_in_row(image[y], dark_threshold) >= min_run_px:
                return y

    return None


def preprocess_page_image(
    image: Any,
    book_type: str = "TVLT2",
    header_ratio: float = DEFAULT_HEADER_CROP_RATIO,
    detect_footnotes: Optional[bool] = None,
) -> Tuple[Any, Dict[str, Any]]:
    """Preprocess a page image before OCR: crop top 7% header and footnote region if present.

    Args:
        image: Input page image (numpy array, PIL Image, 2D list, or metadata dict).
        book_type: Book identifier (`"HVTT"`, `"TLTVN"`, or `"TVLT2"`).
        header_ratio: Top running-header crop ratio (default `0.07`).
        detect_footnotes: Whether to detect and crop at the horizontal footnote separator
            line in the lower half of the page. Defaults to True for `"TLTVN"`, False otherwise.

    Returns:
        Tuple `(processed_image, metadata)` with full coordinate traceability.
    """
    book_key = BOOK_ALIAS_TO_LAYOUT.get(book_type.upper().strip(), book_type.upper().strip())
    orig_h, orig_w = get_image_dimensions(image)

    cropped_img, crop_top_px = crop_running_header(image, header_ratio=header_ratio)
    after_header_h, _ = get_image_dimensions(cropped_img)

    should_detect_fn = (book_key == "TLTVN") if detect_footnotes is None else bool(detect_footnotes)
    separator_y_cropped: Optional[int] = None
    separator_y_original: Optional[int] = None

    if should_detect_fn and after_header_h > 0:
        separator_y_cropped = detect_footnote_separator(cropped_img, lower_half_start=0.20)
        if separator_y_cropped is not None:
            separator_y_original = crop_top_px + separator_y_cropped
            cropped_img = slice_image_vertical(cropped_img, 0, separator_y_cropped)

    eff_h, eff_w = get_image_dimensions(cropped_img)

    meta: Dict[str, Any] = {
        "book_type": book_key,
        "original_width": orig_w,
        "original_height": orig_h,
        "crop_top_px": crop_top_px,
        "header_ratio": header_ratio,
        "footnote_separator_y_cropped": separator_y_cropped,
        "footnote_separator_y_original": separator_y_original,
        "effective_width": eff_w,
        "effective_height": eff_h,
    }
    return cropped_img, meta


# ---------------------------------------------------------------------------
# Layout Grouping & Section Boundary Detection (HVTT, TLTVN, TVLT2)
# ---------------------------------------------------------------------------


def is_stop_section_header(text: str) -> bool:
    """Return True if `text` starts a true apparatus/stop section (`KHẢO ĐÍNH :`, `CHÚ THÍCH :`, etc.)."""
    if not text:
        return False
    folded = _fold_ascii_header(text)
    return bool(_STOP_HEADER_RE.match(unicodedata.normalize("NFC", text.strip())) or _FOLDED_STOP_HEADER_RE.match(folded))


def _extract_header_remainder(text: str, folded_pattern: re.Pattern[str]) -> Tuple[bool, str]:
    """Match a folded header regex and return `(matched, original_unicode_remainder)`."""
    if not text:
        return (False, "")
    nfc = unicodedata.normalize("NFC", text.strip())
    folded = _fold_ascii_header(nfc)
    m = folded_pattern.match(folded)
    if not m:
        return (False, "")
    rest_folded = m.group(1).strip() if m.lastindex and m.lastindex >= 1 else ""
    if not rest_folded:
        return (True, "")
    if len(folded) == len(nfc):
        return (True, nfc[m.start(1):].strip())
    for sep in (":", "：", "."):
        if sep in nfc:
            return (True, nfc.split(sep, 1)[1].strip())
    return (True, rest_folded)


def classify_section_header(text: str) -> Optional[str]:
    """Classify a line as `'stop'`, `'dich_tho'`, `'phien_am'`, `'dich_nghia'`, or `None`."""
    if not text:
        return None
    nfc = unicodedata.normalize("NFC", text.strip())
    folded = _fold_ascii_header(nfc)
    if is_stop_section_header(nfc):
        return "stop"
    if _DICH_THO_HEADER_RE.match(nfc) or _FOLDED_DICH_THO_HEADER_RE.match(folded):
        return "dich_tho"
    if _PHIEN_AM_HEADER_RE.match(nfc) or _FOLDED_PHIEN_AM_HEADER_RE.match(folded):
        return "phien_am"
    if _DICH_NGHIA_HEADER_RE.match(nfc) or _FOLDED_DICH_NGHIA_HEADER_RE.match(folded):
        return "dich_nghia"
    return None


def _word_count(text: str) -> int:
    """Count lexical word tokens in `text`, ignoring standalone punctuation like `'-'`."""
    if not text:
        return 0
    return sum(1 for tok in unicodedata.normalize("NFC", text).split() if any(ch.isalnum() for ch in tok))


def deduplicate_overlapping_items(
    items: Sequence[Dict[str, Any]],
    y_threshold: float = 12.0,
) -> List[Dict[str, Any]]:
    """Drop duplicate overlapping OCR boxes that share normalized text within `|dy| < y_threshold`."""
    kept: List[Tuple[str, float, float, float, float, float, int, Dict[str, Any]]] = []
    for idx, item in enumerate(items):
        raw_text = unicodedata.normalize("NFC", str(item.get("text", "")))
        norm_text = " ".join(raw_text.split())
        if not norm_text:
            continue
        x1, y1, x2, y2 = _box_bounds(item)
        yc = 0.5 * (y1 + y2)
        conf = float(item.get("confidence", 0.0) or 0.0)

        dup_idx: Optional[int] = None
        for k_idx, (k_txt, k_x1, k_y1, k_x2, _k_y2, k_yc, _k_conf, _k_item) in enumerate(kept):
            if k_txt != norm_text:
                continue
            if abs(y1 - k_y1) >= y_threshold and abs(yc - k_yc) >= y_threshold:
                continue
            x_overlaps = min(x2, k_x2) > max(x1, k_x1) - 20.0
            if x_overlaps or abs(x1 - k_x1) < 60.0:
                dup_idx = k_idx
                break

        if dup_idx is None:
            kept.append((norm_text, x1, y1, x2, y2, yc, conf, item))
        else:
            prev = kept[dup_idx]
            prev_w = prev[3] - prev[1]
            cur_w = x2 - x1
            if (conf, cur_w) > (prev[6], prev_w):
                kept[dup_idx] = (norm_text, x1, y1, x2, y2, yc, conf, item)
    return [entry[7] for entry in kept]


def _box_bounds(item: Dict[str, Any]) -> Tuple[float, float, float, float]:
    """Return `(x1, y1, x2, y2)` from an OCR item dict."""
    if "box_xyxy" in item and len(item["box_xyxy"]) == 4:
        x1, y1, x2, y2 = item["box_xyxy"]
        return float(x1), float(y1), float(x2), float(y2)
    bbox = item.get("bbox", [[0, 0], [0, 0], [0, 0], [0, 0]])
    xs = [ float(pt[0]) for pt in bbox ]
    ys = [ float(pt[1]) for pt in bbox ]
    return min(xs), min(ys), max(xs), max(ys)


def _sort_items_reading_order(items: Sequence[Dict[str, Any]], y_tolerance: float = 18.0) -> List[Dict[str, Any]]:
    """Sort OCR bounding-box items top-to-bottom, then left-to-right within the same line band."""
    annotated = []
    for item in items:
        x1, y1, x2, y2 = _box_bounds(item)
        y_center = 0.5 * (y1 + y2)
        x_center = 0.5 * (x1 + x2)
        annotated.append((y_center, x_center, item))
    annotated.sort(key=lambda t: (round(t[0] / max(1.0, y_tolerance)), t[1]))
    return [t[2] for t in annotated]


def group_layout_blocks(
    han_items: Sequence[Dict[str, Any]],
    viet_items: Sequence[Dict[str, Any]],
    book_type: str,
    page_num: int = 2,
    page_width: int = 2000,
) -> Dict[str, Any]:
    """Group OCR items into structured `Chữ Hán`, `Phiên âm`, `Dịch nghĩa`, and `Dịch thơ` blocks.

    Book Rules:
    - `HVTT` (*Hán Văn Tinh Túy*):
      * Odd pages (`page_num % 2 == 1`):
        - Title pages (containing primary Han title): extract `title_block` (`odd_title_page`).
        - Facing verse pages without Han: strip 2-item top running header and collect
          `dich_tho_lines` + `dich_tho_y_centers` (`odd_page_dich_tho`), unless full-width
          biography prose (`odd_page_bio_prose_skipped`).
      * Even pages (`page_num % 2 == 0`):
        - Skip pages with no primary Han (`even_page_non_han_skipped`).
        - Otherwise strip top running header and group 3-line interlinear triplets, merging
          wrapped 2-line `Phiên âm` in vertical bands and flagging `has_dich_nghia`.
    - `TLTVN` (*Thể loại từ VN thời trung đại*):
      * Sequential blocks: `Chữ Hán` -> `Phiên âm:` -> `Dịch nghĩa:` -> `Dịch thơ:`, stopping
        only at numbered footnotes or true apparatus headers (`KHẢO ĐÍNH`, `CHÚ THÍCH`, etc.).
    - `TVLT2` (*Thơ văn Lý – Trần Tập II*):
      * Supports 2-column side-by-side poetry or sequential prose, extracting `DỊCH THƠ :`
        into `dich_tho_lines` and stopping only at true apparatus headers (`KHẢO ĐÍNH`, `CHÚ THÍCH`).
    """
    book_key = BOOK_ALIAS_TO_LAYOUT.get(book_type.upper().strip(), book_type.upper().strip())
    sorted_han = deduplicate_overlapping_items(_sort_items_reading_order(han_items))
    sorted_viet = deduplicate_overlapping_items(_sort_items_reading_order(viet_items))

    # 1. HVTT: odd title/bio/facing-verse pages + even 3-line interlinear pages
    if book_key == "HVTT":
        han_nodes = [
            it for it in sorted_han
            if _is_primary_han_line(it.get("text", ""))
        ]

        if page_num % 2 != 0:
            # Odd title page: centered Han title + Phiên âm + Dịch nghĩa before TIỂU-DẪN
            if han_nodes:
                title_han_node = han_nodes[0]
                title_chu_han = unicodedata.normalize("NFC", title_han_node.get("text", "").strip())
                _, han_y1, _, han_y2 = _box_bounds(title_han_node)
                stop_han_y1: Optional[float] = _box_bounds(han_nodes[1])[1] if len(han_nodes) > 1 else None

                title_phien_am = ""
                title_dn_parts: List[str] = []
                for it in sorted_viet:
                    txt = unicodedata.normalize("NFC", it.get("text", "").strip())
                    if not txt or _is_primary_han_line(txt):
                        continue
                    v_x1, v_y1, _, _ = _box_bounds(it)
                    if _is_hvtt_running_header(txt, v_y1):
                        continue
                    if v_y1 <= han_y1:
                        continue
                    if stop_han_y1 is not None and v_y1 >= stop_han_y1:
                        break
                    folded = _fold_ascii_header(txt)
                    if _FOLDED_TIEU_DAN_RE.match(folded):
                        break
                    if v_x1 >= 0.54 * float(page_width):
                        continue
                    if not title_phien_am:
                        if v_y1 - han_y2 <= 70.0:
                            title_phien_am = txt
                    else:
                        title_dn_parts.append(txt)

                return {
                    "book_type": "HVTT",
                    "page_num": page_num,
                    "layout_mode": "odd_title_page",
                    "title_block": {
                        "chu_han": title_chu_han,
                        "phien_am": title_phien_am,
                        "dich_nghia": " ".join(title_dn_parts).strip(),
                    },
                    "interlinear_triplets": [],
                    "chu_han_lines": [],
                    "phien_am_lines": [],
                    "dich_nghia_lines": [],
                    "dich_tho_lines": [],
                    "dich_tho_y_centers": [],
                }

            # Odd non-title page without Han: strip 2-item top running header pair band
            viet_odd_source = list(sorted_viet)
            if len(viet_odd_source) >= 2:
                v0_x1, v0_y1, _, _ = _box_bounds(viet_odd_source[0])
                v1_x1, v1_y1, _, _ = _box_bounds(viet_odd_source[1])
                if abs(v0_y1 - v1_y1) <= 25.0 and (
                    (v0_x1 < 0.22 * float(page_width) and v1_x1 >= 0.75 * float(page_width))
                    or (v1_x1 < 0.22 * float(page_width) and v0_x1 >= 0.75 * float(page_width))
                ):
                    viet_odd_source = viet_odd_source[2:]

            has_explicit_dich_tho = any(
                _extract_header_remainder(
                    unicodedata.normalize("NFC", it.get("text", "").strip()),
                    _FOLDED_DICH_THO_HEADER_RE,
                )[0]
                or it.get("role", "") == "dich_tho"
                for it in viet_odd_source
            )

            dich_tho_lines: List[str] = []
            dich_tho_y_centers: List[float] = []
            if has_explicit_dich_tho:
                in_dich_tho = False
                for it in viet_odd_source:
                    txt = unicodedata.normalize("NFC", it.get("text", "").strip())
                    _, y1, _, y2 = _box_bounds(it)
                    if not txt or _is_primary_han_line(txt) or _is_hvtt_running_header(txt, y1):
                        continue
                    is_dt_hdr, dt_rest = _extract_header_remainder(txt, _FOLDED_DICH_THO_HEADER_RE)
                    if is_dt_hdr:
                        in_dich_tho = True
                        if dt_rest:
                            dich_tho_lines.append(dt_rest)
                            dich_tho_y_centers.append(0.5 * (y1 + y2))
                        continue
                    if is_stop_section_header(txt):
                        in_dich_tho = False
                        continue
                    if in_dich_tho or it.get("role", "") == "dich_tho":
                        dich_tho_lines.append(txt)
                        dich_tho_y_centers.append(0.5 * (y1 + y2))

                return {
                    "book_type": "HVTT",
                    "page_num": page_num,
                    "layout_mode": "odd_page_dich_tho",
                    "interlinear_triplets": [],
                    "chu_han_lines": [],
                    "phien_am_lines": [],
                    "dich_nghia_lines": [],
                    "dich_tho_lines": dich_tho_lines,
                    "dich_tho_y_centers": dich_tho_y_centers,
                }

            body_entries: List[Tuple[Dict[str, Any], str, float]] = []
            for it in viet_odd_source:
                txt = unicodedata.normalize("NFC", it.get("text", "").strip())
                _, y1, _, y2 = _box_bounds(it)
                if not txt or _is_primary_han_line(txt) or _is_hvtt_running_header(txt, y1):
                    continue
                if is_stop_section_header(txt):
                    break
                body_entries.append((it, txt, 0.5 * (y1 + y2)))

            if body_entries:
                x1s = [_box_bounds(it)[0] for it, _, _ in body_entries]
                x2s = [_box_bounds(it)[2] for it, _, _ in body_entries]
                has_real_coords = any(x2 > 0.0 for x2 in x2s)
                if (
                    has_real_coords
                    and len(body_entries) >= 12
                    and statistics.median(x1s) < 0.20 * float(page_width)
                    and max(x2s) > 0.80 * float(page_width)
                ):
                    return {
                        "book_type": "HVTT",
                        "page_num": page_num,
                        "layout_mode": "odd_page_bio_prose_skipped",
                        "interlinear_triplets": [],
                        "chu_han_lines": [],
                        "phien_am_lines": [],
                        "dich_nghia_lines": [],
                        "dich_tho_lines": [],
                        "dich_tho_y_centers": [],
                    }

            return {
                "book_type": "HVTT",
                "page_num": page_num,
                "layout_mode": "odd_page_dich_tho" if body_entries else "odd_page_commentary_skipped",
                "interlinear_triplets": [],
                "chu_han_lines": [],
                "phien_am_lines": [],
                "dich_nghia_lines": [],
                "dich_tho_lines": [txt for _, txt, _ in body_entries],
                "dich_tho_y_centers": [yc for _, _, yc in body_entries],
            }

        # Even HVTT page
        if not han_nodes:
            return {
                "book_type": "HVTT",
                "page_num": page_num,
                "layout_mode": "even_page_non_han_skipped",
                "interlinear_triplets": [],
                "chu_han_lines": [],
                "phien_am_lines": [],
                "dich_nghia_lines": [],
                "dich_tho_lines": [],
                "has_dich_nghia": False,
            }

        han_lines = [unicodedata.normalize("NFC", it.get("text", "").strip()) for it in han_nodes]
        han_y_centers = [0.5 * (_box_bounds(it)[1] + _box_bounds(it)[3]) for it in han_nodes]
        han_y1_min = _box_bounds(han_nodes[0])[1]
        has_real_boxes = bool(han_nodes) and any(_box_bounds(h)[3] > 0.0 for h in han_nodes)
        has_explicit_roles = any(
            it.get("role") in ("phien_am", "dich_nghia_gloss", "dich_tho")
            for it in sorted_viet
        )
        use_vertical_bands = has_real_boxes and not has_explicit_roles

        # Strip top 2-item even-page running header pair band above the first Han line
        viet_even_source = list(sorted_viet)
        if has_real_boxes and len(viet_even_source) >= 2:
            v0_x1, v0_y1, _, v0_y2 = _box_bounds(viet_even_source[0])
            v1_x1, v1_y1, _, v1_y2 = _box_bounds(viet_even_source[1])
            if (
                abs(v0_y1 - v1_y1) <= 25.0
                and max(v0_y2, v1_y2) < han_y1_min - 5.0
                and (
                    (v0_x1 < 0.22 * float(page_width) and v1_x1 >= 0.50 * float(page_width))
                    or (v1_x1 < 0.22 * float(page_width) and v0_x1 >= 0.50 * float(page_width))
                )
            ):
                viet_even_source = viet_even_source[2:]

        phien_am_lines: List[str] = []
        gloss_lines: List[str] = []
        bottom_dich_nghia: List[str] = []
        dich_tho_lines = []
        band_items: List[List[Tuple[Dict[str, Any], str]]] = [[] for _ in han_nodes]
        in_bottom_dich_nghia = False
        in_dich_tho = False
        is_final_no_dich_nghia_page = page_num >= 367

        for it in viet_even_source:
            txt = unicodedata.normalize("NFC", it.get("text", "").strip())
            _, y1, _, y2 = _box_bounds(it)
            if not txt or _is_primary_han_line(txt) or _is_hvtt_running_header(txt, y1):
                continue
            is_dt_hdr, dt_rest = _extract_header_remainder(txt, _FOLDED_DICH_THO_HEADER_RE)
            if is_dt_hdr:
                in_dich_tho = True
                in_bottom_dich_nghia = False
                if dt_rest:
                    dich_tho_lines.append(dt_rest)
                continue
            if is_stop_section_header(txt):
                break
            is_dn_hdr, dn_rest = _extract_header_remainder(txt, _FOLDED_DICH_NGHIA_HEADER_RE)
            if is_dn_hdr:
                in_bottom_dich_nghia = True
                in_dich_tho = False
                if dn_rest and not is_final_no_dich_nghia_page:
                    bottom_dich_nghia.append(dn_rest)
                continue

            role = it.get("role", "")
            if in_dich_tho or role == "dich_tho":
                dich_tho_lines.append(txt)
            elif in_bottom_dich_nghia:
                if not is_final_no_dich_nghia_page:
                    bottom_dich_nghia.append(txt)
            elif use_vertical_bands:
                y_center = 0.5 * (y1 + y2)
                if y_center < han_y_centers[0] - 5.0:
                    continue
                band_idx = 0
                for cand_idx, h_yc in enumerate(han_y_centers):
                    if y_center >= h_yc - 5.0:
                        band_idx = cand_idx
                band_items[band_idx].append((it, txt))
            else:
                if role == "phien_am":
                    phien_am_lines.append(txt)
                elif role == "dich_nghia_gloss":
                    if not is_final_no_dich_nghia_page:
                        gloss_lines.append(txt)
                else:
                    if is_final_no_dich_nghia_page:
                        phien_am_lines.append(txt)
                    elif len(phien_am_lines) <= len(gloss_lines) and len(phien_am_lines) < len(han_lines):
                        phien_am_lines.append(txt)
                    elif len(gloss_lines) < len(phien_am_lines):
                        gloss_lines.append(txt)
                    else:
                        bottom_dich_nghia.append(txt)

        no_gloss_by_bands = (
            use_vertical_bands
            and len(band_items) > 0
            and sum(1 for b in band_items if len(b) == 1) >= 0.8 * len(band_items)
        )
        has_dich_nghia = not (is_final_no_dich_nghia_page or no_gloss_by_bands)

        if use_vertical_bands:
            phien_am_lines = []
            gloss_lines = []
            for b_idx, b in enumerate(band_items):
                if not b:
                    phien_am_lines.append("")
                    gloss_lines.append("")
                    continue
                pa_txt = b[0][1]
                gl_items = b[1:]
                if len(b) >= 3:
                    l0_x1, _, l0_x2, _ = _box_bounds(b[0][0])
                    l1_x1, _, _, _ = _box_bounds(b[1][0])
                    l2_x1, _, _, _ = _box_bounds(b[2][0])
                    han_char_count = _count_cjk_and_latin(han_lines[b_idx])[0]
                    w0 = _word_count(b[0][1])
                    w1 = _word_count(b[1][1])
                    if (
                        l0_x2 >= 0.80 * float(page_width)
                        and w1 <= 5
                        and (
                            (l1_x1 <= l0_x1 - 18.0 and l1_x1 <= l2_x1 - 18.0)
                            or (l1_x1 <= l2_x1 - 18.0 and w0 < han_char_count)
                        )
                    ):
                        pa_txt = f"{b[0][1]} {b[1][1]}".strip()
                        gl_items = b[2:]
                phien_am_lines.append(pa_txt)
                gloss_lines.append("" if not has_dich_nghia else " ".join(txt for _it, txt in gl_items))

        triplets = []
        for idx, h_line in enumerate(han_lines):
            pa_line = phien_am_lines[idx] if idx < len(phien_am_lines) else ""
            gl_line = "" if not has_dich_nghia else (gloss_lines[idx] if idx < len(gloss_lines) else "")
            triplets.append({
                "triplet_index": idx,
                "chu_han": h_line,
                "phien_am": pa_line,
                "dich_nghia_gloss": gl_line,
            })

        return {
            "book_type": "HVTT",
            "page_num": page_num,
            "layout_mode": "interlinear_3line_even_page",
            "interlinear_triplets": triplets,
            "chu_han_lines": han_lines,
            "phien_am_lines": phien_am_lines,
            "dich_nghia_lines": [] if not has_dich_nghia else (bottom_dich_nghia if bottom_dich_nghia else gloss_lines),
            "dich_tho_lines": dich_tho_lines,
            "has_dich_nghia": has_dich_nghia,
        }

    # 2. TLTVN: Sequential Chữ Hán -> Phiên âm: -> Dịch nghĩa: -> Dịch thơ:
    if book_key == "TLTVN":
        han_lines = [
            unicodedata.normalize("NFC", it.get("text", "").strip())
            for it in sorted_han
            if _is_primary_han_line(it.get("text", ""))
        ]
        phien_am_lines = []
        dich_nghia_lines = []
        dich_tho_lines = []
        current_section = "phien_am"
        prev_viet_y2: Optional[float] = None

        for it in sorted_viet:
            txt = unicodedata.normalize("NFC", it.get("text", "").strip())
            if not txt or _is_primary_han_line(txt):
                continue
            _, y1, _, y2 = _box_bounds(it)
            if prev_viet_y2 is not None and (y1 - prev_viet_y2) > 55.0 and _TLTVN_NUMBERED_FOOTNOTE_RE.match(txt):
                break
            prev_viet_y2 = y2

            header_type = classify_section_header(txt)
            if header_type == "stop":
                break
            if header_type == "phien_am":
                current_section = "phien_am"
                _, rest = _extract_header_remainder(txt, _FOLDED_PHIEN_AM_HEADER_RE)
                if rest:
                    phien_am_lines.append(rest)
                continue
            if header_type == "dich_nghia":
                current_section = "dich_nghia"
                _, rest = _extract_header_remainder(txt, _FOLDED_DICH_NGHIA_HEADER_RE)
                if rest:
                    dich_nghia_lines.append(rest)
                continue
            if header_type == "dich_tho":
                current_section = "dich_tho"
                _, rest = _extract_header_remainder(txt, _FOLDED_DICH_THO_HEADER_RE)
                if rest:
                    dich_tho_lines.append(rest)
                continue

            if current_section == "dich_tho":
                dich_tho_lines.append(txt)
            elif current_section == "dich_nghia":
                dich_nghia_lines.append(txt)
            else:
                phien_am_lines.append(txt)

        return {
            "book_type": "TLTVN",
            "page_num": page_num,
            "layout_mode": "sequential_han_phien_dich",
            "chu_han_lines": han_lines,
            "phien_am_lines": phien_am_lines,
            "dich_nghia_lines": dich_nghia_lines,
            "dich_tho_lines": dich_tho_lines,
        }

    # 3. TVLT2: 2-column side-by-side poetry OR sequential prose, stopping only at KHẢO ĐÍNH / CHÚ THÍCH
    mid_x = 0.5 * float(page_width)

    stop_y: Optional[float] = None
    first_prose_sec_y: Optional[float] = None
    for it in sorted_viet:
        txt = unicodedata.normalize("NFC", it.get("text", "").strip())
        _, y1, _, _ = _box_bounds(it)
        hdr = classify_section_header(txt)
        if hdr == "stop" and stop_y is None:
            stop_y = y1
            break
        if hdr in ("dich_nghia", "dich_tho") and first_prose_sec_y is None:
            first_prose_sec_y = y1

    active_han_items = []
    for it in sorted_han:
        txt = unicodedata.normalize("NFC", it.get("text", "").strip())
        if not _is_primary_han_line(txt):
            continue
        _x1, y1, _x2, _y2 = _box_bounds(it)
        if stop_y is not None and y1 >= stop_y:
            continue
        active_han_items.append(it)

    left_col_han = [
        it for it in active_han_items
        if 0.5 * (_box_bounds(it)[0] + _box_bounds(it)[2]) < mid_x
    ]
    is_two_column_poetry = (
        len(active_han_items) > 0
        and len(left_col_han) == len(active_han_items)
        and any(
            0.5 * (_box_bounds(vit)[0] + _box_bounds(vit)[2]) >= mid_x
            for vit in sorted_viet
            if (stop_y is None or _box_bounds(vit)[1] < stop_y)
            and (first_prose_sec_y is None or _box_bounds(vit)[1] < first_prose_sec_y)
            and classify_section_header(unicodedata.normalize("NFC", vit.get("text", "").strip())) not in ("dich_nghia", "dich_tho", "stop")
        )
    )

    han_lines = [unicodedata.normalize("NFC", it.get("text", "").strip()) for it in active_han_items]
    phien_am_lines = []
    dich_nghia_lines = []
    dich_tho_lines = []
    current_section = "phien_am"

    for it in sorted_viet:
        txt = unicodedata.normalize("NFC", it.get("text", "").strip())
        if not txt or _is_primary_han_line(txt):
            continue
        x1, y1, x2, _y2 = _box_bounds(it)
        if stop_y is not None and y1 >= stop_y:
            break

        header_type = classify_section_header(txt)
        if header_type == "stop":
            break
        if header_type == "phien_am":
            current_section = "phien_am"
            _, rest = _extract_header_remainder(txt, _FOLDED_PHIEN_AM_HEADER_RE)
            if rest:
                phien_am_lines.append(rest)
            continue
        if header_type == "dich_nghia":
            current_section = "dich_nghia"
            _, rest = _extract_header_remainder(txt, _FOLDED_DICH_NGHIA_HEADER_RE)
            if rest:
                dich_nghia_lines.append(rest)
            continue
        if header_type == "dich_tho":
            current_section = "dich_tho"
            _, rest = _extract_header_remainder(txt, _FOLDED_DICH_THO_HEADER_RE)
            if rest:
                dich_tho_lines.append(rest)
            continue

        if current_section == "dich_tho":
            dich_tho_lines.append(txt)
        elif current_section == "dich_nghia":
            dich_nghia_lines.append(txt)
        elif is_two_column_poetry:
            x_center = 0.5 * (x1 + x2)
            if x_center >= mid_x * 0.85:
                phien_am_lines.append(txt)
        else:
            phien_am_lines.append(txt)

    return {
        "book_type": "TVLT2",
        "page_num": page_num,
        "layout_mode": "two_column_poetry" if is_two_column_poetry else "sequential_prose",
        "stop_y": stop_y,
        "chu_han_lines": han_lines,
        "phien_am_lines": phien_am_lines,
        "dich_nghia_lines": dich_nghia_lines,
        "dich_tho_lines": dich_tho_lines,
    }


# ---------------------------------------------------------------------------
# Dual-Engine OCR (PaddleOCR chinese_cht + VietOCR) & Mock/Dry-Run Support
# ---------------------------------------------------------------------------


def _offset_bbox_to_original(
    bbox: Sequence[Sequence[float]],
    crop_top_px: int,
) -> List[List[int]]:
    """Map a 4-point polygon bbox from header-cropped coordinates back to original page coordinates."""
    return [[int(round(pt[0])), int(round(pt[1] + crop_top_px))] for pt in bbox]


def build_mock_ocr_for_page(
    page_id: str,
    book_type: str = "TVLT2",
    page_num: int = 2,
    preprocess_meta: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Generate deterministic mock OCR output (`han_items`, `viet_items`) for local dry-run/testing."""
    book_key = BOOK_ALIAS_TO_LAYOUT.get(book_type.upper().strip(), book_type.upper().strip())
    crop_top_px = int((preprocess_meta or {}).get("crop_top_px", 140))
    page_w = int((preprocess_meta or {}).get("effective_width") or 2000)

    if book_key == "HVTT":
        if page_num == 7:
            han_raw = [
                {
                    "bbox": [[int(0.32 * page_w), 140], [int(0.62 * page_w), 140], [int(0.62 * page_w), 210], [int(0.32 * page_w), 210]],
                    "text": "子 產 論 政",
                    "confidence": 0.992,
                },
                {
                    "bbox": [[int(0.68 * page_w), 420], [int(0.86 * page_w), 420], [int(0.86 * page_w), 470], [int(0.68 * page_w), 470]],
                    "text": "左 丘 明",
                    "confidence": 0.990,
                },
            ]
            viet_raw = [
                {
                    "bbox": [[int(0.28 * page_w), 240], [int(0.66 * page_w), 240], [int(0.66 * page_w), 285], [int(0.28 * page_w), 285]],
                    "text": "TỬ-SẢN LUẬN CHÍNH",
                    "confidence": 0.988,
                },
                {
                    "bbox": [[int(0.26 * page_w), 310], [int(0.68 * page_w), 310], [int(0.68 * page_w), 355], [int(0.26 * page_w), 355]],
                    "text": "Tử-Sản bàn về việc chính-trị.",
                    "confidence": 0.985,
                },
                {
                    "bbox": [[int(0.68 * page_w), 485], [int(0.86 * page_w), 485], [int(0.86 * page_w), 530], [int(0.68 * page_w), 530]],
                    "text": "Tả Khâu Minh",
                    "confidence": 0.984,
                },
                {
                    "bbox": [[int(0.14 * page_w), 610], [int(0.86 * page_w), 610], [int(0.86 * page_w), 655], [int(0.14 * page_w), 655]],
                    "text": "TIỂU-DẪN. — Tả Khâu-Minh là sử-quan nước Lỗ đời Xuân-Thu.",
                    "confidence": 0.981,
                },
            ]
        elif page_num == 9:
            han_raw = []
            viet_raw = [
                {
                    "bbox": [[int(0.08 * page_w), 30], [int(0.32 * page_w), 30], [int(0.32 * page_w), 65], [int(0.08 * page_w), 65]],
                    "text": "HÁN-VĂN TINH-TUÝ",
                    "confidence": 0.989,
                },
                {
                    "bbox": [[int(0.86 * page_w), 30], [int(0.92 * page_w), 30], [int(0.92 * page_w), 65], [int(0.86 * page_w), 65]],
                    "text": "3",
                    "confidence": 0.990,
                },
                {
                    "bbox": [[int(0.20 * page_w), 180], [int(0.75 * page_w), 180], [int(0.75 * page_w), 225], [int(0.20 * page_w), 225]],
                    "text": "Lâm nguy dặn trẻ giữ khoan hòa,",
                    "confidence": 0.983,
                },
                {
                    "bbox": [[int(0.20 * page_w), 240], [int(0.75 * page_w), 240], [int(0.75 * page_w), 285], [int(0.20 * page_w), 285]],
                    "text": "Đức lớn yên dân ấy chính tà.",
                    "confidence": 0.982,
                },
            ]
        elif page_num == 367:
            han_raw = [
                {
                    "bbox": [[int(0.30 * page_w), 140], [int(0.64 * page_w), 140], [int(0.64 * page_w), 210], [int(0.30 * page_w), 210]],
                    "text": "秋 夜 旅 懷 吟",
                    "confidence": 0.991,
                },
                {
                    "bbox": [[int(0.68 * page_w), 430], [int(0.84 * page_w), 430], [int(0.84 * page_w), 480], [int(0.68 * page_w), 480]],
                    "text": "奇 童",
                    "confidence": 0.989,
                },
            ]
            viet_raw = [
                {
                    "bbox": [[int(0.28 * page_w), 240], [int(0.66 * page_w), 240], [int(0.66 * page_w), 285], [int(0.28 * page_w), 285]],
                    "text": "THU DẠ HOÀI NGÂM",
                    "confidence": 0.988,
                },
                {
                    "bbox": [[int(0.24 * page_w), 310], [int(0.70 * page_w), 310], [int(0.70 * page_w), 355], [int(0.24 * page_w), 355]],
                    "text": "KHÚC NGÂM CẢM HOÀI ĐÊM THU",
                    "confidence": 0.986,
                },
                {
                    "bbox": [[int(0.68 * page_w), 495], [int(0.84 * page_w), 495], [int(0.84 * page_w), 540], [int(0.68 * page_w), 540]],
                    "text": "Kỳ-Đồng",
                    "confidence": 0.984,
                },
                {
                    "bbox": [[int(0.14 * page_w), 610], [int(0.86 * page_w), 610], [int(0.86 * page_w), 655], [int(0.14 * page_w), 655]],
                    "text": "TIỂU-DẪN. — Kỳ-Đồng nguyên tên là Nguyễn-văn-Cẩm,",
                    "confidence": 0.981,
                },
            ]
        elif page_num >= 369 and page_num % 2 == 1:
            han_raw = []
            viet_raw = [
                {
                    "bbox": [[int(0.08 * page_w), 30], [int(0.32 * page_w), 30], [int(0.32 * page_w), 65], [int(0.08 * page_w), 65]],
                    "text": "HÁN-VĂN TINH-TUÝ",
                    "confidence": 0.989,
                },
                {
                    "bbox": [[int(0.84 * page_w), 30], [int(0.92 * page_w), 30], [int(0.92 * page_w), 65], [int(0.84 * page_w), 65]],
                    "text": str(page_num - 4),
                    "confidence": 0.988,
                },
                {
                    "bbox": [[int(0.18 * page_w), 160], [int(0.82 * page_w), 160], [int(0.82 * page_w), 205], [int(0.18 * page_w), 205]],
                    "text": "Đêm trung-thu trời mây trong trẻo, Sương đầm đầm lạnh lẽo bốn bên.",
                    "confidence": 0.982,
                },
                {
                    "bbox": [[int(0.18 * page_w), 230], [int(0.82 * page_w), 230], [int(0.82 * page_w), 275], [int(0.18 * page_w), 275]],
                    "text": "Thanh-nhàn riêng một cảnh tiên, Mảng vui cờ thánh rượu hiền tiêu-dao !",
                    "confidence": 0.980,
                },
            ]
        elif page_num % 2 == 1:
            han_raw = []
            viet_raw = [
                {
                    "bbox": [[int(0.08 * page_w), 30], [int(0.32 * page_w), 30], [int(0.32 * page_w), 65], [int(0.08 * page_w), 65]],
                    "text": "HÁN-VĂN TINH-TUÝ",
                    "confidence": 0.989,
                },
                {
                    "bbox": [[int(0.84 * page_w), 30], [int(0.92 * page_w), 30], [int(0.92 * page_w), 65], [int(0.84 * page_w), 65]],
                    "text": str(max(1, page_num - 4)),
                    "confidence": 0.988,
                },
                {
                    "bbox": [[int(0.15 * page_w), 160], [int(0.45 * page_w), 160], [int(0.45 * page_w), 205], [int(0.15 * page_w), 205]],
                    "text": "CHÚ THÍCH :",
                    "confidence": 0.990,
                },
                {
                    "bbox": [[int(0.15 * page_w), 220], [int(0.85 * page_w), 220], [int(0.85 * page_w), 265], [int(0.15 * page_w), 265]],
                    "text": "1) Chú giải văn bản cổ.",
                    "confidence": 0.980,
                },
            ]
        elif page_num == 10:
            han_raw = [
                {"bbox": [[180, 120], [1620, 120], [1620, 175], [180, 175]], "text": "不 忍 猛 而 寬", "confidence": 0.992},
                {"bbox": [[180, 300], [1620, 300], [1620, 355], [180, 355]], "text": "鄭 國 多 盜", "confidence": 0.991},
                {"bbox": [[180, 480], [1620, 480], [1620, 535], [180, 535]], "text": "取 人 於 萑 苻 之 澤", "confidence": 0.988},
                {"bbox": [[180, 660], [1620, 660], [1620, 715], [180, 715]], "text": "太 叔 悔 之 曰", "confidence": 0.990},
                {"bbox": [[180, 840], [1620, 840], [1620, 895], [180, 895]], "text": "吾 早 從 夫 子 不 及 此", "confidence": 0.989},
                {"bbox": [[180, 1020], [1620, 1020], [1620, 1075], [180, 1075]], "text": "興 徒 兵 以 攻 萑 苻 之 盜", "confidence": 0.987},
                {"bbox": [[180, 1200], [1620, 1200], [1620, 1255], [180, 1255]], "text": "盡 殺 之 盜 少 止", "confidence": 0.990},
                {"bbox": [[180, 1380], [1620, 1380], [1620, 1435], [180, 1435]], "text": "仲 尼 曰 善 哉", "confidence": 0.991},
            ]
            viet_raw = [
                {"bbox": [[180, 185], [1620, 185], [1620, 230], [180, 230]], "text": "Bất nhẫn mãnh nhi khoan.", "confidence": 0.985, "role": "phien_am"},
                {"bbox": [[180, 240], [1620, 240], [1620, 285], [180, 285]], "text": "Không nỡ mạnh nên khoan hòa.", "confidence": 0.981, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 365], [1620, 365], [1620, 410], [180, 410]], "text": "Trịnh-quốc đa đạo.", "confidence": 0.986, "role": "phien_am"},
                {"bbox": [[180, 420], [1620, 420], [1620, 465], [180, 465]], "text": "Nước Trịnh nhiều trộm cướp.", "confidence": 0.982, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 545], [1620, 545], [1620, 590], [180, 590]], "text": "Thủ nhân ư hoàn bồ chi trạch.", "confidence": 0.984, "role": "phien_am"},
                {"bbox": [[180, 600], [1620, 600], [1620, 645], [180, 645]], "text": "Bắt người lương thiện ở nơi bãi chằm um tùm.", "confidence": 0.979, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 725], [1620, 725], [1620, 770], [180, 770]], "text": "Thái-Thúc hối chi, viết :", "confidence": 0.985, "role": "phien_am"},
                {"bbox": [[180, 780], [1620, 780], [1620, 825], [180, 825]], "text": "Thái-Thúc ăn-năn, nói :", "confidence": 0.980, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 905], [1620, 905], [1620, 950], [180, 950]], "text": "Ngô tảo tòng phu-tử, bất cập thử.", "confidence": 0.986, "role": "phien_am"},
                {"bbox": [[180, 960], [1620, 960], [1620, 1005], [180, 1005]], "text": "Ta sớm biết theo lời cha đâu đến nỗi này.", "confidence": 0.981, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 1085], [1620, 1085], [1620, 1130], [180, 1130]], "text": "Hưng đồ binh dĩ công hoàn bồ chi đạo.", "confidence": 0.985, "role": "phien_am"},
                {"bbox": [[180, 1140], [1620, 1140], [1620, 1185], [180, 1185]], "text": "Đem binh đi tiễu trừ trộm cướp.", "confidence": 0.980, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 1265], [1620, 1265], [1620, 1310], [180, 1310]], "text": "Tận sát chi. Đạo thiểu chỉ.", "confidence": 0.986, "role": "phien_am"},
                {"bbox": [[180, 1320], [1620, 1320], [1620, 1365], [180, 1365]], "text": "Giết hết. Cướp trộm yên.", "confidence": 0.982, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 1445], [1620, 1445], [1620, 1490], [180, 1490]], "text": "Trọng-Ni viết : Thiện tai !", "confidence": 0.987, "role": "phien_am"},
                {"bbox": [[180, 1500], [1620, 1500], [1620, 1545], [180, 1545]], "text": "Khổng-tử nói : Giỏi thay !", "confidence": 0.983, "role": "dich_nghia_gloss"},
            ]
        elif page_num == 12:
            han_raw = [
                {"bbox": [[180, 120], [1620, 120], [1620, 175], [180, 175]], "text": "政 寬 則 民 慢", "confidence": 0.992},
                {"bbox": [[180, 300], [1620, 300], [1620, 355], [180, 355]], "text": "慢 則 糾 之 以 猛", "confidence": 0.990},
                {"bbox": [[180, 480], [1620, 480], [1620, 535], [180, 535]], "text": "猛 則 民 殘 殘 則 施 之 以 寬", "confidence": 0.989},
                {"bbox": [[180, 660], [1620, 660], [1620, 715], [180, 715]], "text": "寬 以 濟 猛 猛 以 濟 寬", "confidence": 0.991},
                {"bbox": [[180, 840], [1620, 840], [1620, 895], [180, 895]], "text": "政 是 以 和", "confidence": 0.992},
                {"bbox": [[180, 1020], [1620, 1020], [1620, 1075], [180, 1075]], "text": "詩 曰 民 亦 勞 止 汔 可 小 康", "confidence": 0.988},
                {"bbox": [[180, 1260], [1620, 1260], [1620, 1315], [180, 1315]], "text": "惠 此 中 國 以 綏 四 方", "confidence": 0.989},
                {"bbox": [[180, 1500], [1620, 1500], [1620, 1555], [180, 1555]], "text": "施 之 以 寬 也", "confidence": 0.991},
            ]
            viet_raw = [
                {"bbox": [[180, 185], [1620, 185], [1620, 230], [180, 230]], "text": "Chính khoan tắc dân mạn,", "confidence": 0.985, "role": "phien_am"},
                {"bbox": [[180, 240], [1620, 240], [1620, 285], [180, 285]], "text": "Chính sách khoan hòa dân nhờn,", "confidence": 0.981, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 365], [1620, 365], [1620, 410], [180, 410]], "text": "mạn tắc củ chi dĩ mãnh.", "confidence": 0.986, "role": "phien_am"},
                {"bbox": [[180, 420], [1620, 420], [1620, 465], [180, 465]], "text": "nhờn thì lấy « mạnh » (thẳng tay) mà đàn áp.", "confidence": 0.980, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 545], [1620, 545], [1620, 590], [180, 590]], "text": "Mãnh tắc dân tàn, tàn tắc thi chi dĩ khoan.", "confidence": 0.984, "role": "phien_am"},
                {"bbox": [[180, 600], [1620, 600], [1620, 645], [180, 645]], "text": "Mạnh tất dân hại, hại thì lại lấy khoan mà thi-hành.", "confidence": 0.979, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 725], [1620, 725], [1620, 770], [180, 770]], "text": "Khoan dĩ tế mãnh, mãnh dĩ tế khoan.", "confidence": 0.986, "role": "phien_am"},
                {"bbox": [[180, 780], [1620, 780], [1620, 825], [180, 825]], "text": "Khoan để đỡ mạnh, mạnh để đỡ khoan.", "confidence": 0.982, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 905], [1620, 905], [1620, 950], [180, 950]], "text": "Chính thị dĩ hòa.", "confidence": 0.987, "role": "phien_am"},
                {"bbox": [[180, 960], [1620, 960], [1620, 1005], [180, 1005]], "text": "Chính sự sẽ hòa.", "confidence": 0.983, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 1085], [1620, 1085], [1620, 1130], [180, 1130]], "text": "Thi viết : dân diệc lao chỉ, ngật khả tiểu-khang.", "confidence": 0.984, "role": "phien_am"},
                {"bbox": [[180, 1140], [1620, 1140], [1620, 1185], [180, 1185]], "text": "Kinh thi nói : dân đỡ vất-vả, để tạm yên vui.", "confidence": 0.980, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 1195], [1620, 1195], [1620, 1240], [180, 1240]], "text": "Dân vất-vả, ngõ hầu yên-ổn,", "confidence": 0.978, "role": "dich_tho"},
                {"bbox": [[180, 1325], [1620, 1325], [1620, 1370], [180, 1370]], "text": "Huệ thử trung-quốc, dĩ tuy tứ phương.", "confidence": 0.985, "role": "phien_am"},
                {"bbox": [[180, 1380], [1620, 1380], [1620, 1425], [180, 1425]], "text": "Ra ơn trong nước, để yên bốn phương.", "confidence": 0.981, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 1435], [1620, 1435], [1620, 1480], [180, 1480]], "text": "Ơn ban ra vỗ-về bốn phương.", "confidence": 0.979, "role": "dich_tho"},
                {"bbox": [[180, 1565], [1620, 1565], [1620, 1610], [180, 1610]], "text": "Thi chi dĩ khoan dã.", "confidence": 0.986, "role": "phien_am"},
                {"bbox": [[180, 1620], [1620, 1620], [1620, 1665], [180, 1665]], "text": "Ấy là lấy « khoan » mà thi-hành vậy.", "confidence": 0.982, "role": "dich_nghia_gloss"},
            ]
        elif page_num >= 368:
            # Bài cuối (Thu dạ hoài ngâm): chỉ có Hán - Dịch âm - Dịch thơ, cột Dịch nghĩa để trống
            han_raw = [
                {"bbox": [[180, 160], [1620, 160], [1620, 215], [180, 215]], "text": "天 氣 入 中 秋 之 夜 蕭 條 經 四 坐 霜 寒", "confidence": 0.990},
                {"bbox": [[180, 380], [1620, 380], [1620, 435], [180, 435]], "text": "仙 家 別 占 清 閒 打 殘 棋 陣 飲 殘 菊 杯", "confidence": 0.989},
            ]
            viet_raw = [
                {"bbox": [[180, 225], [1620, 225], [1620, 270], [180, 270]], "text": "Thiên khí nhập trung-thu chi dạ, Tiêu-điều kinh tứ tọa sương hàn.", "confidence": 0.985, "role": "phien_am"},
                {"bbox": [[180, 280], [1620, 280], [1620, 325], [180, 325]], "text": "Đêm trung-thu trời mây trong trẻo, Sương đầm đầm lạnh lẽo bốn bên.", "confidence": 0.982, "role": "dich_tho"},
                {"bbox": [[180, 445], [1620, 445], [1620, 490], [180, 490]], "text": "Tiên gia biệt chiếm thanh-nhàn, Đả tàn kỳ trận, ẩm tàn cúc bôi !", "confidence": 0.984, "role": "phien_am"},
                {"bbox": [[180, 500], [1620, 500], [1620, 545], [180, 545]], "text": "Thanh-nhàn riêng một cảnh tiên, Mảng vui cờ thánh rượu hiền tiêu-dao !", "confidence": 0.980, "role": "dich_tho"},
            ]
        else:
            han_raw = [
                {"bbox": [[180, 120], [1620, 120], [1620, 175], [180, 175]], "text": "鄭 子 產 有 疾 謂 子 太 叔 曰", "confidence": 0.992},
                {"bbox": [[180, 310], [1620, 310], [1620, 365], [180, 365]], "text": "我 死 子 必 爲 政", "confidence": 0.990},
                {"bbox": [[180, 490], [1620, 490], [1620, 545], [180, 545]], "text": "惟 有 德 者 能 以 寬 服 民", "confidence": 0.989},
                {"bbox": [[180, 670], [1620, 670], [1620, 725], [180, 725]], "text": "其 次 莫 如 猛", "confidence": 0.991},
                {"bbox": [[180, 850], [1620, 850], [1620, 905], [180, 905]], "text": "夫 火 烈 民 望 而 畏 之 故 鮮 死 焉", "confidence": 0.989},
                {"bbox": [[180, 1030], [1620, 1030], [1620, 1085], [180, 1085]], "text": "水 懦 弱 民 狎 而 翫 之 則 多 死 焉", "confidence": 0.988},
                {"bbox": [[180, 1210], [1620, 1210], [1620, 1265], [180, 1265]], "text": "故 寬 難", "confidence": 0.992},
                {"bbox": [[180, 1390], [1620, 1390], [1620, 1445], [180, 1445]], "text": "疾 數 月 而 卒 太 叔 爲 政", "confidence": 0.990},
            ]
            viet_raw = [
                {"bbox": [[180, 185], [1620, 185], [1620, 230], [180, 230]], "text": "Trịnh Tử-Sản hữu tật, vị tử Thái-Thúc viết :", "confidence": 0.985, "role": "phien_am"},
                {"bbox": [[180, 240], [1620, 240], [1620, 290], [180, 290]], "text": "Trịnh Tử-Sản bệnh nặng, bảo con là Thái-Thúc rằng :", "confidence": 0.978, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 375], [1620, 375], [1620, 420], [180, 420]], "text": "Ngã tử, tử tất vi chính.", "confidence": 0.986, "role": "phien_am"},
                {"bbox": [[180, 430], [1620, 430], [1620, 475], [180, 475]], "text": "Ta chết, con sẽ giữ chính-quyền.", "confidence": 0.980, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 555], [1620, 555], [1620, 600], [180, 600]], "text": "Duy hữu đức giả, năng dĩ khoan phục dân,", "confidence": 0.984, "role": "phien_am"},
                {"bbox": [[180, 610], [1620, 610], [1620, 655], [180, 655]], "text": "Chỉ kẻ có đức mới có thể lấy khoan hòa cho dân phục,", "confidence": 0.976, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 735], [1620, 735], [1620, 780], [180, 780]], "text": "Kỳ thứ mạc như mãnh.", "confidence": 0.987, "role": "phien_am"},
                {"bbox": [[180, 790], [1620, 790], [1620, 835], [180, 835]], "text": "còn thì không gì bằng chính-sách mạnh.", "confidence": 0.981, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 915], [1620, 915], [1620, 960], [180, 960]], "text": "Phù hỏa liệt, dân vọng nhi úy chi, cố tiển tử yên.", "confidence": 0.985, "role": "phien_am"},
                {"bbox": [[180, 970], [1620, 970], [1620, 1015], [180, 1015]], "text": "Như lửa cháy, dân trông là sợ, nên ít kẻ chết vì lửa.", "confidence": 0.979, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 1095], [1620, 1095], [1620, 1140], [180, 1140]], "text": "Thủy nhu nhược, dân hạp nhi ngoạn chi, tắc đa tử yên.", "confidence": 0.984, "role": "phien_am"},
                {"bbox": [[180, 1150], [1620, 1150], [1620, 1195], [180, 1195]], "text": "Nước mềm yếu, dân ưa đùa-rỡn, nên chết nhiều.", "confidence": 0.978, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 1275], [1620, 1275], [1620, 1320], [180, 1320]], "text": "Cố khoan nan.", "confidence": 0.988, "role": "phien_am"},
                {"bbox": [[180, 1330], [1620, 1330], [1620, 1375], [180, 1375]], "text": "Vì thế khoan hồng là khó.", "confidence": 0.982, "role": "dich_nghia_gloss"},
                {"bbox": [[180, 1455], [1620, 1455], [1620, 1500], [180, 1500]], "text": "Tật sổ nguyệt nhi tốt, Thái-Thúc vi chính.", "confidence": 0.985, "role": "phien_am"},
                {"bbox": [[180, 1510], [1620, 1510], [1620, 1555], [180, 1555]], "text": "Đau mấy tháng rồi chết, Thái-Thúc lên cầm quyền.", "confidence": 0.980, "role": "dich_nghia_gloss"},
            ]
    elif book_key == "TLTVN":
        han_raw = [
            {"bbox": [[220, 150], [1480, 150], [1480, 200], [220, 200]], "text": "祥光風好錦帆張, 神仙復帝鄉.", "confidence": 0.992},
            {"bbox": [[220, 210], [1480, 210], [1480, 260], [220, 260]], "text": "千重萬里涉滄浪, 九天歸路長.", "confidence": 0.990},
            {"bbox": [[220, 270], [1480, 270], [1480, 320], [220, 320]], "text": "情慘切, 對離觴, 攀戀使星郎.", "confidence": 0.991},
            {"bbox": [[220, 330], [1480, 330], [1480, 380], [220, 380]], "text": "願將深意為南疆, 分明報我皇.", "confidence": 0.990},
        ]
        viet_raw = [
            {"bbox": [[220, 410], [900, 410], [900, 450], [220, 450]], "text": "Phiên âm:", "confidence": 0.995},
            {"bbox": [[220, 460], [1500, 460], [1500, 505], [220, 505]], "text": "Tường quang phong hảo cẩm phàm trương, Thần tiên phục đế hương².", "confidence": 0.986},
            {"bbox": [[220, 515], [1500, 515], [1500, 560], [220, 560]], "text": "Thiên trùng vạn lí¹ thiệp thương lương, Cửu thiên quy lộ trường.", "confidence": 0.985},
            {"bbox": [[220, 570], [1500, 570], [1500, 615], [220, 615]], "text": "Tình thảm thiết², Đối li thương, Phan luyến sứ tinh lang³.", "confidence": 0.986},
            {"bbox": [[220, 625], [1500, 625], [1500, 670], [220, 670]], "text": "Nguyện tương thâm ý vị Nam cương, Phân minh báo⁴ ngã hoàng.", "confidence": 0.985},
            {"bbox": [[220, 690], [900, 690], [900, 730], [220, 730]], "text": "Dịch nghĩa:", "confidence": 0.994},
            {"bbox": [[220, 740], [1580, 740], [1580, 790], [220, 790]], "text": "Ánh sáng tốt lành, gió thuận, căng cánh buồm gấm, Thần tiên trở về quê hương của hoàng đế⁵.", "confidence": 0.983},
            {"bbox": [[220, 800], [1580, 800], [1580, 850], [220, 850]], "text": "Nghìn trùng muôn dặm vượt qua những làn sóng xanh, Đường qua về chín tầng trời¹.", "confidence": 0.982},
            {"bbox": [[220, 860], [1580, 860], [1580, 910], [220, 910]], "text": "Tình thảm thiết, Đối diện với chén rượu biệt li, Yêu mến vin lấy chàng sứ giả.", "confidence": 0.983},
            {"bbox": [[220, 920], [1580, 920], [1580, 970], [220, 970]], "text": "Xin hãy đem cái ý sâu xa vì biên cương phía Nam, Báo rõ cho nhà vua của chúng ta.", "confidence": 0.984},
            {"bbox": [[220, 990], [900, 990], [900, 1030], [220, 1030]], "text": "Dịch theo nguyên điệu:", "confidence": 0.991},
            {"bbox": [[220, 1040], [1400, 1040], [1400, 1085], [220, 1085]], "text": "Trời trong gió mát cánh buồm giương, Thần tiên về đế hương.", "confidence": 0.980},
        ]
    else:
        # TVLT2: page-aware pilot blocks (Work 1 at page 19, Work 2 at page 20, Work 3 at page 22..26)
        if page_num == 20:
            han_raw = [
                {"bbox": [[180, 160], [880, 160], [880, 210], [180, 210]], "text": "顧無瓊報自懷慚，極目江皋意不堪。", "confidence": 0.992},
                {"bbox": [[180, 225], [880, 225], [880, 275], [180, 275]], "text": "馬首秋風吹劍鋏，屋梁落月照書庵。", "confidence": 0.991},
                {"bbox": [[180, 290], [880, 290], [880, 340], [180, 340]], "text": "幕空難駐燕歸北，地暖愁聞雁別南。", "confidence": 0.990},
                {"bbox": [[180, 355], [880, 355], [880, 405], [180, 405]], "text": "此去未知傾蓋日，詩篇聊為當清談。", "confidence": 0.991},
            ]
            viet_raw = [
                {"bbox": [[1020, 160], [1780, 160], [1780, 210], [1020, 210]], "text": "Cố 1* vô quỳnh báo tự hoài tàm, Cực mục giang cao ý bất kham.", "confidence": 0.987},
                {"bbox": [[1020, 225], [1780, 225], [1780, 275], [1020, 275]], "text": "Mã thủ thu phong xuy kiếm giáp, Ốc lương lạc nguyệt 2* chiếu thư am.", "confidence": 0.986},
                {"bbox": [[1020, 290], [1780, 290], [1780, 340], [1020, 340]], "text": "Mạc 3* không nan trụ 4* yến quy Bắc, Địa noãn 5* sầu văn nhạn biệt Nam.", "confidence": 0.986},
                {"bbox": [[1020, 355], [1780, 355], [1780, 405], [1020, 405]], "text": "Thử khứ vị tri khuynh cái nhật, Thi thiên 6* liêu vị 7* đáng thanh 8* đàm.", "confidence": 0.985},
                {"bbox": [[180, 450], [600, 450], [600, 495], [180, 495]], "text": "DỊCH NGHĨA :", "confidence": 0.994},
                {"bbox": [[180, 505], [1780, 505], [1780, 550], [180, 550]], "text": "Nghĩ không có ngọc quỳnh (2) đáp lại, lòng tự thẹn. Trên bờ sông nhìn xa mãi xiết bao bùi ngùi.", "confidence": 0.985},
                {"bbox": [[180, 560], [1780, 560], [1780, 605], [180, 605]], "text": "Gió thu trước đầu ngựa thổi vào thanh gươm, Ánh trăng lọt qua rường nhà (3) dọi vào phòng sách.", "confidence": 0.984},
                {"bbox": [[180, 615], [1780, 615], [1780, 660], [180, 660]], "text": "Màn trống khó ngăn chim én về phương Bắc, Đất ấm buồn nghe chim nhạn biệt phương Nam.", "confidence": 0.984},
                {"bbox": [[180, 670], [1780, 670], [1780, 715], [180, 715]], "text": "Lần đi này chưa biết ngày nào mới có dịp nghiêng lọng (4), Xin vì cuộc chuyện trò tao nhã mà có một bài thơ.", "confidence": 0.983},
                {"bbox": [[180, 735], [600, 735], [600, 780], [180, 780]], "text": "DỊCH THƠ :", "confidence": 0.992},
                {"bbox": [[180, 790], [1400, 790], [1400, 840], [180, 840]], "text": "Nghĩ chẳng ngọc quỳnh đáp tấm lòng, Bến giang man mác nỗi hoài trông.", "confidence": 0.980},
            ]
        elif page_num in (22, 23, 24, 26):
            han_raw = [
                {"bbox": [[180, 160], [1720, 160], [1720, 210], [180, 210]], "text": "朕竊謂佛無南北均可修求，性有智愚同資覺悟。", "confidence": 0.991},
                {"bbox": [[180, 225], [1720, 225], [1720, 275], [180, 275]], "text": "是以誘群迷之方便，明生死之捷徑者，我佛之大教也；任垂世之權衡，作將來之軌範者，先聖之重責也。", "confidence": 0.990},
                {"bbox": [[180, 290], [1720, 290], [1720, 340], [180, 340]], "text": "故六祖有言云：先大聖人與大師無別，則知我佛之教，又假先聖人以傳於世也。今朕焉可不以先聖之任為己之任，我佛之教為己之教哉！", "confidence": 0.989},
                {"bbox": [[180, 355], [1720, 355], [1720, 405], [180, 405]], "text": "且朕於孩童有識之年，稍聞禪師之訓，則澄思息慮，慨然清淨，有心乎內教，參究於禪宗，虛己求師，精誠慕道。雖回向之意已萌，而感觸之機未達。", "confidence": 0.988},
                {"bbox": [[180, 420], [1720, 420], [1720, 470], [180, 470]], "text": "師曰：山本無佛，惟存乎心。心寂而知，是名真佛。今陛下若悟此心，則立地成佛，無苦外求也。", "confidence": 0.990},
                {"bbox": [[180, 485], [1720, 485], [1720, 535], [180, 535]], "text": "朕聞是言，乃命工楷寫，敕令開印，非特以為後世指迷，蓋欲繼先代聖人之功廣，因自為序云。", "confidence": 0.989},
            ]
            viet_raw = [
                {"bbox": [[180, 570], [500, 570], [500, 610], [180, 610]], "text": "PHIÊN ÂM :", "confidence": 0.993},
                {"bbox": [[180, 620], [1780, 620], [1780, 665], [180, 665]], "text": "Trẫm thiết vị : Phật vô Nam Bắc, quân khả tu cầu ; tính hữu trí ngu, đồng tư giác ngộ.", "confidence": 0.986},
                {"bbox": [[180, 675], [1780, 675], [1780, 720], [180, 720]], "text": "Thị dĩ dụ quần mê chi phương-tiện, minh sinh tử chi tiệp kính giả, ngã Phật chi đại giáo dã ; nhậm thùy thế chi quyền hành, tác tương lai chi quỹ phạm giả, tiên thánh chi trọng trách 1* dã.", "confidence": 0.985},
                {"bbox": [[180, 730], [1780, 730], [1780, 775], [180, 775]], "text": "Cố Lục Tổ hữu ngôn vân : Tiên đại thánh nhân dữ đại sư vô biệt, tắc tri ngã Phật chi giáo hựu giả tiên thánh nhân dĩ truyền ư thế dã. Kim trẫm yên khả bất dĩ tiên thánh chi nhậm vi kỷ chi nhậm, ngã Phật chi giáo vi kỷ chi giáo tai !", "confidence": 0.984},
                {"bbox": [[180, 785], [1780, 785], [1780, 830], [180, 830]], "text": "Thả trẫm ư hài đồng hữu thức chi niên, sảo văn Thiền sư chi huấn, tắc trừng tư tức lự, khái nhiên thanh tịnh, hữu tâm hồ nội giáo, tham cứu ư Thiền tông, hư kỷ cầu sư, tinh thành mộ đạo. Tuy hồi hướng chi ý dĩ manh, nhi cảm xúc chi cơ vị đạt.", "confidence": 0.984},
                {"bbox": [[180, 840], [1780, 840], [1780, 885], [180, 885]], "text": "Sư viết : Sơn bản vô Phật, duy tồn hồ tâm. Tâm tịch nhi tri, thị danh Chân Phật. Kim Bệ hạ nhược ngộ thử tâm, tắc lập địa thành Phật, vô khổ ngoại cầu dã.", "confidence": 0.985},
                {"bbox": [[180, 895], [1780, 895], [1780, 940], [180, 940]], "text": "Trẫm văn thị ngôn, nãi mệnh công khải tả, sắc lệnh khai ấn, phi đặc dĩ vi hậu thế chỉ mê, cái dục kế tiên đại thánh nhân chi công quảng, nhân tự vi tự vân.", "confidence": 0.984},
            ]
        else:
            # Default / Page 19: 2-column side-by-side poetry + DỊCH NGHĨA + DỊCH THƠ stop boundary
            han_raw = [
                {"bbox": [[180, 160], [880, 160], [880, 210], [180, 210]], "text": "風打松關月照庭，心期風景共淒清。", "confidence": 0.993},
                {"bbox": [[180, 225], [880, 225], [880, 275], [180, 275]], "text": "箇中滋味無人識，付與山僧樂到明。", "confidence": 0.991},
            ]
            viet_raw = [
                {"bbox": [[1020, 160], [1780, 160], [1780, 210], [1020, 210]], "text": "Phong đả tùng quan 1* nguyệt chiếu đình, Tâm kỳ phong cảnh cộng thê thanh.", "confidence": 0.988},
                {"bbox": [[1020, 225], [1780, 225], [1780, 275], [1020, 275]], "text": "Cá trung tư vị vô nhân thức, Phó dữ sơn tăng lạc đáo minh.", "confidence": 0.987},
                {"bbox": [[180, 340], [600, 340], [600, 385], [180, 385]], "text": "DỊCH NGHĨA :", "confidence": 0.994},
                {"bbox": [[180, 395], [1780, 395], [1780, 440], [180, 440]], "text": "Gió đập cổng thông, trăng sáng trước sân, Lòng hẹn với phong cảnh cùng trong sạch lặng lẽ.", "confidence": 0.985},
                {"bbox": [[180, 450], [1780, 450], [1780, 495], [180, 495]], "text": "Bao nhiêu thú vị trong đó không ai hay, Mặc cho nhà sư trong núi vui đến sáng.", "confidence": 0.984},
                {"bbox": [[180, 520], [600, 520], [600, 565], [180, 565]], "text": "DỊCH THƠ :", "confidence": 0.992},
                {"bbox": [[180, 575], [1400, 575], [1400, 625], [180, 625]], "text": "Gió đập cửa thông, trăng lấp loáng, Lòng đây, cảnh đấy cùng thanh sảng.", "confidence": 0.980},
            ]

    han_items: List[Dict[str, Any]] = []
    for idx, item in enumerate(han_raw):
        bbox = item["bbox"]
        x1, y1, x2, y2 = _box_bounds({"bbox": bbox})
        han_items.append({
            "line_id": f"{page_id}_han_{idx:03d}",
            "bbox": bbox,
            "bbox_original": _offset_bbox_to_original(bbox, crop_top_px),
            "box_xyxy": [int(x1), int(y1), int(x2), int(y2)],
            "text": item["text"],
            "confidence": float(item["confidence"]),
        })

    viet_items: List[Dict[str, Any]] = []
    for idx, item in enumerate(viet_raw):
        bbox = item["bbox"]
        x1, y1, x2, y2 = _box_bounds({"bbox": bbox})
        entry: Dict[str, Any] = {
            "line_id": f"{page_id}_viet_{idx:03d}",
            "bbox": bbox,
            "bbox_original": _offset_bbox_to_original(bbox, crop_top_px),
            "box_xyxy": [int(x1), int(y1), int(x2), int(y2)],
            "text": item["text"],
            "confidence": float(item["confidence"]),
        }
        if "role" in item:
            entry["role"] = item["role"]
        viet_items.append(entry)

    return han_items, viet_items


class _VietOCRCudaSubprocessProxy:
    """Lightweight persistent subprocess delegating VietOCR `predict_batch` to a CUDA-enabled Python."""

    _WORKER_CODE = r'''
import base64, contextlib, io, json, sys, torch
from PIL import Image
if not hasattr(Image, "ANTIALIAS"):
    resampling = getattr(Image, "Resampling", Image)
    Image.ANTIALIAS = getattr(resampling, "LANCZOS")
orig_load = torch.load
torch.load = lambda *a, **kw: orig_load(*a, **{**kw, "weights_only": False})
from vietocr.tool.config import Cfg
from vietocr.tool.predictor import Predictor
with contextlib.redirect_stdout(sys.stderr):
    cfg = Cfg.load_config_from_name("vgg_transformer")
    cfg["cnn"]["pretrained"] = True
    cfg["device"] = "cuda:0" if torch.cuda.is_available() else "cpu"
    pred = Predictor(cfg)
sys.stdout.write(json.dumps({"ready": True, "device": cfg["device"]}) + "\n")
sys.stdout.flush()
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    req = json.loads(line)
    if req.get("cmd") == "quit":
        break
    imgs = [Image.open(io.BytesIO(base64.b64decode(b))).convert("RGB") for b in req["crops_b64"]]
    if not imgs:
        sys.stdout.write(json.dumps({"results": []}) + "\n")
        sys.stdout.flush()
        continue
    texts, probs = pred.predict_batch(imgs, return_prob=True)
    out = [[str(t), float(p)] for t, p in zip(texts, probs)]
    sys.stdout.write(json.dumps({"results": out}, ensure_ascii=False) + "\n")
    sys.stdout.flush()
'''

    def __init__(self, python_exe: str) -> None:
        env = dict(os.environ)
        env.pop("VIRTUAL_ENV", None)
        env.pop("PYTHONHOME", None)
        self._proc = subprocess.Popen(
            [python_exe, "-u", "-c", self._WORKER_CODE],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            encoding="utf-8",
        )
        assert self._proc.stdout is not None
        ready_line = ""
        while True:
            raw = self._proc.stdout.readline()
            if not raw:
                break
            if raw.strip().startswith("{"):
                ready_line = raw.strip()
                break
        if not ready_line:
            err = self._proc.stderr.read() if self._proc.stderr else ""
            self.close()
            raise RuntimeError(f"VietOCR CUDA proxy failed to start: {err}")
        info = json.loads(ready_line)
        self.device = str(info.get("device", "cuda:0"))

    def predict_batch(self, pil_images: List[Any], return_prob: bool = True) -> Tuple[List[str], List[float]]:
        import base64
        import io
        if not pil_images:
            return [], []
        assert self._proc.stdin is not None and self._proc.stdout is not None
        crops_b64: List[str] = []
        for img in pil_images:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            crops_b64.append(base64.b64encode(buf.getvalue()).decode("ascii"))
        self._proc.stdin.write(json.dumps({"crops_b64": crops_b64}) + "\n")
        self._proc.stdin.flush()
        resp_line = self._proc.stdout.readline().strip()
        if not resp_line:
            raise RuntimeError("VietOCR CUDA proxy returned EOF")
        res = json.loads(resp_line).get("results", [])
        return [str(t) for t, _ in res], [float(p) for _, p in res]

    def predict(self, pil_img: Any, return_prob: bool = True) -> Tuple[str, float]:
        texts, probs = self.predict_batch([pil_img], return_prob=True)
        return texts[0], probs[0]

    def close(self) -> None:
        proc = getattr(self, "_proc", None)
        if proc is None:
            return
        try:
            if proc.poll() is None and proc.stdin is not None:
                proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
                proc.stdin.flush()
                proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        self._proc = None


class KaggleDualOCREngine:
    """Wrapper around GPU PaddleOCR (`chinese_cht` / `vi`) and optional VietOCR (`vgg_transformer`).

    Compatible with both PaddleOCR 2.x and PaddleOCR 3.x APIs on Kaggle Python 3.13+.
    """

    def __init__(self, use_gpu: bool = True, mock: bool = False) -> None:
        self.use_gpu = use_gpu
        self.mock = mock
        self._han_ocr: Any = None
        self._viet_det_ocr: Any = None
        self._viet_predictor: Any = None

    @staticmethod
    def _is_kaggle_runtime() -> bool:
        return bool(os.environ.get("KAGGLE_KERNEL_RUN_TYPE") or Path("/kaggle/working").exists())

    @staticmethod
    def _create_paddle_ocr(lang: str, effective_gpu: bool) -> Any:
        from paddleocr import PaddleOCR  # type: ignore

        device_str = "gpu:0" if effective_gpu else "cpu"
        try:
            return PaddleOCR(
                lang=lang,
                device=device_str,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        except (TypeError, ValueError):
            try:
                return PaddleOCR(
                    use_angle_cls=False,
                    lang=lang,
                    use_gpu=effective_gpu,
                    show_log=False,
                )
            except (TypeError, ValueError):
                return PaddleOCR(lang=lang)

    @staticmethod
    def _run_paddle_ocr(ocr_obj: Any, image_bgr: Any) -> List[Tuple[List[List[int]], str, float]]:
        """Run OCR across PaddleOCR 2.x `.ocr()` and 3.x `.predict()` interfaces."""
        parsed: List[Tuple[List[List[int]], str, float]] = []
        if hasattr(ocr_obj, "predict"):
            try:
                preds = ocr_obj.predict(image_bgr)
                for res in preds or []:
                    payload = getattr(res, "json", None)
                    if callable(payload):
                        payload = payload()
                    data = payload.get("res", payload) if isinstance(payload, dict) else (
                        res if isinstance(res, dict) else {}
                    )
                    polys = data.get("dt_polys")
                    if polys is None or len(polys) == 0:
                        polys = data.get("rec_polys")
                    if polys is None:
                        polys = []
                    texts = data.get("rec_texts")
                    if texts is None:
                        texts = []
                    scores = data.get("rec_scores")
                    if scores is None:
                        scores = []
                    for poly, txt, sc in zip(polys, texts, scores):
                        pts = [[int(round(float(pt[0]))), int(round(float(pt[1])))] for pt in poly]
                        parsed.append((pts, str(txt), float(sc)))
                return parsed
            except Exception:
                parsed = []

        raw: Any = []
        if hasattr(ocr_obj, "ocr"):
            try:
                raw = ocr_obj.ocr(image_bgr, cls=True)
            except TypeError:
                raw = ocr_obj.ocr(image_bgr)
        lines = raw[0] if raw and raw[0] else []
        for line in lines:
            pts = [[int(round(float(pt[0]))), int(round(float(pt[1])))] for pt in line[0]]
            txt, sc = str(line[1][0]), float(line[1][1])
            parsed.append((pts, txt, sc))
        return parsed

    def _lazy_init_gpu_engines(self) -> None:
        if self.mock or self._han_ocr is not None:
            return

        global cv2, np, Image
        try:
            try:
                import torch  # type: ignore  # noqa: F401
            except Exception:
                pass
            import paddle  # type: ignore  # noqa: F401
            from paddleocr import PaddleOCR  # type: ignore  # noqa: F401
        except ImportError:
            if self._is_kaggle_runtime():
                _install_kaggle_dependencies_if_needed()
                try:
                    import cv2 as _cv2  # type: ignore
                    import numpy as _np  # type: ignore
                    from PIL import Image as _Image  # type: ignore
                    cv2 = _cv2
                    np = _np
                    Image = _Image
                except ImportError:
                    pass
            else:
                raise RuntimeError(
                    "Live OCR requires `paddleocr` and `opencv-python-headless`. "
                    "Install them or run via Kaggle GPU (`./kaggle_ocr/deploy_to_kaggle.sh`) "
                    "or use `--mock` / `--dry-run` locally."
                )

        if Image is None:
            try:
                from PIL import Image as _Image  # type: ignore
                Image = _Image
            except ImportError:
                pass

        try:
            import torch  # type: ignore  # noqa: F401
        except Exception:
            pass
        import paddle  # type: ignore

        effective_gpu = bool(
            self.use_gpu
            and getattr(paddle.device, "is_compiled_with_cuda", lambda: False)()
            and paddle.device.cuda.device_count() > 0
        )

        self._han_ocr = self._create_paddle_ocr("chinese_cht", effective_gpu)

        # Pillow 10+/13 compatibility shim for legacy Image.ANTIALIAS in VietOCR
        if Image is not None and not hasattr(Image, "ANTIALIAS"):
            resampling = getattr(Image, "Resampling", Image)
            Image.ANTIALIAS = getattr(resampling, "LANCZOS")  # type: ignore[attr-defined]

        # PyTorch 2.6+ defaults `weights_only=True`, which breaks legacy VietOCR checkpoints
        orig_torch_load = None
        torch_mod = None
        try:
            import torch  # type: ignore
            torch_mod = torch
            orig_torch_load = torch.load

            def _compat_torch_load(*args: Any, **kwargs: Any) -> Any:
                kwargs.setdefault("weights_only", False)
                return orig_torch_load(*args, **kwargs)

            torch.load = _compat_torch_load  # type: ignore[assignment]

            base_py = Path(sys.base_prefix) / ("python.exe" if os.name == "nt" else "bin/python")
            if (
                effective_gpu
                and not torch.cuda.is_available()
                and base_py.is_file()
                and str(base_py.resolve()) != str(Path(sys.executable).resolve())
            ):
                try:
                    probe = subprocess.call(
                        [str(base_py), "-c", "import torch, vietocr; assert torch.cuda.is_available()"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=15,
                    )
                    if probe == 0:
                        self._viet_predictor = _VietOCRCudaSubprocessProxy(str(base_py))
                        print(
                            f"[ocr_pipeline_kaggle] Initialized VietOCR vgg_transformer via CUDA proxy ({self._viet_predictor.device}).",
                            flush=True,
                        )
                except Exception as proxy_exc:
                    print(
                        f"[ocr_pipeline_kaggle] Notice: VietOCR CUDA proxy unavailable ({proxy_exc}); falling back in-process.",
                        flush=True,
                    )
                    self._viet_predictor = None

            if self._viet_predictor is None:
                from vietocr.tool.config import Cfg  # type: ignore
                from vietocr.tool.predictor import Predictor  # type: ignore

                cfg = Cfg.load_config_from_name("vgg_transformer")
                cfg["cnn"]["pretrained"] = True
                target_device = "cuda:0" if (effective_gpu and torch.cuda.is_available()) else "cpu"
                cfg["device"] = target_device
                self._viet_predictor = Predictor(cfg)
                print(
                    f"[ocr_pipeline_kaggle] Initialized VietOCR vgg_transformer on {target_device}.",
                    flush=True,
                )
        except Exception as exc:
            print(
                f"[ocr_pipeline_kaggle] Notice: VietOCR unavailable ({exc}); "
                "using PaddleOCR Vietnamese recognizer.",
                flush=True,
            )
            self._viet_predictor = None
        finally:
            if torch_mod is not None and orig_torch_load is not None:
                torch_mod.load = orig_torch_load

        if self._viet_predictor is None:
            self._viet_det_ocr = self._create_paddle_ocr("vi", effective_gpu)
        else:
            self._viet_det_ocr = None

    def _predict_viet_crop(
        self,
        ocr_input: Any,
        cx1: int,
        cy1: int,
        cx2: int,
        cy2: int,
        fallback_text: str,
        fallback_conf: float,
    ) -> Tuple[str, float]:
        """Run VietOCR inference on an `[cy1:cy2, cx1:cx2]` BGR crop, falling back safely on errors."""
        if (
            self._viet_predictor is None
            or Image is None
            or not hasattr(ocr_input, "shape")
            or cx2 <= cx1
            or cy2 <= cy1
        ):
            return fallback_text, fallback_conf
        crop_patch = ocr_input[cy1:cy2, cx1:cx2]
        if getattr(crop_patch, "size", 0) <= 0:
            return fallback_text, fallback_conf
        try:
            pil_patch = Image.fromarray(crop_patch[:, :, ::-1] if crop_patch.ndim == 3 else crop_patch)
            pred = self._viet_predictor.predict(pil_patch, return_prob=True)
            if isinstance(pred, tuple) and len(pred) == 2:
                return str(pred[0]), float(pred[1])
            return str(pred), fallback_conf
        except Exception:
            return fallback_text, fallback_conf

    def _predict_viet_crops_batch(
        self,
        ocr_input: Any,
        pending: Sequence[Dict[str, Any]],
    ) -> List[Tuple[str, float]]:
        """Run batched VietOCR inference for all pending `[cy1:cy2, cx1:cx2]` crops on a page."""
        if not pending:
            return []
        if self._viet_predictor is None or Image is None or not hasattr(ocr_input, "shape"):
            return [(str(p["fallback_text"]), float(p["fallback_conf"])) for p in pending]

        pil_list: List[Any] = []
        valid_indices: List[int] = []
        outputs: List[Tuple[str, float]] = [
            (str(p["fallback_text"]), float(p["fallback_conf"])) for p in pending
        ]
        for i, p in enumerate(pending):
            cx1, cy1, cx2, cy2 = int(p["cx1"]), int(p["cy1"]), int(p["cx2"]), int(p["cy2"])
            if cx2 <= cx1 or cy2 <= cy1:
                continue
            crop_patch = ocr_input[cy1:cy2, cx1:cx2]
            if getattr(crop_patch, "size", 0) <= 0:
                continue
            pil_list.append(Image.fromarray(crop_patch[:, :, ::-1] if crop_patch.ndim == 3 else crop_patch))
            valid_indices.append(i)

        if not pil_list:
            return outputs

        try:
            if hasattr(self._viet_predictor, "predict_batch"):
                pred_out = self._viet_predictor.predict_batch(pil_list, return_prob=True)
                texts, probs = pred_out
                for idx_pos, txt, prb in zip(valid_indices, texts, probs):
                    outputs[idx_pos] = (str(txt), float(prb))
                return outputs
        except Exception:
            pass

        for idx_pos in valid_indices:
            p = pending[idx_pos]
            outputs[idx_pos] = self._predict_viet_crop(
                ocr_input,
                int(p["cx1"]),
                int(p["cy1"]),
                int(p["cx2"]),
                int(p["cy2"]),
                fallback_text=str(p["fallback_text"]),
                fallback_conf=float(p["fallback_conf"]),
            )
        return outputs

    def recognize_page(
        self,
        cropped_image: Any,
        page_id: str,
        book_type: str,
        page_num: int,
        preprocess_meta: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Run dual-engine OCR on `cropped_image` (or mock OCR in `--dry-run` / `--mock` mode)."""
        if self.mock or cropped_image is None or isinstance(cropped_image, dict):
            return build_mock_ocr_for_page(
                page_id=page_id,
                book_type=book_type,
                page_num=page_num,
                preprocess_meta=preprocess_meta,
            )

        self._lazy_init_gpu_engines()

        # Normalize PIL.Image -> BGR numpy array expected by PaddleOCR
        ocr_input = cropped_image
        if np is not None and not hasattr(ocr_input, "shape") and Image is not None and isinstance(ocr_input, Image.Image):
            rgb = np.array(ocr_input.convert("RGB"))
            ocr_input = rgb[:, :, ::-1]

        crop_top_px = int(preprocess_meta.get("crop_top_px", 0))
        img_h, img_w = get_image_dimensions(ocr_input)

        # 1. PaddleOCR (`chinese_cht`) pass for detection + Classical Chinese recognition
        raw_han_lines = self._run_paddle_ocr(self._han_ocr, ocr_input)
        han_items: List[Dict[str, Any]] = []
        viet_items: List[Dict[str, Any]] = []

        if self._viet_predictor is not None:
            is_tvlt2 = book_type.upper().strip() == "TVLT2"
            pending_viet_crops: List[Dict[str, Any]] = []
            for bbox_pts, raw_text, raw_conf in raw_han_lines:
                x1, y1, x2, y2 = _box_bounds({"bbox": bbox_pts})
                ix1 = max(0, min(img_w - 1, int(x1)))
                iy1 = max(0, min(img_h - 1, int(y1)))
                ix2 = max(ix1 + 1, min(img_w, int(x2)))
                iy2 = max(iy1 + 1, min(img_h, int(y2)))
                cjk_cnt, latin_cnt = _count_cjk_and_latin(raw_text)

                if (
                    is_tvlt2
                    and x1 < 0.45 * img_w
                    and x2 > 0.55 * img_w
                    and cjk_cnt >= 2
                    and latin_cnt >= 4
                ):
                    # Split merged 2-column TVLT2 poetry row into left CJK and right Vietnamese crop
                    m_lead = re.match(
                        r"^\s*([\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\s，。、；：？！「」『』（）]+?)"
                        r"(?=\s*[A-Za-z\u00C0-\u024F\u1E00-\u1EFF])",
                        raw_text,
                    )
                    han_seg = m_lead.group(1).strip() if m_lead else raw_text
                    split_x = max(ix1 + 1, min(img_w, int(0.48 * img_w)))
                    han_bbox = [[ix1, iy1], [split_x, iy1], [split_x, iy2], [ix1, iy2]]
                    han_items.append({
                        "line_id": f"{page_id}_han_{len(han_items):03d}",
                        "bbox": han_bbox,
                        "bbox_original": _offset_bbox_to_original(han_bbox, crop_top_px),
                        "box_xyxy": [ix1, iy1, split_x, iy2],
                        "text": han_seg,
                        "confidence": round(float(raw_conf), 4),
                    })

                    vx1 = max(ix1, int(0.46 * img_w))
                    pad_y = max(4, int(0.14 * (iy2 - iy1)))
                    vy1 = max(0, iy1 - pad_y)
                    vy2 = min(img_h, iy2 + pad_y)
                    v_bbox = [[vx1, iy1], [ix2, iy1], [ix2, iy2], [vx1, iy2]]
                    pending_viet_crops.append({
                        "cx1": vx1, "cy1": vy1, "cx2": ix2, "cy2": vy2,
                        "bbox": v_bbox,
                        "box_xyxy": [vx1, iy1, ix2, iy2],
                        "fallback_text": raw_text,
                        "fallback_conf": float(raw_conf),
                    })
                elif cjk_cnt >= 1 and (latin_cnt == 0 or cjk_cnt >= 3 * latin_cnt):
                    han_items.append({
                        "line_id": f"{page_id}_han_{len(han_items):03d}",
                        "bbox": bbox_pts,
                        "bbox_original": _offset_bbox_to_original(bbox_pts, crop_top_px),
                        "box_xyxy": [ix1, iy1, ix2, iy2],
                        "text": raw_text,
                        "confidence": round(float(raw_conf), 4),
                    })
                else:
                    if cjk_cnt >= 1:
                        han_items.append({
                            "line_id": f"{page_id}_han_{len(han_items):03d}",
                            "bbox": bbox_pts,
                            "bbox_original": _offset_bbox_to_original(bbox_pts, crop_top_px),
                            "box_xyxy": [ix1, iy1, ix2, iy2],
                            "text": raw_text,
                            "confidence": round(float(raw_conf), 4),
                        })
                    pad_y = max(4, int(0.14 * (iy2 - iy1)))
                    pad_x = max(4, int(0.02 * (ix2 - ix1)))
                    cx1 = max(0, ix1 - pad_x)
                    cy1 = max(0, iy1 - pad_y)
                    cx2 = min(img_w, ix2 + pad_x)
                    cy2 = min(img_h, iy2 + pad_y)
                    pending_viet_crops.append({
                        "cx1": cx1, "cy1": cy1, "cx2": cx2, "cy2": cy2,
                        "bbox": bbox_pts,
                        "box_xyxy": [ix1, iy1, ix2, iy2],
                        "fallback_text": raw_text,
                        "fallback_conf": float(raw_conf),
                    })

            batch_preds = self._predict_viet_crops_batch(ocr_input, pending_viet_crops)
            for meta_crop, (recognized_text, v_conf) in zip(pending_viet_crops, batch_preds):
                v_bbox = meta_crop["bbox"]
                viet_items.append({
                    "line_id": f"{page_id}_viet_{len(viet_items):03d}",
                    "bbox": v_bbox,
                    "bbox_original": _offset_bbox_to_original(v_bbox, crop_top_px),
                    "box_xyxy": meta_crop["box_xyxy"],
                    "text": unicodedata.normalize("NFC", recognized_text),
                    "confidence": round(float(v_conf), 4),
                })
            return han_items, viet_items

        # Fallback path when VietOCR is unavailable: populate han_items + PaddleOCR(`vi`)
        for idx, (bbox_pts, text, conf) in enumerate(raw_han_lines):
            x1, y1, x2, y2 = _box_bounds({"bbox": bbox_pts})
            han_items.append({
                "line_id": f"{page_id}_han_{idx:03d}",
                "bbox": bbox_pts,
                "bbox_original": _offset_bbox_to_original(bbox_pts, crop_top_px),
                "box_xyxy": [int(x1), int(y1), int(x2), int(y2)],
                "text": text,
                "confidence": round(conf, 4),
            })

        raw_viet_lines = self._run_paddle_ocr(self._viet_det_ocr, ocr_input)
        for idx, (bbox_pts, fallback_text, det_conf) in enumerate(raw_viet_lines):
            x1, y1, x2, y2 = _box_bounds({"bbox": bbox_pts})
            ix1 = max(0, min(img_w - 1, int(x1)))
            iy1 = max(0, min(img_h - 1, int(y1)))
            ix2 = max(ix1 + 1, min(img_w, int(x2)))
            iy2 = max(iy1 + 1, min(img_h, int(y2)))
            viet_items.append({
                "line_id": f"{page_id}_viet_{idx:03d}",
                "bbox": bbox_pts,
                "bbox_original": _offset_bbox_to_original(bbox_pts, crop_top_px),
                "box_xyxy": [ix1, iy1, ix2, iy2],
                "text": unicodedata.normalize("NFC", fallback_text),
                "confidence": round(det_conf, 4),
            })

        return han_items, viet_items


# ---------------------------------------------------------------------------
# Traceable Output Storage (`02_ocr_tho/han/<page>.json` & `viet/<page>.json`)
# ---------------------------------------------------------------------------


def resolve_ocr_output_dirs(
    output_root: Union[str, Path],
    book_folder: Optional[str] = None,
) -> Tuple[Path, Path]:
    """Return `(han_dir, viet_dir)` under `02_ocr_tho/han` and `02_ocr_tho/viet`.

    Supports flat `output_root`, root ending with `<book_folder>`, or `<output_root>/deliverables/<book_folder>`.
    """
    root = Path(output_root)
    if book_folder:
        if root.name == book_folder:
            base = root / "02_ocr_tho"
        elif root.name == "deliverables":
            base = root / book_folder / "02_ocr_tho"
        else:
            base = root / "deliverables" / book_folder / "02_ocr_tho"
    elif root.name == "02_ocr_tho":
        base = root
    else:
        base = root / "02_ocr_tho"
    han_dir = base / "han"
    viet_dir = base / "viet"
    han_dir.mkdir(parents=True, exist_ok=True)
    viet_dir.mkdir(parents=True, exist_ok=True)
    return han_dir, viet_dir


def _resolve_book_folder(book_type: str, image_or_path: Any = None) -> str:
    """Resolve the deliverable folder name (e.g. `HVTT_HanVanTinhTuy`) for a page."""
    if isinstance(image_or_path, (str, Path)):
        parts = Path(image_or_path).parts
        for idx, part in enumerate(parts):
            if part == "deliverables" and idx + 1 < len(parts):
                return parts[idx + 1]
            if part.upper() in DELIVERABLE_DIR_TO_BOOK:
                return part
    book_key = BOOK_ALIAS_TO_LAYOUT.get(book_type.upper().strip(), book_type.upper().strip())
    return BOOK_DELIVERABLE_DIRS.get(book_key, f"{book_key}_Deliverable")


def save_page_ocr_outputs(
    output_root: Union[str, Path],
    page_id: str,
    book_type: str,
    page_num: int,
    preprocess_meta: Dict[str, Any],
    han_items: Sequence[Dict[str, Any]],
    viet_items: Sequence[Dict[str, Any]],
    layout_summary: Dict[str, Any],
    book_folder: Optional[str] = None,
) -> Tuple[Path, Path]:
    """Write raw OCR outputs to `02_ocr_tho/han/<page>.json` and `02_ocr_tho/viet/<page>.json`."""
    safe_page_id = re.sub(r"\.(?:png|jpg|jpeg|tif|tiff|json)$", "", page_id, flags=re.IGNORECASE)
    resolved_book_folder = book_folder or _resolve_book_folder(book_type)

    han_payload = {
        "page_id": safe_page_id,
        "book_type": book_type.upper(),
        "book_folder": resolved_book_folder,
        "page_num": page_num,
        "engine": "paddleocr_chinese_cht",
        "preprocess": preprocess_meta,
        "items": list(han_items),
        "layout_summary": {
            "layout_mode": layout_summary.get("layout_mode"),
            "chu_han_lines": layout_summary.get("chu_han_lines", []),
            "interlinear_triplets": layout_summary.get("interlinear_triplets", []),
        },
    }

    viet_payload = {
        "page_id": safe_page_id,
        "book_type": book_type.upper(),
        "book_folder": resolved_book_folder,
        "page_num": page_num,
        "engine": "vietocr_vgg_transformer",
        "preprocess": preprocess_meta,
        "items": list(viet_items),
        "layout_summary": {
            "layout_mode": layout_summary.get("layout_mode"),
            "phien_am_lines": layout_summary.get("phien_am_lines", []),
            "dich_nghia_lines": layout_summary.get("dich_nghia_lines", []),
            "dich_tho_lines": layout_summary.get("dich_tho_lines", []),
            "interlinear_triplets": layout_summary.get("interlinear_triplets", []),
            **(
                {"title_block": layout_summary["title_block"]}
                if "title_block" in layout_summary
                else {}
            ),
            **(
                {"dich_tho_y_centers": layout_summary["dich_tho_y_centers"]}
                if "dich_tho_y_centers" in layout_summary
                else {}
            ),
            **(
                {"has_dich_nghia": layout_summary["has_dich_nghia"]}
                if "has_dich_nghia" in layout_summary
                else {}
            ),
        },
    }

    # Primary output inside book folder or flat output_root (idempotent overwrite of <safe_page_id>.json)
    han_dir, viet_dir = resolve_ocr_output_dirs(output_root)
    han_path = han_dir / f"{safe_page_id}.json"
    viet_path = viet_dir / f"{safe_page_id}.json"

    # Avoid cross-book filename collision only in shared root outputs where multiple books mix
    root_path = Path(output_root)
    is_book_specific_root = (
        root_path.name == resolved_book_folder
        or root_path.name == "02_ocr_tho"
        or "deliverables" in root_path.parts
    )
    if not is_book_specific_root and han_path.exists():
        existing_book = ""
        try:
            existing_book = json.loads(han_path.read_text(encoding="utf-8")).get("book_type", "")
        except Exception:
            existing_book = ""
        if existing_book and existing_book.upper() != book_type.upper():
            flat_page_id = f"{book_type.upper()}_{safe_page_id}"
            han_path = han_dir / f"{flat_page_id}.json"
            viet_path = viet_dir / f"{flat_page_id}.json"

    with han_path.open("w", encoding="utf-8") as f:
        json.dump(han_payload, f, ensure_ascii=False, indent=2)

    with viet_path.open("w", encoding="utf-8") as f:
        json.dump(viet_payload, f, ensure_ascii=False, indent=2)

    # Deliverable per-book mirror when writing to a shared workspace/working directory
    if not is_book_specific_root:
        deliv_han_dir, deliv_viet_dir = resolve_ocr_output_dirs(
            output_root, book_folder=resolved_book_folder
        )
        deliv_han_path = deliv_han_dir / f"{safe_page_id}.json"
        deliv_viet_path = deliv_viet_dir / f"{safe_page_id}.json"
        with deliv_han_path.open("w", encoding="utf-8") as f:
            json.dump(han_payload, f, ensure_ascii=False, indent=2)
        with deliv_viet_path.open("w", encoding="utf-8") as f:
            json.dump(viet_payload, f, ensure_ascii=False, indent=2)
        return deliv_han_path, deliv_viet_path

    return han_path, viet_path


def process_single_page(
    engine: KaggleDualOCREngine,
    image_or_path: Any,
    output_root: Union[str, Path],
    page_id: str,
    book_type: str = "TVLT2",
    page_num: int = 2,
    header_ratio: float = DEFAULT_HEADER_CROP_RATIO,
    book_folder: Optional[str] = None,
) -> Dict[str, Any]:
    """Run preprocessing, dual-engine OCR, layout grouping, and JSON persistence for one page."""
    loaded_image: Any = image_or_path
    resolved_book_folder = book_folder or _resolve_book_folder(book_type, image_or_path)
    if isinstance(image_or_path, (str, Path)):
        img_path = Path(image_or_path)
        if img_path.is_file() and img_path.stat().st_size > 0:
            try:
                if cv2 is not None:
                    loaded_image = cv2.imread(str(img_path))
                    if loaded_image is None:
                        loaded_image = {"width": 2000, "height": 2800}
                elif Image is not None:
                    loaded_image = Image.open(img_path)
                else:
                    loaded_image = {"width": 2000, "height": 2800}
            except Exception:
                loaded_image = {"width": 2000, "height": 2800}
        else:
            loaded_image = {"width": 2000, "height": 2800}
    elif loaded_image is None:
        loaded_image = {"width": 2000, "height": 2800}

    cropped_img, preprocess_meta = preprocess_page_image(
        loaded_image,
        book_type=book_type,
        header_ratio=header_ratio,
    )

    han_items, viet_items = engine.recognize_page(
        cropped_image=cropped_img,
        page_id=page_id,
        book_type=book_type,
        page_num=page_num,
        preprocess_meta=preprocess_meta,
    )

    page_w = int(preprocess_meta.get("effective_width") or 2000)
    layout_summary = group_layout_blocks(
        han_items=han_items,
        viet_items=viet_items,
        book_type=book_type,
        page_num=page_num,
        page_width=page_w,
    )

    han_json_path, viet_json_path = save_page_ocr_outputs(
        output_root=output_root,
        page_id=page_id,
        book_type=book_type,
        page_num=page_num,
        preprocess_meta=preprocess_meta,
        han_items=han_items,
        viet_items=viet_items,
        layout_summary=layout_summary,
        book_folder=resolved_book_folder,
    )

    return {
        "page_id": page_id,
        "book_type": book_type.upper(),
        "book_folder": resolved_book_folder,
        "page_num": page_num,
        "han_json": str(han_json_path),
        "viet_json": str(viet_json_path),
        "preprocess": preprocess_meta,
        "han_items": han_items,
        "viet_items": viet_items,
        "layout_summary": layout_summary,
    }


# ---------------------------------------------------------------------------
# CLI Entrypoint (Supports Kaggle GPU Execution & Local `--dry-run` / `--mock`)
# ---------------------------------------------------------------------------


def _infer_book_and_page(filename: str, default_book: str = "TVLT2", default_page: int = 2) -> Tuple[str, int]:
    """Infer `(book_type, page_num)` from an image path like `deliverables/HVTT_HanVanTinhTuy/01_nguon/page_012.png`."""
    path_obj = Path(filename)
    for part in path_obj.parts:
        part_upper = part.upper()
        if part_upper in DELIVERABLE_DIR_TO_BOOK:
            book = DELIVERABLE_DIR_TO_BOOK[part_upper]
            break
    else:
        upper = str(filename).upper()
        book = default_book
        for candidate in BOOK_TYPES:
            if candidate in upper:
                book = candidate
                break

    stem = path_obj.stem
    matches = re.findall(r"(\d+)", stem)
    page_num = int(matches[-1]) if matches else default_page
    return book, page_num


def _discover_input_images(input_dir: Path) -> List[Path]:
    """Discover page images under `deliverables/*/01_nguon/*.png` or anywhere under `input_dir`."""
    candidate_roots = [input_dir]
    if not input_dir.exists() and Path("/kaggle/input").is_dir():
        candidate_roots.append(Path("/kaggle/input"))

    discovered: List[Path] = []
    seen_resolved: set[str] = set()

    for root in candidate_roots:
        if not root.is_dir():
            continue
        # Prioritize deliverables/*/01_nguon/*
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.tif", "*.tiff"):
            for p in sorted(root.rglob(f"deliverables/*/01_nguon/{ext}")):
                key = str(p)
                if key not in seen_resolved:
                    seen_resolved.add(key)
                    discovered.append(p)
        if discovered:
            return discovered
        # Fallback to any image in root
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.tif", "*.tiff"):
            for p in sorted(root.rglob(ext)):
                key = str(p)
                if key not in seen_resolved:
                    seen_resolved.add(key)
                    discovered.append(p)
        if discovered:
            return discovered

    return discovered


def _write_jsonl_records(output_dir: Path, results: Sequence[Dict[str, Any]]) -> None:
    """Write `ocr_results.jsonl` both per-book (`deliverables/<book>/02_ocr_tho/ocr_results.jsonl`) and globally."""
    by_book: Dict[str, List[Dict[str, Any]]] = {}
    for res in results:
        b_folder = str(res.get("book_folder") or _resolve_book_folder(str(res.get("book_type", "TVLT2"))))
        by_book.setdefault(b_folder, []).append(res)

    for b_folder, book_results in by_book.items():
        book_han_dir, _ = resolve_ocr_output_dirs(output_dir, book_folder=b_folder)
        book_jsonl_path = book_han_dir.parent / "ocr_results.jsonl"
        book_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with book_jsonl_path.open("w", encoding="utf-8") as f:
            for item in book_results:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    global_jsonl_paths = [
        output_dir / "02_ocr_tho" / "ocr_results.jsonl",
    ]
    for g_path in global_jsonl_paths:
        g_path.parent.mkdir(parents=True, exist_ok=True)
        with g_path.open("w", encoding="utf-8") as f:
            for item in results:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _has_nvidia_cuda_runtime() -> bool:
    """Return True if an NVIDIA GPU driver (`nvidia-smi` or `libcuda.so.1`) is available."""
    try:
        if subprocess.call(["nvidia-smi"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            return True
    except OSError:
        pass
    try:
        import ctypes
        ctypes.CDLL("libcuda.so.1")
        return True
    except OSError:
        return False


def _install_kaggle_dependencies_if_needed() -> None:
    """Install PaddlePaddle, PaddleOCR, and best-effort VietOCR inside a Kaggle kernel."""
    pip_base = [sys.executable, "-m", "pip", "install", "-q"]
    subprocess.check_call([*pip_base, "opencv-python-headless", "paddleocr"])

    has_cuda = _has_nvidia_cuda_runtime()
    paddle_installed = subprocess.call(
        [sys.executable, "-c", "import paddle"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ) == 0
    if not paddle_installed:
        installed = False
        if has_cuda:
            gpu_indexes = [
                "https://www.paddlepaddle.org.cn/packages/stable/cu126/",
                "https://www.paddlepaddle.org.cn/packages/stable/cu118/",
            ]
            for idx_url in gpu_indexes:
                if subprocess.call([*pip_base, "paddlepaddle-gpu", "-i", idx_url]) == 0:
                    installed = True
                    break
            if not installed and subprocess.call([*pip_base, "paddlepaddle-gpu"]) == 0:
                installed = True
        if not installed:
            print("[install] Installing CPU paddlepaddle wheel.", flush=True)
            subprocess.check_call([*pip_base, "paddlepaddle"])

    verify_cmd = [
        sys.executable,
        "-c",
        "import paddle; from paddleocr import PaddleOCR",
    ]
    if subprocess.call(verify_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0 and has_cuda:
        print(
            "[install] PaddleOCR import verification failed on GPU runtime (likely NCCL/CUDA mismatch); "
            "upgrading nvidia-nccl-cu12>=2.27.3...",
            flush=True,
        )
        subprocess.call([*pip_base, "--upgrade", "nvidia-nccl-cu12>=2.27.3"])

    subprocess.check_call([*pip_base, "einops", "gdown"])
    vietocr_rc = subprocess.call([*pip_base, "--no-deps", "vietocr"])
    if vietocr_rc != 0:
        print(
            f"[install] Warning: `pip install --no-deps vietocr` exited with {vietocr_rc}; "
            "falling back to PaddleOCR Vietnamese recognizer.",
            flush=True,
        )
    else:
        viet_verify = subprocess.run(
            [
                sys.executable,
                "-c",
                "from vietocr.tool.config import Cfg; from vietocr.tool.predictor import Predictor",
            ],
            capture_output=True,
            text=True,
        )
        if viet_verify.returncode == 0:
            print("[install] VietOCR (with --no-deps) verified cleanly.", flush=True)
        else:
            print(
                "[install] Warning: VietOCR import verification failed: "
                f"{(viet_verify.stderr or viet_verify.stdout).strip()}",
                flush=True,
            )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Kaggle GPU & Local Mock OCR Pipeline for Hán-Việt Parallel Corpus."
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="/kaggle/input/han-viet-parallel-corpus-pages",
        help="Input directory containing rendered 300 DPI page images.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="/kaggle/working" if Path("/kaggle/working").exists() else ".",
        help="Base output directory where `deliverables/<book>/02_ocr_tho/{han,viet}` and `ocr_results.jsonl` are written.",
    )
    parser.add_argument(
        "--book-type",
        type=str,
        default="ALL",
        choices=["ALL", "HVTT", "TLTVN", "TVLT2", "VPO_01", "VPO_02", "VPO_03"],
        help="Book type layout rule to apply.",
    )
    parser.add_argument(
        "--header-ratio",
        type=float,
        default=DEFAULT_HEADER_CROP_RATIO,
        help="Top running header crop ratio (default: 0.07).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run locally in deterministic mock mode without requiring GPU packages.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Alias for --dry-run (uses deterministic mock OCR engines).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maximum number of pages to process (useful for fast pilot runs).",
    )
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Install PaddleOCR and VietOCR via pip before running (for Kaggle GPU kernels).",
    )
    parser.add_argument(
        "--pilot-only",
        action="store_true",
        help="Restrict image processing to verified pilot pages defined in config/book_manifest.json.",
    )
    parser.add_argument(
        "--run-alignment",
        action="store_true",
        help="Run full corpus post-processing & alignment (`src.corpus_pipeline`) after OCR completes.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip pages whose non-mock han/viet OCR JSON files already exist in output_dir.",
    )

    args = parser.parse_args(argv)
    is_mock = bool(args.dry_run or args.mock)

    if args.install_deps and not is_mock:
        _install_kaggle_dependencies_if_needed()

    pilot_pages_map: Dict[str, set[int]] = {}
    if args.pilot_only:
        for cand_manifest in (
            Path(__file__).resolve().parent.parent / "config" / "book_manifest.json",
            Path(args.input_dir) / "config" / "book_manifest.json",
            Path(args.input_dir) / "book_manifest.json",
        ):
            if cand_manifest.is_file():
                m_data = json.loads(cand_manifest.read_text(encoding="utf-8"))
                for b_k, b_cfg in m_data.get("books", {}).items():
                    pset = {int(p) for p in b_cfg.get("pilot_pages", [])}
                    pilot_pages_map[b_k] = pset
                    layout_k = BOOK_ALIAS_TO_LAYOUT.get(b_k.upper())
                    if layout_k:
                        pilot_pages_map[layout_k] = pset
                break

    engine = KaggleDualOCREngine(use_gpu=not is_mock, mock=is_mock)
    input_path = Path(args.input_dir)
    discovered_files = _discover_input_images(input_path)

    req_type = "ALL" if args.book_type == "ALL" else BOOK_ALIAS_TO_LAYOUT.get(args.book_type.upper(), args.book_type.upper())

    # Filter by book_type (and --pilot-only) FIRST before applying --max-pages
    filtered_files: List[Tuple[Path, str, int]] = []
    for img_file in discovered_files:
        inferred_book, page_num = _infer_book_and_page(
            str(img_file),
            default_book="TVLT2" if req_type == "ALL" else req_type,
        )
        if req_type != "ALL" and inferred_book != req_type:
            continue
        if args.pilot_only and inferred_book in pilot_pages_map and page_num not in pilot_pages_map[inferred_book]:
            continue
        filtered_files.append((img_file, inferred_book, page_num))

    if args.max_pages is not None and args.max_pages > 0:
        filtered_files = filtered_files[:args.max_pages]

    results: List[Dict[str, Any]] = []

    if filtered_files:
        import time as _time
        t_batch_start = _time.perf_counter()
        total_pages = len(filtered_files)
        for idx_page, (img_file, inferred_book, page_num) in enumerate(filtered_files, start=1):
            book_folder = _resolve_book_folder(inferred_book, img_file)
            safe_stem = re.sub(r"\.(?:png|jpg|jpeg|tif|tiff|json)$", "", img_file.stem, flags=re.IGNORECASE)
            if args.skip_existing and not is_mock:
                chk_han_dir, chk_viet_dir = resolve_ocr_output_dirs(args.output_dir, book_folder=book_folder)
                chk_han = chk_han_dir / f"{safe_stem}.json"
                chk_viet = chk_viet_dir / f"{safe_stem}.json"
                if chk_han.is_file() and chk_viet.is_file():
                    try:
                        existing_h = json.loads(chk_han.read_text(encoding="utf-8"))
                        if "mock" not in str(existing_h.get("engine", "")).lower():
                            if idx_page % 25 == 0 or idx_page == total_pages:
                                print(
                                    f"[ocr] [{idx_page}/{total_pages}] skipped existing {book_folder}/{img_file.name}",
                                    flush=True,
                                )
                            continue
                    except Exception:
                        pass

            t_page_start = _time.perf_counter()
            res = process_single_page(
                engine=engine,
                image_or_path=img_file,
                output_root=args.output_dir,
                page_id=img_file.stem,
                book_type=inferred_book,
                page_num=page_num,
                header_ratio=args.header_ratio,
                book_folder=book_folder,
            )
            results.append(res)
            page_sec = _time.perf_counter() - t_page_start
            elapsed_total = _time.perf_counter() - t_batch_start
            done_new = len(results)
            avg_sec = elapsed_total / max(1, done_new)
            eta_min = (total_pages - idx_page) * avg_sec / 60.0
            print(
                f"[ocr] [{idx_page}/{total_pages}] {book_folder}/{img_file.name} (p.{page_num}) | "
                f"han={len(res.get('han_items', []))} viet={len(res.get('viet_items', []))} | "
                f"{page_sec:.2f}s (avg {avg_sec:.2f}s/p, ETA {eta_min:.1f}m)",
                flush=True,
            )
    elif is_mock:
        # In dry-run/mock mode with no input images on disk, run sample pages for all requested books
        sample_books = list(BOOK_TYPES) if args.book_type == "ALL" else [args.book_type]
        for b_type in sample_books:
            sample_page_num = 2 if b_type == "HVTT" else 4
            page_id = f"{b_type}_page_{sample_page_num:03d}"
            mock_img = {
                "width": 2000,
                "height": 2800,
                "footnote_separator_y": 2150 if b_type == "TLTVN" else None,
            }
            res = process_single_page(
                engine=engine,
                image_or_path=mock_img,
                output_root=args.output_dir,
                page_id=page_id,
                book_type=b_type,
                page_num=sample_page_num,
                header_ratio=args.header_ratio,
                book_folder=BOOK_DELIVERABLE_DIRS.get(b_type),
            )
            results.append(res)

    out_dir_path = Path(args.output_dir)
    if hasattr(engine._viet_predictor, "close"):
        engine._viet_predictor.close()
    _write_jsonl_records(out_dir_path, results)

    run_mode_label = "mock" if is_mock else "kaggle_gpu"
    summary_path = out_dir_path / "02_ocr_tho" / "ocr_run_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "mode": run_mode_label,
                "pages_processed": len(results),
                "pages": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    by_book_meta: Dict[str, List[Dict[str, Any]]] = {}
    for res in results:
        b_folder = str(res.get("book_folder") or _resolve_book_folder(str(res.get("book_type", "TVLT2"))))
        by_book_meta.setdefault(b_folder, []).append({
            "page_id": res.get("page_id"),
            "book_type": res.get("book_type"),
            "page_num": res.get("page_num"),
            "han_json": res.get("han_json"),
            "viet_json": res.get("viet_json"),
        })
    for b_folder, book_pages in by_book_meta.items():
        book_han_dir, _ = resolve_ocr_output_dirs(out_dir_path, book_folder=b_folder)
        book_summary_path = book_han_dir.parent / "ocr_run_summary.json"
        if book_summary_path != summary_path:
            book_summary_path.parent.mkdir(parents=True, exist_ok=True)
            with book_summary_path.open("w", encoding="utf-8") as bf:
                json.dump(
                    {
                        "mode": run_mode_label,
                        "book_folder": b_folder,
                        "pages_processed": len(book_pages),
                        "pages": book_pages,
                    },
                    bf,
                    ensure_ascii=False,
                    indent=2,
                )

    print(f"[ocr_pipeline_kaggle] Processed {len(results)} page(s) (mode={'mock' if is_mock else 'gpu'}).")

    # Optionally run end-to-end post-processing & alignment (auto-enabled inside Kaggle GPU kernel if src/ is staged)
    should_align = bool(args.run_alignment or (not is_mock and KaggleDualOCREngine._is_kaggle_runtime()))
    if should_align:
        candidate_code_roots = [
            Path(__file__).resolve().parent.parent,
            input_path,
            Path("/kaggle/input/han-viet-parallel-corpus-pages"),
        ]
        kaggle_input_dir = Path("/kaggle/input")
        if kaggle_input_dir.is_dir():
            for found_cp in sorted(kaggle_input_dir.glob("**/src/corpus_pipeline.py")):
                cand_root = found_cp.parent.parent
                if cand_root not in candidate_code_roots:
                    candidate_code_roots.append(cand_root)

        for root_cand in candidate_code_roots:
            if (root_cand / "src" / "corpus_pipeline.py").is_file():
                if str(root_cand) not in sys.path:
                    sys.path.insert(0, str(root_cand))
                try:
                    import kaggle_ocr.ocr_pipeline_kaggle  # type: ignore  # noqa: F401
                except ImportError:
                    import types
                    pkg_mod = sys.modules.get("kaggle_ocr")
                    if pkg_mod is None:
                        pkg_mod = types.ModuleType("kaggle_ocr")
                        pkg_mod.__path__ = [str(Path(__file__).resolve().parent)]  # type: ignore[attr-defined]
                        sys.modules["kaggle_ocr"] = pkg_mod
                    self_mod = sys.modules[__name__]
                    setattr(pkg_mod, "ocr_pipeline_kaggle", self_mod)
                    sys.modules["kaggle_ocr.ocr_pipeline_kaggle"] = self_mod
                from src.corpus_pipeline import run_corpus_from_ocr  # type: ignore

                supp_rel = Path("deliverables") / "TVLT2_ThoVanLyTran2" / "01_nguon" / "bai_03_thien_tong_chi_nam_tu_dich_nghia.txt"
                src_supp = root_cand / supp_rel
                dst_supp = out_dir_path / supp_rel
                if src_supp.is_file() and not dst_supp.is_file():
                    dst_supp.parent.mkdir(parents=True, exist_ok=True)
                    dst_supp.write_text(src_supp.read_text(encoding="utf-8"), encoding="utf-8")

                manifest_candidate = (
                    root_cand / "config" / "book_manifest.json"
                    if (root_cand / "config" / "book_manifest.json").is_file()
                    else None
                )
                align_summary = run_corpus_from_ocr(
                    workspace_root=out_dir_path,
                    ocr_root=out_dir_path,
                    manifest_path=manifest_candidate,
                    book_filter=None if args.book_type == "ALL" else args.book_type,
                )
                print("[ocr_pipeline_kaggle] End-to-end alignment summary:")
                print(json.dumps(align_summary, ensure_ascii=False, indent=2))
                break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
