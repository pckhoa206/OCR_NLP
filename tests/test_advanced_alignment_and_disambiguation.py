"""Tests for Advanced OCR Disambiguation, Word-Level Alignment & Flexible DP Beads."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.aligner import align_work_sentences, BEAD_PRIORS
from src.ocr_disambiguator import (
    disambiguate_character_with_phonetic,
    correct_han_line_with_phien_am,
    get_confusion_cluster_stats,
    VISUAL_CONFUSION_CLUSTERS,
    POLYPHONIC_CHARACTERS,
)
from src.word_aligner import (
    align_words_in_pair,
    batch_evaluate_word_coverage,
    get_candidate_readings_and_glosses,
)


class TestAdvancedDisambiguationAndWordAligner(unittest.TestCase):
    """Verify SOTA 105+ OCR confusion clusters, word-level grounding, and flexible beads."""

    def test_confusion_cluster_scale_and_classic_triads(self) -> None:
        """Verify 105+ confusion clusters and famous triads (戊/戌/戍, 己/已/巳, 侯/候, 祇/祗)."""
        stats = get_confusion_cluster_stats()
        self.assertGreaterEqual(stats["total_clusters"], 105)
        self.assertGreaterEqual(stats["total_characters"], 250)
        self.assertGreaterEqual(stats["polyphonic_count"], 20)

        # 1. 戊 (mậu) vs 戌 (tuất) vs 戍 (thú)
        char1, was_corr1, reason1 = disambiguate_character_with_phonetic("戊", "tuất")
        self.assertTrue(was_corr1)
        self.assertEqual(char1, "戌")

        char2, was_corr2, _ = disambiguate_character_with_phonetic("戊", "thú")
        self.assertTrue(was_corr2)
        self.assertEqual(char2, "戍")

        # 2. 侯 (hầu) vs 候 (hậu)
        char3, was_corr3, _ = disambiguate_character_with_phonetic("侯", "hậu")
        self.assertTrue(was_corr3)
        self.assertEqual(char3, "候")

        # 3. 祇 (kỳ) vs 祗 (chi)
        char4, was_corr4, _ = disambiguate_character_with_phonetic("祇", "chi")
        self.assertTrue(was_corr4)
        self.assertEqual(char4, "祗")

        # 4. Correct line with multiple mixed confusions
        raw_han = "風打松開月照庭"  # '開' misrecognized for '關' (quan)
        phien_am = "Phong đả tùng quan nguyệt chiếu đình"
        corrected_line, corrections = correct_han_line_with_phien_am(raw_han, phien_am)
        self.assertEqual(corrected_line, "風打松關月照庭")
        self.assertEqual(len(corrections), 1)
        self.assertEqual(corrections[0]["corrected_char"], "關")

    def test_word_aligner_fine_grained_grounding(self) -> None:
        """Verify fine-grained token-level grounding and coverage metrics."""
        han = "風打松關月照庭"
        viet = "Gió đập cổng thông trăng sáng trước sân"
        result = align_words_in_pair(han, viet)

        self.assertEqual(result["han_char_count"], 7)
        self.assertGreaterEqual(result["han_coverage_pct"], 90.0)
        self.assertGreaterEqual(result["confidence_score"], 0.85)
        self.assertEqual(len(result["unmatched_han"]), 0)

        # Ensure aligned_matches contains expected semantic pairs
        matched_dict = {m["han_char"]: m["viet_word"].lower() for m in result["aligned_matches"]}
        self.assertEqual(matched_dict.get("風"), "gió")
        self.assertEqual(matched_dict.get("松"), "thông")
        self.assertEqual(matched_dict.get("月"), "trăng")

    def test_word_aligner_detects_omission(self) -> None:
        """Verify word aligner identifies omitted Han characters when translator skips content."""
        han = "天地玄黃宇宙洪荒"
        viet = "Trời đất đen vàng"  # Missing 宇宙洪荒 (vũ trụ hồng hoang)
        result = align_words_in_pair(han, viet)

        # First 4 chars (天地玄黃) match, last 4 chars (宇宙洪荒) should be flagged in unmatched_han
        self.assertIn("宇", result["unmatched_han"])
        self.assertIn("宙", result["unmatched_han"])
        self.assertIn("洪", result["unmatched_han"])
        self.assertIn("荒", result["unmatched_han"])
        self.assertLess(result["han_coverage_pct"], 60.0)

    def test_flexible_dp_beads_1_4_and_2_3(self) -> None:
        """Verify aligner supports 1:4 and 2:3 beads without falling back or crashing."""
        self.assertIn((1, 4), BEAD_PRIORS)
        self.assertIn((4, 1), BEAD_PRIORS)
        self.assertIn((2, 3), BEAD_PRIORS)
        self.assertIn((3, 2), BEAD_PRIORS)

        # 1 Han sentence translated into 4 short Vietnamese modern clauses
        han_sents = [
            "朕竊謂佛無南北均可修求性有智愚同資覺悟"
        ]
        viet_sents = [
            "Trẫm thầm nghĩ.",
            "Phật không có nam bắc.",
            "Mọi người đều có thể tu cầu.",
            "Tánh có trí ngu đồng sẵn giác ngộ.",
        ]
        aligned = align_work_sentences(han_sents, viet_sents)
        self.assertEqual(len(aligned), 1)
        self.assertEqual(aligned[0]["align_type"], "1-4")
        self.assertEqual(len(aligned[0]["viet_indices"]), 4)

    def test_batch_word_coverage_on_pilot_corpora(self) -> None:
        """Run batch evaluation across all 3 books deliverables."""
        from src.exporter_and_qa import read_tsv

        for book_code in ["HVTT_HanVanTinhTuy", "TVLT2_ThoVanLyTran2", "TLTVN_TheLoaiTuVN"]:
            tsv_path = ROOT_DIR / "deliverables" / book_code / "04_dong_hang" / f"{book_code}_parallel.tsv"
            self.assertTrue(tsv_path.is_file(), f"Missing deliverable: {tsv_path}")
            rows = read_tsv(str(tsv_path))
            summary = batch_evaluate_word_coverage(rows)
            self.assertGreater(summary["total_pairs"], 0)
            self.assertGreaterEqual(summary["avg_han_coverage_pct"], 50.0)
            self.assertGreaterEqual(summary["avg_confidence"], 0.55)


if __name__ == "__main__":
    unittest.main()
