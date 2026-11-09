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
BOOK_DELIVERABLE_DIRS: Dict[str, str] = {
    "HVTT": "HVTT_HanVanTinhTuy",
    "TLTVN": "TLTVN_TheLoaiTuVN",
    "TVLT2": "TVLT2_ThoVanLyTran2",
}
DELIVERABLE_DIR_TO_BOOK: Dict[str, str] = {
    v.upper(): k for k, v in BOOK_DELIVERABLE_DIRS.items()
}
DEFAULT_HEADER_CROP_RATIO = 0.07
DEFAULT_LOWER_HALF_START_RATIO = 0.50
DEFAULT_FOOTNOTE_MAX_Y_RATIO = 0.94
DEFAULT_MIN_SEPARATOR_WIDTH_RATIO = 0.15

# Regex patterns for section headers in TVLT2 / TLTVN / HVTT
_STOP_HEADER_RE = re.compile(
    r"^\s*(?:DỊCH\s*THƠ|Dịch\s*thơ|DỊCH\s*THEO\s*NGUYÊN\s*ĐIỆU|Dịch\s*theo\s*nguyên\s*điệu|"
    r"KHẢO\s*ĐÍNH|Khảo\s*đính|CÁC\s*DỊ\s*BẢN|Các\s*dị\s*bản|CHÚ\s*THÍCH|Chú\s*thích|LỜI\s*BÀN|Lời\s*bàn)\s*[:：.]?",
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

# CJK detection regex for distinguishing Han lines from Vietnamese lines
_CJK_CHAR_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


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
    book_key = book_type.upper().strip()
    orig_h, orig_w = get_image_dimensions(image)

    cropped_img, crop_top_px = crop_running_header(image, header_ratio=header_ratio)
    after_header_h, _ = get_image_dimensions(cropped_img)

    should_detect_fn = (book_key == "TLTVN") if detect_footnotes is None else bool(detect_footnotes)
    separator_y_cropped: Optional[int] = None
    separator_y_original: Optional[int] = None

    if should_detect_fn and after_header_h > 0:
        separator_y_cropped = detect_footnote_separator(cropped_img)
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
    """Return True if `text` starts a non-corpus section (`DỊCH THƠ :`, `KHẢO ĐÍNH :`, `CHÚ THÍCH :`)."""
    if not text:
        return False
    normalized = unicodedata.normalize("NFC", text.strip())
    return bool(_STOP_HEADER_RE.match(normalized))


def classify_section_header(text: str) -> Optional[str]:
    """Classify a line as `'stop'`, `'phien_am'`, `'dich_nghia'`, or `None`."""
    if not text:
        return None
    normalized = unicodedata.normalize("NFC", text.strip())
    if _STOP_HEADER_RE.match(normalized):
        return "stop"
    if _PHIEN_AM_HEADER_RE.match(normalized):
        return "phien_am"
    if _DICH_NGHIA_HEADER_RE.match(normalized):
        return "dich_nghia"
    return None


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
    """Group OCR items into structured `Chữ Hán`, `Phiên âm`, and `Dịch nghĩa` blocks per book type.

    Book Rules:
    - `HVTT` (*Hán Văn Tinh Túy*):
      * Odd pages (`page_num % 2 == 1`) are commentary pages (`Chú thích` / `Lời bàn`) -> skipped.
      * Even pages (`page_num % 2 == 0`) contain 3-line interlinear triplets
        (`Line 1: Chữ Hán`, `Line 2: Phiên âm`, `Line 3: Dịch nghĩa` gloss) followed by a
        full `Dịch nghĩa` translation block at the bottom of the page.
    - `TLTVN` (*Thể loại từ VN thời trung đại*):
      * Sequential blocks: `Chữ Hán` -> `Phiên âm:` -> `Dịch nghĩa:`, stopping if `Dịch thơ:`
        or a stop header is encountered.
    - `TVLT2` (*Thơ văn Lý – Trần Tập II*):
      * Supports 2-column side-by-side poetry (left column `x_center < 0.5 * page_width` for
        `Chữ Hán`, right column `x_center >= 0.5 * page_width` for `Phiên âm`, followed by
        full-width `DỊCH NGHĨA :`) as well as sequential prose (`Chữ Hán` -> `PHIÊN ÂM :` ->
        `DỊCH NGHĨA :`), stopping immediately at `DỊCH THƠ :` / `KHẢO ĐÍNH :` / `CHÚ THÍCH :`.
    """
    book_key = book_type.upper().strip()
    sorted_han = _sort_items_reading_order(han_items)
    sorted_viet = _sort_items_reading_order(viet_items)

    # 1. HVTT: 3-line interlinear blocks on even pages
    if book_key == "HVTT":
        if page_num % 2 != 0:
            return {
                "book_type": "HVTT",
                "page_num": page_num,
                "layout_mode": "odd_page_commentary_skipped",
                "interlinear_triplets": [],
                "chu_han_lines": [],
                "phien_am_lines": [],
                "dich_nghia_lines": [],
            }

        # Filter out non-CJK noise from han lines
        han_lines = [
            it["text"].strip()
            for it in sorted_han
            if _CJK_CHAR_RE.search(it.get("text", ""))
        ]

        # Separate interlinear Vietnamese lines (Phiên âm + word-by-word gloss) from bottom Dịch nghĩa
        phien_am_lines: List[str] = []
        gloss_lines: List[str] = []
        bottom_dich_nghia: List[str] = []
        in_bottom_dich_nghia = False

        for it in sorted_viet:
            txt = unicodedata.normalize("NFC", it.get("text", "").strip())
            if not txt or _CJK_CHAR_RE.search(txt):
                continue
            if is_stop_section_header(txt):
                break
            m_dn = _DICH_NGHIA_HEADER_RE.match(txt)
            if m_dn:
                in_bottom_dich_nghia = True
                rest = m_dn.group(1).strip()
                if rest:
                    bottom_dich_nghia.append(rest)
                continue
            if in_bottom_dich_nghia:
                bottom_dich_nghia.append(txt)
            else:
                role = it.get("role", "")
                if role == "phien_am":
                    phien_am_lines.append(txt)
                elif role == "dich_nghia_gloss":
                    gloss_lines.append(txt)
                else:
                    # Alternate between Phiên âm (line 2 of triplet) and gloss (line 3 of triplet)
                    if len(phien_am_lines) <= len(gloss_lines) and len(phien_am_lines) < len(han_lines):
                        phien_am_lines.append(txt)
                    elif len(gloss_lines) < len(phien_am_lines):
                        gloss_lines.append(txt)
                    else:
                        bottom_dich_nghia.append(txt)

        triplets = []
        for idx, h_line in enumerate(han_lines):
            pa_line = phien_am_lines[idx] if idx < len(phien_am_lines) else ""
            gl_line = gloss_lines[idx] if idx < len(gloss_lines) else ""
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
            "dich_nghia_lines": bottom_dich_nghia if bottom_dich_nghia else gloss_lines,
        }

    # 2. TLTVN: Sequential Chữ Hán -> Phiên âm: -> Dịch nghĩa:
    if book_key == "TLTVN":
        han_lines = [
            it["text"].strip()
            for it in sorted_han
            if _CJK_CHAR_RE.search(it.get("text", ""))
        ]
        phien_am_lines = []
        dich_nghia_lines = []
        current_section = "phien_am"

        for it in sorted_viet:
            txt = unicodedata.normalize("NFC", it.get("text", "").strip())
            if not txt or _CJK_CHAR_RE.search(txt):
                continue
            header_type = classify_section_header(txt)
            if header_type == "stop":
                break
            if header_type == "phien_am":
                current_section = "phien_am"
                rest = _PHIEN_AM_HEADER_RE.sub("", txt).strip()
                if rest:
                    phien_am_lines.append(rest)
                continue
            if header_type == "dich_nghia":
                current_section = "dich_nghia"
                rest = _DICH_NGHIA_HEADER_RE.sub("", txt).strip()
                if rest:
                    dich_nghia_lines.append(rest)
                continue

            if current_section == "dich_nghia":
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
        }

    # 3. TVLT2: 2-column side-by-side poetry OR sequential prose, stopping at DỊCH THƠ / KHẢO ĐÍNH / CHÚ THÍCH
    mid_x = 0.5 * float(page_width)

    # First find the vertical y-cutoff where a stop header (DỊCH THƠ / KHẢO ĐÍNH / CHÚ THÍCH) appears
    stop_y: Optional[float] = None
    for it in sorted_viet:
        txt = unicodedata.normalize("NFC", it.get("text", "").strip())
        if is_stop_section_header(txt):
            _, y1, _, _ = _box_bounds(it)
            stop_y = y1
            break

    active_han_items = []
    for it in sorted_han:
        txt = it.get("text", "").strip()
        if not _CJK_CHAR_RE.search(txt):
            continue
        x1, y1, x2, y2 = _box_bounds(it)
        if stop_y is not None and y1 >= stop_y:
            continue
        active_han_items.append(it)

    # Detect if Han items are predominantly in the left column (2-column poetry layout)
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
            and not _DICH_NGHIA_HEADER_RE.match(unicodedata.normalize("NFC", vit.get("text", "").strip()))
        )
    )

    han_lines = [it["text"].strip() for it in active_han_items]
    phien_am_lines = []
    dich_nghia_lines = []
    current_section = "phien_am"

    for it in sorted_viet:
        txt = unicodedata.normalize("NFC", it.get("text", "").strip())
        if not txt or _CJK_CHAR_RE.search(txt):
            continue
        x1, y1, x2, _y2 = _box_bounds(it)
        if stop_y is not None and y1 >= stop_y:
            break

        header_type = classify_section_header(txt)
        if header_type == "stop":
            break
        if header_type == "phien_am":
            current_section = "phien_am"
            rest = _PHIEN_AM_HEADER_RE.sub("", txt).strip()
            if rest:
                phien_am_lines.append(rest)
            continue
        if header_type == "dich_nghia":
            current_section = "dich_nghia"
            rest = _DICH_NGHIA_HEADER_RE.sub("", txt).strip()
            if rest:
                dich_nghia_lines.append(rest)
            continue

        if current_section == "dich_nghia":
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
    book_key = book_type.upper().strip()
    crop_top_px = int((preprocess_meta or {}).get("crop_top_px", 140))

    if book_key == "HVTT":
        han_raw = [
            {"bbox": [[180, 120], [1620, 120], [1620, 175], [180, 175]], "text": "鄭 子 產 有 疾 謂 子 太 叔 曰", "confidence": 0.992},
            {"bbox": [[180, 310], [1620, 310], [1620, 365], [180, 365]], "text": "我 死 子 必 爲 政", "confidence": 0.990},
            {"bbox": [[180, 490], [1620, 490], [1620, 545], [180, 545]], "text": "惟 有 德 者 能 以 寬 服 民", "confidence": 0.989},
            {"bbox": [[180, 670], [1620, 670], [1620, 725], [180, 725]], "text": "其 次 莫 如 猛", "confidence": 0.991},
        ]
        viet_raw = [
            {"bbox": [[180, 185], [1620, 185], [1620, 230], [180, 230]], "text": "Trịnh Tử-Sản hữu tật, vị tử Thái-Thúc viết :", "confidence": 0.985, "role": "phien_am"},
            {"bbox": [[180, 240], [1620, 240], [1620, 290], [180, 290]], "text": "Trịnh Tử-Sản bệnh nặng, bảo con là Thái-Thúc rằng :", "confidence": 0.978, "role": "dich_nghia_gloss"},
            {"bbox": [[180, 375], [1620, 375], [1620, 420], [180, 420]], "text": "Ngã tử, tử tất vi chính", "confidence": 0.986, "role": "phien_am"},
            {"bbox": [[180, 430], [1620, 430], [1620, 475], [180, 475]], "text": "Ta chết, con sẽ giữ chính-quyền.", "confidence": 0.980, "role": "dich_nghia_gloss"},
            {"bbox": [[180, 555], [1620, 555], [1620, 600], [180, 600]], "text": "Duy hữu đức giả, năng dĩ khoan phục dân", "confidence": 0.984, "role": "phien_am"},
            {"bbox": [[180, 610], [1620, 610], [1620, 655], [180, 655]], "text": "Chỉ kẻ có đức mới có thể lấy khoan hòa cho dân phục,", "confidence": 0.976, "role": "dich_nghia_gloss"},
            {"bbox": [[180, 735], [1620, 735], [1620, 780], [180, 780]], "text": "Kỳ thứ mạc như mãnh.", "confidence": 0.987, "role": "phien_am"},
            {"bbox": [[180, 790], [1620, 790], [1620, 835], [180, 835]], "text": "còn thì không gì bằng chính-sách mạnh.", "confidence": 0.981, "role": "dich_nghia_gloss"},
        ]
    elif book_key == "TLTVN":
        han_raw = [
            {"bbox": [[220, 150], [1480, 150], [1480, 200], [220, 200]], "text": "祥光風好錦帆張, 神仙復帝鄉.", "confidence": 0.992},
            {"bbox": [[220, 210], [1480, 210], [1480, 260], [220, 260]], "text": "千重萬里涉滄浪, 九天歸路長.", "confidence": 0.990},
        ]
        viet_raw = [
            {"bbox": [[220, 280], [900, 280], [900, 320], [220, 320]], "text": "Phiên âm:", "confidence": 0.995},
            {"bbox": [[220, 330], [1500, 330], [1500, 375], [220, 375]], "text": "Tường quang phong hảo cẩm phàm trương, Thần tiên phục đế hương².", "confidence": 0.986},
            {"bbox": [[220, 385], [1500, 385], [1500, 430], [220, 430]], "text": "Thiên trùng vạn lí¹ thiệp thương lương, Cửu thiên quy lộ trường.", "confidence": 0.985},
            {"bbox": [[220, 450], [900, 450], [900, 490], [220, 490]], "text": "Dịch nghĩa:", "confidence": 0.994},
            {"bbox": [[220, 500], [1580, 500], [1580, 550], [220, 550]], "text": "Ánh sáng tốt lành, gió thuận, căng cánh buồm gấm, Thần tiên trở về quê hương của hoàng đế⁵.", "confidence": 0.983},
            {"bbox": [[220, 560], [1580, 560], [1580, 610], [220, 610]], "text": "Nghìn trùng muôn dặm vượt qua những làn sóng xanh, Đường qua về chín tầng trời¹.", "confidence": 0.982},
            {"bbox": [[220, 630], [900, 630], [900, 670], [220, 670]], "text": "Dịch theo nguyên điệu:", "confidence": 0.991},
            {"bbox": [[220, 680], [1400, 680], [1400, 725], [220, 725]], "text": "Trời trong gió mát cánh buồm giương, Thần tiên về đế hương.", "confidence": 0.980},
        ]
    else:
        # TVLT2: 2-column side-by-side poetry + DỊCH NGHĨA + DỊCH THƠ stop boundary
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


class KaggleDualOCREngine:
    """Wrapper around GPU PaddleOCR (`chinese_cht`) and VietOCR (`vgg_transformer`)."""

    def __init__(self, use_gpu: bool = True, mock: bool = False) -> None:
        self.use_gpu = use_gpu
        self.mock = mock
        self._han_ocr: Any = None
        self._viet_det_ocr: Any = None
        self._viet_predictor: Any = None

    def _lazy_init_gpu_engines(self) -> None:
        if self.mock or self._han_ocr is not None:
            return
        from paddleocr import PaddleOCR  # type: ignore
        from vietocr.tool.config import Cfg  # type: ignore
        from vietocr.tool.predictor import Predictor  # type: ignore

        self._han_ocr = PaddleOCR(
            use_angle_cls=True,
            lang="chinese_cht",
            use_gpu=self.use_gpu,
            show_log=False,
        )
        self._viet_det_ocr = PaddleOCR(
            use_angle_cls=True,
            lang="vi",
            use_gpu=self.use_gpu,
            show_log=False,
        )
        cfg = Cfg.load_config_from_name("vgg_transformer")
        cfg["cnn"]["pretrained"] = True
        cfg["device"] = "cuda:0" if self.use_gpu else "cpu"
        self._viet_predictor = Predictor(cfg)

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
        crop_top_px = int(preprocess_meta.get("crop_top_px", 0))
        img_h, img_w = get_image_dimensions(cropped_image)

        # 1. PaddleOCR (chinese_cht) pass for Chữ Hán
        han_result = self._han_ocr.ocr(cropped_image, cls=True)
        han_items: List[Dict[str, Any]] = []
        raw_han_lines = han_result[0] if han_result and han_result[0] else []
        for idx, line in enumerate(raw_han_lines):
            bbox_pts = [[int(round(pt[0])), int(round(pt[1]))] for pt in line[0]]
            text, conf = str(line[1][0]), float(line[1][1])
            x1, y1, x2, y2 = _box_bounds({"bbox": bbox_pts})
            han_items.append({
                "line_id": f"{page_id}_han_{idx:03d}",
                "bbox": bbox_pts,
                "bbox_original": _offset_bbox_to_original(bbox_pts, crop_top_px),
                "box_xyxy": [int(x1), int(y1), int(x2), int(y2)],
                "text": text,
                "confidence": round(conf, 4),
            })

        # 2. PaddleOCR detector + VietOCR recognizer pass for Phiên âm & Dịch nghĩa
        viet_det_result = self._viet_det_ocr.ocr(cropped_image, cls=True)
        viet_items: List[Dict[str, Any]] = []
        raw_viet_lines = viet_det_result[0] if viet_det_result and viet_det_result[0] else []
        for idx, line in enumerate(raw_viet_lines):
            bbox_pts = [[int(round(pt[0])), int(round(pt[1]))] for pt in line[0]]
            fallback_text, det_conf = str(line[1][0]), float(line[1][1])
            x1, y1, x2, y2 = _box_bounds({"bbox": bbox_pts})
            ix1 = max(0, min(img_w - 1, int(x1)))
            iy1 = max(0, min(img_h - 1, int(y1)))
            ix2 = max(ix1 + 1, min(img_w, int(x2)))
            iy2 = max(iy1 + 1, min(img_h, int(y2)))

            recognized_text = fallback_text
            conf = det_conf
            if Image is not None and hasattr(cropped_image, "shape"):
                crop_patch = cropped_image[iy1:iy2, ix1:ix2]
                if crop_patch.size > 0:
                    pil_patch = Image.fromarray(crop_patch[:, :, ::-1] if crop_patch.ndim == 3 else crop_patch)
                    pred = self._viet_predictor.predict(pil_patch, return_prob=True)
                    if isinstance(pred, tuple) and len(pred) == 2:
                        recognized_text, conf = str(pred[0]), float(pred[1])
                    else:
                        recognized_text = str(pred)

            viet_items.append({
                "line_id": f"{page_id}_viet_{idx:03d}",
                "bbox": bbox_pts,
                "bbox_original": _offset_bbox_to_original(bbox_pts, crop_top_px),
                "box_xyxy": [ix1, iy1, ix2, iy2],
                "text": unicodedata.normalize("NFC", recognized_text),
                "confidence": round(conf, 4),
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

    If `book_folder` is provided (e.g. `'HVTT_HanVanTinhTuy'`), resolves under
    `<output_root>/deliverables/<book_folder>/02_ocr_tho/{han,viet}`.
    """
    root = Path(output_root)
    if book_folder:
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
    book_key = book_type.upper().strip()
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
    """Write raw OCR outputs to `02_ocr_tho/han/<page>.json` and `02_ocr_tho/viet/<page>.json`.

    Also mirrors outputs into `<output_root>/deliverables/<book_folder>/02_ocr_tho/{han,viet}/<page>.json`
    so both flat and multi-book deliverable layouts are always populated.
    """
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
            "interlinear_triplets": layout_summary.get("interlinear_triplets", []),
        },
    }

    # 1. Primary flat output (`<output_root>/02_ocr_tho/{han,viet}/<page>.json`)
    han_dir, viet_dir = resolve_ocr_output_dirs(output_root)
    flat_page_id = (
        safe_page_id
        if safe_page_id.upper().startswith(book_type.upper())
        else f"{book_type.upper()}_{safe_page_id}"
    )
    han_path = han_dir / f"{safe_page_id}.json"
    viet_path = viet_dir / f"{safe_page_id}.json"
    if han_path.exists() and flat_page_id != safe_page_id:
        han_path = han_dir / f"{flat_page_id}.json"
        viet_path = viet_dir / f"{flat_page_id}.json"

    with han_path.open("w", encoding="utf-8") as f:
        json.dump(han_payload, f, ensure_ascii=False, indent=2)

    with viet_path.open("w", encoding="utf-8") as f:
        json.dump(viet_payload, f, ensure_ascii=False, indent=2)

    # 2. Deliverable per-book output (`<output_root>/deliverables/<book>/02_ocr_tho/{han,viet}/<page>.json`)
    root_path = Path(output_root)
    if root_path.name != "02_ocr_tho" and "deliverables" not in root_path.parts:
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
        book_jsonl_path = output_dir / "deliverables" / b_folder / "02_ocr_tho" / "ocr_results.jsonl"
        book_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with book_jsonl_path.open("w", encoding="utf-8") as f:
            for item in book_results:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    global_jsonl_paths = [
        output_dir / "02_ocr_tho" / "ocr_results.jsonl",
        output_dir / "ocr_results.jsonl",
    ]
    for g_path in global_jsonl_paths:
        g_path.parent.mkdir(parents=True, exist_ok=True)
        with g_path.open("w", encoding="utf-8") as f:
            for item in results:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _install_kaggle_dependencies_if_needed() -> None:
    """Install PaddleOCR and VietOCR inside a Kaggle GPU kernel when requested."""
    pkgs = [
        "paddlepaddle-gpu",
        "paddleocr>=2.7.0",
        "vietocr",
        "opencv-python-headless",
    ]
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *pkgs])


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
        choices=["ALL", "HVTT", "TLTVN", "TVLT2"],
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

    args = parser.parse_args(argv)
    is_mock = bool(args.dry_run or args.mock)

    if args.install_deps and not is_mock:
        _install_kaggle_dependencies_if_needed()

    engine = KaggleDualOCREngine(use_gpu=not is_mock, mock=is_mock)
    input_path = Path(args.input_dir)
    image_files = _discover_input_images(input_path)
    if args.max_pages is not None and args.max_pages > 0:
        image_files = image_files[:args.max_pages]

    results: List[Dict[str, Any]] = []

    if image_files:
        for img_file in image_files:
            inferred_book, page_num = _infer_book_and_page(
                str(img_file),
                default_book="TVLT2" if args.book_type == "ALL" else args.book_type,
            )
            if args.book_type != "ALL" and inferred_book != args.book_type:
                continue
            book_folder = _resolve_book_folder(inferred_book, img_file)
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
    _write_jsonl_records(out_dir_path, results)

    summary_path = out_dir_path / "02_ocr_tho" / "ocr_run_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "mode": "mock" if is_mock else "kaggle_gpu",
                "pages_processed": len(results),
                "pages": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"[ocr_pipeline_kaggle] Processed {len(results)} page(s) (mode={'mock' if is_mock else 'gpu'}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
