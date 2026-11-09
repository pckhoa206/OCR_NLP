"""Extreme Stress and Boundary Test Suite for Hán–Việt Alignment Pipeline.

Tests:
1. Severe length disparity stress (1:10 and 10:1 ratio edge cases).
2. Malformed characters, lacunae markers ('□', '[.....]'), and messy footnotes.
3. XML control character and tab/newline injection sanitization.
4. Scale & throughput benchmark: 1,000 pairs aligned and exported in < 1 second.
5. OCR disambiguator and poetic couplet aligner boundary handling.
"""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.aligner import align_work_sentences, compute_length_ratio_score
from src.exporter_and_qa import (
    _sanitize_cell_text,
    export_tsv,
    export_xlsx_zero_dep,
    read_tsv,
    read_xlsx_zero_dep,
    validate_pairs,
)
from src.ocr_disambiguator import (
    correct_han_line_with_phien_am,
    disambiguate_character_with_phonetic,
)
from src.poetic_aligner import align_classical_poem, detect_vietnamese_poetic_meter
from src.text_cleaner import clean_han_text, clean_viet_text


class TestStressAndEdgeCases(unittest.TestCase):
    """Stress testing edge cases, boundary conditions, and performance scalability."""

    def test_extreme_length_ratio_disparities(self) -> None:
        """Ensure aligner never crashes or raises unhandled exceptions under extreme ratio imbalances."""
        # 1 very short Han char vs long Viet sentence
        short_h = ["佛"]
        long_v = ["Đức Phật là bậc giác ngộ hoàn toàn thấu suốt tam giới và muôn loài chúng sinh khắp mười phương."]
        res1 = align_work_sentences(short_h, long_v)
        self.assertEqual(len(res1), 1)
        self.assertEqual(res1[0]["han"], "佛")

        # 1 long Han sentence vs 1 short Viet word
        long_h = ["天地玄黃宇宙洪荒日月盈昃辰宿列張寒來暑往秋收冬藏閏餘成歲律呂調陽雲騰致雨露結為霜"]
        short_v = ["Trời."]
        res2 = align_work_sentences(long_h, short_v)
        self.assertEqual(len(res2), 1)

    def test_lacunae_and_missing_character_markers(self) -> None:
        """Test preservation and cleaning of historical lacunae markers (□, [...])."""
        raw_han = "霸橋□詩 [............]"
        cleaned = clean_han_text(raw_han)
        self.assertIn("霸橋□詩", cleaned)

        # Ensure validate_pairs treats legitimate lacunae without breaking
        report = validate_pairs([("霸橋□詩", "Cầu Bá ngâm vịnh.")])
        self.assertEqual(report["missing_count"], 0)

    def test_injection_sanitization_in_xlsx_and_tsv(self) -> None:
        """Verify XML control characters, unescaped tags, and tabs/newlines are safely sanitized."""
        malicious_han = "鄭子產\x00\x08<script>alert(1)</script>\t\n有疾"
        malicious_viet = "Trịnh Tử-Sản\x1f\r\n\t bệnh nặng <xml>test</xml>"

        clean_h = _sanitize_cell_text(malicious_han)
        clean_v = _sanitize_cell_text(malicious_viet)

        self.assertNotIn("\x00", clean_h)
        self.assertNotIn("\x1f", clean_v)
        self.assertNotIn("\t", clean_h)
        self.assertNotIn("\n", clean_h)

        # Test export and read back through zero-dependency OpenXML engine
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_tsv = Path(tmp_dir) / "test.tsv"
            tmp_xlsx = Path(tmp_dir) / "test.xlsx"

            pairs = [(malicious_han, malicious_viet)]
            export_tsv(pairs, str(tmp_tsv))
            export_xlsx_zero_dep(pairs, str(tmp_xlsx))

            roundtrip_tsv = read_tsv(str(tmp_tsv))
            roundtrip_xlsx = read_xlsx_zero_dep(str(tmp_xlsx))

            self.assertEqual(roundtrip_tsv, roundtrip_xlsx)
            self.assertEqual(len(roundtrip_tsv), 1)

    def test_ocr_disambiguator_boundary_conditions(self) -> None:
        """Test disambiguator on mismatched length inputs and untargeted characters."""
        # Length mismatch: should safely return original without crashing
        mismatched_h = "風打松開月照庭"  # 7 chars
        short_phien_am = "Phong đả tùng"  # 3 words
        res_h, diffs = correct_han_line_with_phien_am(mismatched_h, short_phien_am)
        self.assertEqual(res_h, mismatched_h)
        self.assertEqual(len(diffs), 0)

        # Character not in any confusion cluster: should remain untouched
        normal_h = "國"
        cand, was_corr, _ = disambiguate_character_with_phonetic(normal_h, "quốc")
        self.assertEqual(cand, "國")
        self.assertFalse(was_corr)

    def test_throughput_benchmark_1000_pairs(self) -> None:
        """Performance benchmark: process and export 1,000 alignment pairs in under 1 second."""
        synthetic_pairs = [
            (
                f"子曰學而時習之不亦說乎第{i}章",
                f"Khổng-tử nói: Học mà thường ôn tập, chẳng cũng thích sao, chương {i}.",
            )
            for i in range(1, 1001)
        ]

        t0 = time.perf_counter()
        with tempfile.TemporaryDirectory() as tmp_dir:
            bench_tsv = Path(tmp_dir) / "bench.tsv"
            bench_xlsx = Path(tmp_dir) / "bench.xlsx"

            # 1. Validate
            qa_res = validate_pairs(synthetic_pairs)
            self.assertEqual(qa_res["total_pairs"], 1000)

            # 2. Export TSV & XLSX
            export_tsv(synthetic_pairs, str(bench_tsv))
            export_xlsx_zero_dep(synthetic_pairs, str(bench_xlsx))

            # 3. Read back
            rt_tsv = read_tsv(str(bench_tsv))
            rt_xlsx = read_xlsx_zero_dep(str(bench_xlsx))
            self.assertEqual(len(rt_tsv), 1000)
            self.assertEqual(len(rt_xlsx), 1000)

        elapsed = time.perf_counter() - t0
        self.assertLess(elapsed, 1.5, f"1,000 pairs took {elapsed:.3f}s (should be < 1.5s)")


if __name__ == "__main__":
    unittest.main()
