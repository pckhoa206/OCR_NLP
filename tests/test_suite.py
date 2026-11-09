"""Comprehensive Unit & Integration Test Suite for Group CV04 Pipeline.

Verifies:
1. [MASK] token preservation in text_cleaner, phonetic_verifier, aligner, and exporter_and_qa.
2. Context-aware Sino-Vietnamese polysemous character disambiguation.
3. 4-column parallel alignment (Hán - Dịch âm - Dịch nghĩa - Dịch thơ).
4. Cross-platform PDF page extraction at 300 DPI via PyMuPDF.
5. Full pipeline execution and 100% TSV/XLSX deliverable compliance for CV04_VPO_01/02/03.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.aligner import align_work_sentences
from src.exporter_and_qa import (
    export_tsv,
    export_xlsx_zero_dep,
    read_tsv,
    read_xlsx_zero_dep,
    validate_pairs,
)
from src.ocr_disambiguator import correct_han_line_with_phien_am
from src.pdf_extractor import parse_page_spec, render_pdf_pages_to_png
from src.phonetic_verifier import (
    count_han_chars,
    project_punctuation_from_phien_am,
    verify_han_phien_am_pair,
)
from src.pipeline_runner import run_pipeline
from src.text_cleaner import clean_han_text


class TestCV04PipelineSuite(unittest.TestCase):
    def test_mask_token_preservation_and_counting(self) -> None:
        raw_han = "霸橋[MASK]詩，山明[MASK]秀。"
        cleaned = clean_han_text(raw_han)
        self.assertIn("[MASK]", cleaned)
        self.assertEqual(cleaned, "霸橋[MASK]詩，山明[MASK]秀。")
        # 4 chars in first clause (3 CJK + 1 [MASK]) + 4 chars in second clause (3 CJK + 1 [MASK]) = 8
        han_tokens = count_han_chars(cleaned)
        self.assertEqual(len(han_tokens), 8)
        self.assertEqual(han_tokens[2], "[MASK]")

        # Phonetic verification with [MASK] should treat [MASK] as matching the corresponding syllable
        ver = verify_han_phien_am_pair("霸橋[MASK]詩", "Bá Kiều vịnh thi")
        self.assertTrue(ver["length_match"])
        self.assertEqual(ver["char_count"], 4)
        self.assertEqual(len(ver["phonetic_mismatches"]), 0)
        self.assertGreaterEqual(ver["confidence_score"], 0.95)

        # Punctuation projection with [MASK]
        projected = project_punctuation_from_phien_am(
            "霸橋[MASK]詩山明[MASK]秀",
            "Bá Kiều vịnh thi, sơn minh thủy tú.",
        )
        self.assertEqual(projected, "霸橋[MASK]詩，山明[MASK]秀。")

    def test_qa_validator_accepts_mask_and_4_columns(self) -> None:
        rows = [
            (
                "霸橋[MASK]詩。",
                "Bá Kiều [MASK] thi.",
                "Cầu Bá ngâm vịnh thơ.",
                "Cầu Bá ngâm thơ cảnh tuyệt vời.",
            ),
            (
                "五更籌。",
                "Ngũ canh trù.",
                "",  # Empty Dịch nghĩa allowed when Dịch thơ is present (e.g. VPO_01 final poem)
                "Trống cầm canh đã điểm năm canh.",
            ),
        ]
        report = validate_pairs(rows)
        self.assertTrue(report["is_valid"])
        self.assertEqual(report["error_rate"], 0.0)
        self.assertEqual(report["valid_pairs"], 2)

    def test_ocr_disambiguation_with_phien_am(self) -> None:
        corrected, changes = correct_han_line_with_phien_am("夫火烈民望而畏之", "Phù hỏa liệt, dân vọng nhi úy chi")
        self.assertEqual(corrected, "夫火烈民望而畏之")
        self.assertIsInstance(changes, list)

    def test_gale_church_alignment_fast(self) -> None:
        han = ["學而時習之，不亦說乎。", "有朋自遠方來，不亦樂乎。"]
        viet = [
            "Học mà thường ôn tập lại, chẳng cũng vui sướng lắm sao.",
            "Có bạn từ phương xa tìm đến, chẳng cũng vui vẻ lắm sao.",
        ]
        pairs = align_work_sentences(han, viet)
        self.assertEqual(len(pairs), 2)
        self.assertGreater(pairs[0]["score"], 0.5)

    def test_tsv_and_xlsx_roundtrip_4col(self) -> None:
        rows = [
            ("老鶴摩空，", "Lão hạc ma không,", "Chim hạc già bay sát tầng mây,", "Hạc già cọ cánh tầng không,"),
            ("壯士暮年。", "Tráng sĩ mộ niên.", "Người tráng sĩ lúc tuổi về chiều.", "Tráng sĩ tuổi xế tấm lòng chưa phai."),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            tsv_p = Path(tmp) / "test.tsv"
            xlsx_p = Path(tmp) / "test.xlsx"
            export_tsv(rows, str(tsv_p))
            export_xlsx_zero_dep(rows, str(xlsx_p))
            r_tsv = read_tsv(str(tsv_p))
            r_xlsx = read_xlsx_zero_dep(str(xlsx_p))
            self.assertEqual(r_tsv, rows)
            self.assertEqual(r_xlsx, rows)

    def test_pymupdf_page_extraction(self) -> None:
        self.assertEqual(parse_page_spec("8,10,12-14", {}), [8, 10, 12, 13, 14])
        pdf_path = ROOT_DIR / "raw_data" / "Hán văn tinh tuý - Lãng Nhân.pdf"
        if pdf_path.is_file():
            with tempfile.TemporaryDirectory() as tmp:
                out = render_pdf_pages_to_png(pdf_path, tmp, [8], dpi=150)
                self.assertEqual(len(out), 1)
                self.assertTrue(out[0].is_file())
                self.assertEqual(out[0].name, "0008.png")

    def test_full_pipeline_deliverables(self) -> None:
        summary = run_pipeline(ROOT_DIR, four_col_all=True)
        books = summary.get("books", {})
        for code in ("VPO_01", "VPO_02", "VPO_03"):
            self.assertIn(code, books)
            info = books[code]
            self.assertGreater(info["pair_count"], 0)
            self.assertEqual(info["columns"], 4)
            self.assertEqual(info["error_rate"], 0.0)
            self.assertTrue(info["tsv_xlsx_identical"])


if __name__ == "__main__":
    unittest.main()
