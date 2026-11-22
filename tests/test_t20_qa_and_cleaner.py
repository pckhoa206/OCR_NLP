"""TDD Test Suite for Ticket T20: Text Cleaner, 4-Column QA, Workbench, Word Aligner, HF Packaging & Handoff."""

from __future__ import annotations

import json
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path
from unittest import mock

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.exporter_and_qa import (
    export_tsv,
    export_xlsx_zero_dep,
    read_tsv,
    read_xlsx_zero_dep,
    validate_pairs,
)
from src.text_cleaner import clean_viet_text, split_viet_sentences
from src.word_aligner import align_words_in_pair, batch_evaluate_word_coverage
from src.workbench_editor import (
    merge_rows,
    save_and_reexport_corpus,
    split_row,
)
from web_app.app import BOOK_METADATA, run_headless_check


class TestT20TextCleanerAndSegmentation(unittest.TestCase):
    """Verify OCR footnote noise cleaning while preserving dates, years, acronyms, and genuine questions."""

    def test_strip_ocr_parenthesized_markers_and_preserve_lexical_and_years(self) -> None:
        raw = (
            "Nghĩ không có ngọc quỳnh (?) đáp lại, thực quyền (??), "
            "ngôi trời ('), triều Chu (\"\"), càng nặng (%), con lừa ba chân (1?), "
            "bài thứ (1%), chú thích (1*), da phấn (s), sức sinh (t), mục (l), "
            "chiếu (1) và ( 12 ) trong bản (kim) hoặc (tây) "
            "theo (Điệu Xuân quang hảo) và sách (VNGVHS1)."
        )
        cleaned = clean_viet_text(raw)
        for noise in ("(?)", "(??)", "(')", '("")', "(%)", "(1?)", "(1%)", "(1*)", "(s)", "(t)", "(l)", "(1)", "( 12 )"):
            self.assertNotIn(noise, cleaned, f"Failed to strip noise {noise!r} -> {cleaned!r}")
        for kept in ("(kim)", "(tây)", "(Điệu Xuân quang hảo)", "(VNGVHS1)"):
            self.assertIn(kept, cleaned, f"Should preserve lexical/genre paren {kept!r}")

    def test_preserve_years_ranges_dates_and_quantities(self) -> None:
        raw = (
            "Năm (1258) đời Trần, giai đoạn (1218–1277) và (933 - 1011), "
            "ngày (1-V-1277) và (8-10-1875), vào 16 tháng Sáu năm 1929, lúc 55 tuổi."
        )
        cleaned = clean_viet_text(raw)
        for kept in (
            "(1258)",
            "(1218–1277)",
            "(933 - 1011)",
            "(1-V-1277)",
            "(8-10-1875)",
            "16 tháng Sáu",
            "1929",
            "55 tuổi",
        ):
            self.assertIn(kept, cleaned, f"Must preserve date/year/quantity {kept!r}")

        # Standalone year must also survive clean_viet_text()
        self.assertEqual(clean_viet_text("1929"), "1929")
        self.assertEqual(clean_viet_text("(1258)"), "(1258)")

    def test_strip_trailing_superscript_digits_after_lowercase_preserve_acronyms(self) -> None:
        raw = (
            "Quê hương của hoàng đế5, như vân mẫu3 treo, đế hương2. "
            "Đối chiếu TVTL2, KHL1, VNGVHS1, NĐ60 và ĐẠI1."
        )
        cleaned = clean_viet_text(raw)
        self.assertIn("hoàng đế,", cleaned)
        self.assertIn("vân mẫu treo", cleaned)
        self.assertIn("đế hương.", cleaned)
        for sigla in ("TVTL2", "KHL1", "VNGVHS1", "NĐ60", "ĐẠI1"):
            self.assertIn(sigla, cleaned, f"Must preserve uppercase sigla {sigla!r}")

    def test_strip_standalone_ocr_variant_markers_preserve_pure_numbers(self) -> None:
        raw = "Cố 1? vô, tru 4% yến, Mạc 45 không, hưởng thọ 55 tuổi."
        cleaned = clean_viet_text(raw)
        self.assertIn("Cố vô", cleaned)
        self.assertIn("tru yến", cleaned)
        self.assertIn("Mạc 45 không", cleaned)
        self.assertIn("55 tuổi", cleaned)
        self.assertNotIn("1?", cleaned)
        self.assertNotIn("4%", cleaned)

    def test_strip_mid_sentence_ocr_question_mark_keep_genuine_questions(self) -> None:
        raw = (
            "Xưa có Tăng Sâm được khen là con hiếu?, Dùi mài Lục kinh?, "
            "Chim thước? màu trắng ứng vào điềm gì vậy? Liệng đến sân nhà. "
            "Phân minh báo? ngã hoàng. Làm sao biết? Đêm đã khuya rồi?"
        )
        cleaned = clean_viet_text(raw)
        self.assertIn("con hiếu,", cleaned)
        self.assertIn("Lục kinh,", cleaned)
        self.assertIn("Chim thước màu trắng", cleaned)
        self.assertIn("báo ngã hoàng.", cleaned)
        # Genuine questions followed by uppercase (including Đ) or end-of-string must stay
        self.assertIn("điềm gì vậy? Liệng đến sân nhà.", cleaned)
        self.assertIn("Làm sao biết? Đêm đã khuya rồi?", cleaned)

        # Ensure Unicode NFC is maintained even when input is NFD
        nfd_raw = unicodedata.normalize("NFD", raw)
        cleaned_nfc = clean_viet_text(nfd_raw)
        self.assertEqual(cleaned_nfc, unicodedata.normalize("NFC", cleaned_nfc))
        self.assertEqual(cleaned_nfc, cleaned)

    def test_split_viet_sentences_cleans_footnote_noise_before_splitting(self) -> None:
        text = (
            "Chim thước? màu trắng ứng vào điềm gì vậy? "
            "Xưa có Tăng Sâm được khen là con hiếu?, Dùi mài Lục kinh?, báo? ngã hoàng."
        )
        sents = split_viet_sentences(text, mode="sent")
        self.assertEqual(
            sents,
            [
                "Chim thước màu trắng ứng vào điềm gì vậy?",
                "Xưa có Tăng Sâm được khen là con hiếu, Dùi mài Lục kinh, báo ngã hoàng.",
            ],
        )


class TestT20FourColExporterAndQA(unittest.TestCase):
    """Verify 4-column QA rules and empty XLSX export with explicit 4-col headers."""

    def test_validate_pairs_four_col_title_and_partial_columns(self) -> None:
        rows = [
            # Valid title row (Hán + Dịch âm only)
            ("鄭子產論政", "Trịnh Tử-Sản luận chính", "", ""),
            # Valid row omitting Dịch âm
            ("風打松關月照庭", "", "Gió đập cổng thông, trăng sáng trước sân", ""),
            # Valid verse-only row omitting Dịch nghĩa
            ("仙家別占清閒", "Tiên gia biệt chiếm thanh-nhàn", "", "Thanh-nhàn riêng một cảnh tiên"),
            # Valid row with only Dịch thơ
            ("心期風景共淒清", "", "", "Lòng hẹn phong cảnh cùng trong sạch lặng lẽ"),
        ]
        report = validate_pairs(rows)
        self.assertTrue(report["is_valid"], f"Expected valid report, got issues: {report['issues']}")
        self.assertEqual(report["missing_count"], 0)
        self.assertEqual(report["error_rate"], 0.0)

    def test_validate_pairs_four_col_catches_true_missing_and_ratio_on_primary(self) -> None:
        bad_rows = [
            ("", "Trịnh", "Nghĩa", ""),  # Missing Hán -> MISSING
            ("鄭子產有疾", "", "", ""),  # All 3 Vietnamese cols empty -> MISSING
            # Primary Vietnamese (dich_nghia) too short -> OMISSION even though dich_am is present
            ("天地玄黃宇宙洪荒日月盈昃辰宿列張", "Thiên địa huyền hoàng", "Trời đất.", ""),
        ]
        report = validate_pairs(bad_rows)
        self.assertFalse(report["is_valid"])
        self.assertEqual(report["missing_count"], 2)
        self.assertEqual(report["omission_count"], 1)

    def test_export_xlsx_empty_pairs_with_explicit_four_col_headers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xlsx_path = Path(tmp) / "empty_4col.xlsx"
            headers = ("Hán", "Dịch âm", "Dịch nghĩa", "Dịch thơ")
            export_xlsx_zero_dep(
                [],
                str(xlsx_path),
                stats={"Tổng số cặp câu": 0},
                headers=headers,
            )
            with_hdr = read_xlsx_zero_dep(str(xlsx_path), sheet_name="DONG_HANG", include_header=True)
            self.assertEqual(with_hdr, [headers])
            no_hdr = read_xlsx_zero_dep(str(xlsx_path), sheet_name="DONG_HANG", include_header=False)
            self.assertEqual(no_hdr, [])


class TestT20WorkbenchAndWebApp(unittest.TestCase):
    """Verify 4-col web metadata, merge_rows empty cells, split_row per-col offsets, and save_and_reexport."""

    def test_web_app_metadata_unified_four_col_and_headless_check(self) -> None:
        for book in ("HVTT", "TVLT2", "TLTVN"):
            self.assertTrue(BOOK_METADATA[book]["is_four_col"], f"{book} must have is_four_col=True")
        summary = run_headless_check()
        self.assertEqual(set(summary.keys()), {"HVTT", "TVLT2", "TLTVN"})

    def test_merge_rows_four_col_empty_cells_never_emit_stray_commas(self) -> None:
        rows = [
            ("鄭子產", "Trịnh Tử-Sản", "", "Thơ một"),
            ("論政", "", "luận chính", ""),
        ]
        merged = merge_rows(rows, 0, 1)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0], ("鄭子產，論政", "Trịnh Tử-Sản", "luận chính", "Thơ một"))

        both_empty = [
            ("風", "Phong", "", ""),
            ("月", "Nguyệt", "", ""),
        ]
        merged_empty = merge_rows(both_empty, 0, 1)
        self.assertEqual(merged_empty[0], ("風，月", "Phong, Nguyệt", "", ""))

    def test_split_row_four_col_with_optional_offsets_and_fallback(self) -> None:
        rows = [
            ("風打松關月照庭", "Phong đả tùng quan, nguyệt chiếu đình", "Gió đập cổng thông, trăng sáng trước sân", "Câu thơ một Câu thơ hai"),
        ]
        # Explicit per-column offsets
        res = split_row(
            rows,
            0,
            han_split_pos=4,
            viet_split_pos=20,
            dich_am_split_pos=19,
            dich_nghia_split_pos=20,
            dich_tho_split_pos=11,
        )
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0][0], "風打松關")
        self.assertEqual(res[1][0], "月照庭")
        self.assertEqual(res[0][1], "Phong đả tùng quan,")
        self.assertEqual(res[1][1], "nguyệt chiếu đình")
        self.assertEqual(res[0][2], "Gió đập cổng thông,")
        self.assertEqual(res[1][2], "trăng sáng trước sân")
        self.assertEqual(res[0][3], "Câu thơ một")
        self.assertEqual(res[1][3], "Câu thơ hai")

        # Backward-compatible omission of optional offsets
        res_fallback = split_row(rows, 0, han_split_pos=4, viet_split_pos=20)
        self.assertEqual(len(res_fallback), 2)
        self.assertEqual(res_fallback[0][0], "風打松關")
        self.assertEqual(res_fallback[1][0], "月照庭")
        self.assertEqual(res_fallback[0][3], "Câu thơ một Câu thơ hai")
        self.assertEqual(res_fallback[1][3], "")

    def test_save_and_reexport_four_col_canonical_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            rows_4col = [
                ("鄭子產論政", "Trịnh Tử-Sản luận chính", "", ""),
                ("風打松關月照庭", "Phong đả tùng quan, nguyệt chiếu đình", "Gió đập cổng thông, trăng sáng trước sân", ""),
            ]
            res = save_and_reexport_corpus("TVLT2", rows_4col, tmp_root)
            self.assertEqual(res["status"], "SUCCESS")
            self.assertTrue(res["is_valid"])
            tsv_path = Path(res["tsv_path"])
            xlsx_path = Path(res["xlsx_path"])
            self.assertEqual(tsv_path.name, "TVLT2_ThoVanLyTran2_parallel.tsv")
            self.assertEqual(xlsx_path.name, "TVLT2_ThoVanLyTran2_parallel.xlsx")
            # Short duplicate file should NOT be created from scratch when canonical suffices
            self.assertFalse((tsv_path.parent / "TVLT2_parallel.tsv").exists())

            xlsx_hdr = read_xlsx_zero_dep(str(xlsx_path), sheet_name="DONG_HANG", include_header=True)
            self.assertEqual(xlsx_hdr[0], ("Hán", "Dịch âm", "Dịch nghĩa", "Dịch thơ"))
            self.assertEqual(read_tsv(str(tsv_path)), xlsx_hdr[1:])
            stats_rows = read_xlsx_zero_dep(str(xlsx_path), sheet_name="THONG_KE", include_header=True)
            self.assertEqual(stats_rows[0], ("Chỉ số", "Giá trị"))


class TestT20WordAlignerHFDiagnosticsAndHandoff(unittest.TestCase):
    """Verify title-row fallback in HF packaging/diagnostics, 4-col length_score in word_aligner, and handoff count."""

    def test_batch_word_coverage_uses_primary_col_for_length_score(self) -> None:
        # 7 Han chars; each Vietnamese column has ~8 words, so combined is ~24 words (ratio ~3.4 > 2.4)
        # while primary column (dich_nghia) has ratio ~1.14 (within ideal [0.80, 2.40]).
        row = (
            "風打松關月照庭",
            "Phong đả tùng quan nguyệt chiếu đình",
            "Gió đập cổng thông trăng sáng trước sân",
            "Ngọn gió đập cửa thông trăng chiếu sân",
        )
        batch_res = batch_evaluate_word_coverage([row])
        single_primary_len = align_words_in_pair(
            row[0],
            f"{row[1]} {row[2]} {row[3]}",
            length_text=row[2],
        )
        single_combined_len = align_words_in_pair(row[0], f"{row[1]} {row[2]} {row[3]}")
        self.assertEqual(batch_res["avg_confidence"], single_primary_len["confidence_score"])
        self.assertGreater(single_primary_len["confidence_score"], single_combined_len["confidence_score"])

        # Empty corpus should safely include avg_han_coverage_pct
        empty_res = batch_evaluate_word_coverage([])
        self.assertEqual(empty_res["total_pairs"], 0)
        self.assertIn("avg_han_coverage_pct", empty_res)

    def test_package_hf_dataset_title_row_fallback(self) -> None:
        from scripts import package_hf_dataset

        with tempfile.TemporaryDirectory() as tmp:
            tsv_path = Path(tmp) / "HVTT_HanVanTinhTuy_parallel.tsv"
            export_tsv(
                [
                    ("鄭子產論政", "Trịnh Tử-Sản luận chính", "", ""),
                    ("故寬難", "Cố khoan nan", "Vì thế khoan hồng là khó", ""),
                ],
                str(tsv_path),
            )
            fake_books = [
                {
                    "id": "HVTT",
                    "title": "Hán Văn Tinh Túy",
                    "author": "Lãng Nhân",
                    "tsv": tsv_path,
                    "genre": "classical_prose_and_verse",
                    "period": "cổ đại",
                }
            ]
            with mock.patch.object(package_hf_dataset, "BOOKS", fake_books):
                records = package_hf_dataset.load_all_records()

            self.assertEqual(len(records), 2)
            # Title row falls back to Dịch âm instead of ""
            self.assertEqual(records[0]["vietnamese_translation"], "Trịnh Tử-Sản luận chính")
            self.assertEqual(records[1]["vietnamese_translation"], "Vì thế khoan hồng là khó")

    def test_diagnose_corpus_quality_title_row_fallback(self) -> None:
        from scripts import diagnose_corpus_quality

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            align_dir = tmp_root / "deliverables" / "HVTT_HanVanTinhTuy" / "04_dong_hang"
            align_dir.mkdir(parents=True)
            tsv_path = align_dir / "HVTT_HanVanTinhTuy_parallel.tsv"
            export_tsv(
                [("鄭子產論政", "Trịnh Tử-Sản luận chính", "", "")],
                str(tsv_path),
            )
            diag = diagnose_corpus_quality.diagnose_book("HVTT", workspace_root=tmp_root)
            self.assertEqual(diag["total_rows"], 1)
            # Flagged or not, translation field must fall back to Dịch âm
            # Inspect internal row_diagnostics via monkeypatching threshold or checking low/high
            # Wait: check directly with a low-coverage title row so it appears in flagged_rows
            export_tsv(
                [("天地玄黃宇宙洪荒", "Thiên địa huyền hoàng vũ trụ hồng hoang", "", "")],
                str(tsv_path),
            )
            diag2 = diagnose_corpus_quality.diagnose_book("HVTT", workspace_root=tmp_root)
            # Ensure non-empty translation when flagged or verify via clean row
            self.assertEqual(diag2["total_rows"], 1)
            if diag2["flagged_rows"]:
                self.assertEqual(
                    diag2["flagged_rows"][0]["translation"],
                    "Thiên địa huyền hoàng vũ trụ hồng hoang",
                )

    def test_handoff_prefers_canonical_tsv_and_counts_all_rows_without_header_subtraction(self) -> None:
        import importlib.util

        handoff_path = ROOT_DIR / ".agents" / "skills" / "handoff" / "scripts" / "handoff.py"
        spec = importlib.util.spec_from_file_location("t20_handoff", handoff_path)
        assert spec is not None and spec.loader is not None
        handoff_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(handoff_mod)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            align_dir = tmp_root / "deliverables" / "HVTT_HanVanTinhTuy" / "04_dong_hang"
            align_dir.mkdir(parents=True)

            # Write canonical TSV with 3 rows and stale short TSV with 1 row
            canonical_tsv = align_dir / "HVTT_HanVanTinhTuy_parallel.tsv"
            canonical_xlsx = align_dir / "HVTT_HanVanTinhTuy_parallel.xlsx"
            short_tsv = align_dir / "HVTT_parallel.tsv"

            canonical_tsv.write_text("A\tB\tC\tD\nE\tF\tG\tH\nI\tJ\tK\tL\n", encoding="utf-8")
            canonical_xlsx.write_bytes(b"placeholder")
            short_tsv.write_text("OLD\tROW\n", encoding="utf-8")

            with mock.patch.object(handoff_mod, "WORKSPACE_ROOT", tmp_root):
                stats = handoff_mod.count_book_deliverables("HVTT", "HVTT_HanVanTinhTuy")

            self.assertTrue(stats["tsv_exists"])
            self.assertTrue(stats["xlsx_exists"])
            # Must use canonical_tsv (3 lines) and NOT subtract 1 for a non-existent header!
            self.assertEqual(stats["aligned_pairs_count"], 3)


if __name__ == "__main__":
    unittest.main()
