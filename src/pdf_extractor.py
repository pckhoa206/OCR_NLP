"""Cross-platform (Windows/macOS/Linux) 300 DPI PDF page renderer & text extractor.

Replaces macOS-only `extract_pages.swift` with PyMuPDF (`fitz`) so the entire
team can render 300 DPI page scans and extract digital text layers directly
from `raw_data/*.pdf` into `CV04_VPO_0*/01_nguon/`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


def load_manifest(workspace_root: Path) -> Dict[str, Any]:
    """Load `config/book_manifest.json`."""
    manifest_path = workspace_root / "config" / "book_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found at {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def resolve_book_id(book_key: str, manifest: Dict[str, Any]) -> str:
    """Resolve any book alias (`HVTT`, `VPO_01`, `CV04_VPO_01`, etc.) to canonical `VPO_01/02/03`."""
    aliases = manifest.get("aliases", {})
    key_upper = book_key.upper().strip()
    if key_upper in aliases:
        return aliases[key_upper]
    if key_upper in manifest.get("books", {}):
        return key_upper
    raise ValueError(f"Unknown book code: {book_key!r}. Valid codes: VPO_01, VPO_02, VPO_03 (or HVTT, TLTVN, TVLT2)")


def parse_page_spec(page_spec: str, book_cfg: Dict[str, Any]) -> List[int]:
    """Parse a page specification string (`'pilot'`, `'valid'`, or `'8,10,12-20'`) into 1-based PDF pages."""
    spec = page_spec.strip().lower()
    if spec == "pilot":
        return sorted(int(p) for p in book_cfg.get("pilot_pages", []))

    valid_range = book_cfg.get("valid_range", {})
    excluded_set = set(int(p) for p in book_cfg.get("excluded_pdf_pages_in_valid_range", []))
    if spec in ("valid", "all"):
        start = int(valid_range.get("pdf_page_start", 1))
        end = int(valid_range.get("pdf_page_end", book_cfg.get("total_pdf_pages", 1)))
        step = int(valid_range.get("step", 1))
        return [p for p in range(start, end + 1, step) if p not in excluded_set]

    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part or ".." in part:
            sep = ".." if ".." in part else "-"
            bounds = part.split(sep, 1)
            p_start, p_end = int(bounds[0].strip()), int(bounds[1].strip())
            for p in range(min(p_start, p_end), max(p_start, p_end) + 1):
                pages.add(p)
        else:
            pages.add(int(part))
    return sorted(pages)


def render_pdf_pages_to_png(
    pdf_path: Union[str, Path],
    output_dir: Union[str, Path],
    pages_1based: Sequence[int],
    dpi: int = 300,
    overwrite: bool = False,
) -> List[Path]:
    """Render 1-based PDF pages to 4-digit PNG files (`0008.png`) using PyMuPDF (`fitz`)."""
    import fitz  # PyMuPDF

    pdf_file = Path(pdf_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_file.is_file():
        raise FileNotFoundError(f"PDF file not found: {pdf_file}")

    doc = fitz.open(str(pdf_file))
    total_pages = len(doc)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    saved_paths: List[Path] = []
    try:
        for p_num in pages_1based:
            if p_num < 1 or p_num > total_pages:
                continue
            out_png = out_dir / f"{p_num:04d}.png"
            if out_png.is_file() and out_png.stat().st_size > 10_000 and not overwrite:
                saved_paths.append(out_png)
                continue
            page = doc[p_num - 1]
            pix = page.get_pixmap(matrix=mat, alpha=False)
            pix.save(str(out_png))
            saved_paths.append(out_png)
    finally:
        doc.close()

    return saved_paths


def extract_book_pages(
    workspace_root: Path,
    book_key: str = "ALL",
    page_spec: str = "pilot",
    dpi: int = 300,
    overwrite: bool = False,
) -> Dict[str, List[str]]:
    """Render requested pages for one or all books from `raw_data/` into `CV04_VPO_0*/01_nguon/`."""
    manifest = load_manifest(workspace_root)
    books_cfg = manifest["books"]

    if book_key.upper().strip() == "ALL":
        target_books = list(books_cfg.keys())
    else:
        target_books = [resolve_book_id(book_key, manifest)]

    extracted: Dict[str, List[str]] = {}
    for b_id in target_books:
        cfg = books_cfg[b_id]
        pdf_path = workspace_root / cfg["pdf_path"]
        out_dir = workspace_root / cfg["source_dir"]
        pages = parse_page_spec(page_spec, cfg)
        paths = render_pdf_pages_to_png(
            pdf_path=pdf_path,
            output_dir=out_dir,
            pages_1based=pages,
            dpi=dpi,
            overwrite=overwrite,
        )
        extracted[b_id] = [str(p.relative_to(workspace_root)) for p in paths]

    return extracted

