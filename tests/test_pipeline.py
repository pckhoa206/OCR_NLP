"""Comprehensive Deterministic Test Suite for the Hán–Việt Parallel Corpus Pipeline.

Compatible with both `unittest` (`python3 -m unittest discover -s tests -p "test_*.py" -v`)
and `pytest`.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from kaggle_ocr.ocr_pipeline_kaggle import (
    KaggleDualOCREngine,
    crop_running_header,
    detect_footnote_separator,
    group_layout_blocks,
    main as kaggle_ocr_main,
    preprocess_page_image,
    process_single_page,
)
from scripts.run_pilot_demo import run_pilot_pipeline
from src.aligner import (
    align_interlinear_blocks,
    align_work_sentences,
    compute_anchor_similarity,
    compute_length_ratio_score,
)
from src.exporter_and_qa import (
    export_tsv,
    export_xlsx_zero_dep,
    read_tsv,
    read_xlsx_zero_dep,
    validate_pairs,
)
from src.phonetic_verifier import (
    count_han_chars,
    normalize_viet_syllable,
    project_punctuation_from_phien_am,
    strip_footnote_markers,
    tokenize_phien_am,
    verify_han_phien_am_pair,
)
from src.text_cleaner import (
    clean_han_text,
    clean_viet_text,
    normalize_unicode_nfc,
    split_han_sentences,
    split_viet_sentences,
)


class TestInventoryAndManifest(unittest.TestCase):
    """Verify Step 1, Step 2, and Step 3 manifest and extracted pilot PNG pages."""

    def test_manifest_and_pilot_pngs_exist(self) -> None:
        manifest_path = ROOT_DIR / "config" / "book_manifest.json"
        self.assertTrue(manifest_path.is_file(), "config/book_manifest.json must exist")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        books = manifest["books"]
        self.assertEqual(set(books.keys()), {"HVTT", "TVLT2", "TLTVN"})

        # Verify page offsets & counts
        self.assertEqual(books["HVTT"]["book_to_pdf_offset"], 6)
        self.assertEqual(books["HVTT"]["valid_range"]["valid_pdf_page_count"], 374)
        self.assertEqual(books["HVTT"]["valid_range"]["even_han_page_count"], 187)
        self.assertEqual(books["TVLT2"]["pdf_to_book_offset"], 2)
        self.assertIn(25, books["TVLT2"]["excluded_pdf_pages_in_valid_range"])
        self.assertEqual(books["TLTVN"]["book_to_pdf_offset"], 7)
        self.assertEqual(books["TLTVN"]["valid_range"]["pdf_page_start"], 134)
        self.assertEqual(books["TLTVN"]["valid_range"]["pdf_page_end"], 547)

        # Verify extracted pilot PNGs in 01_nguon/
        for book_key, cfg in books.items():
            src_dir = ROOT_DIR / cfg["source_dir"]
            self.assertTrue(src_dir.is_dir(), f"Missing source_dir for {book_key}: {src_dir}")
            for pdf_page in cfg["pilot_pages"]:
                png_path = src_dir / f"{pdf_page:04d}.png"
                self.assertTrue(png_path.is_file(), f"Missing extracted pilot PNG: {png_path}")
                self.assertGreater(png_path.stat().st_size, 10_000)

        # Verify Step 2 inventory markdown report exists
        inventory_doc = ROOT_DIR / "docs" / "BANG_KIEM_KE_NGUON.md"
        self.assertTrue(inventory_doc.is_file())
        doc_text = inventory_doc.read_text(encoding="utf-8")
        self.assertIn("HVTT_HanVanTinhTuy", doc_text)
        self.assertIn("TVLT2_ThoVanLyTran2", doc_text)
        self.assertIn("TLTVN_TheLoaiTuVN", doc_text)


class TestPhoneticVerifier(unittest.TestCase):
    """Test Sino-Vietnamese phonetic verification and punctuation projection on real lines."""

    def test_hvtt_real_line_and_punctuation_projection(self) -> None:
        han = "鄭 子 產 有 疾 謂 子 太 叔 曰"
        phien_am = "Trịnh Tử-Sản hữu tật, vị tử Thái-Thúc viết :"

        res = verify_han_phien_am_pair(han, phien_am)
        self.assertEqual(res["char_count"], 10)
        self.assertEqual(res["syllable_count"], 10)
        self.assertTrue(res["length_match"])
        self.assertEqual(res["phonetic_mismatches"], [])
        self.assertEqual(res["confidence_score"], 1.0)

        projected = project_punctuation_from_phien_am(han, phien_am)
        self.assertEqual(projected, "鄭子產有疾，謂子太叔曰：")

    def test_tltvn_real_line_verification(self) -> None:
        han = "祥光風好錦帆張, 神仙復帝鄉."
        phien_am = "Tường quang phong hảo cẩm phàm trương, Thần tiên phục đế hương²."

        res = verify_han_phien_am_pair(han, phien_am)
        self.assertEqual(res["char_count"], 12)
        self.assertEqual(res["syllable_count"], 12)
        self.assertTrue(res["length_match"])
        self.assertEqual(res["phonetic_mismatches"], [])
        self.assertEqual(res["confidence_score"], 1.0)

    def test_tvlt2_real_line_verification_with_star_footnotes(self) -> None:
        han = "風打松關月照庭，心期風景共淒清。"
        phien_am = "Phong đả tùng quan 1* nguyệt chiếu đình, Tâm kỳ phong cảnh cộng thê thanh."

        res = verify_han_phien_am_pair(han, phien_am)
        self.assertEqual(res["char_count"], 14)
        self.assertEqual(res["syllable_count"], 14)
        self.assertTrue(res["length_match"])
        self.assertEqual(res["phonetic_mismatches"], [])
        self.assertEqual(res["confidence_score"], 1.0)

    def test_orthographic_equivalence_and_mismatch_detection(self) -> None:
        self.assertEqual(normalize_viet_syllable("Lý"), normalize_viet_syllable("lí"))
        self.assertEqual(normalize_viet_syllable("Quy"), normalize_viet_syllable("qui"))
        self.assertEqual(normalize_viet_syllable("thuỷ"), normalize_viet_syllable("thủy"))
        self.assertEqual(normalize_viet_syllable("hoà"), normalize_viet_syllable("hòa"))

        # Simulate OCR misrecognizing 關 (quan) as 開 (khai)
        bad_han = "風打松開月照庭，心期風景共淒清。"
        phien_am = "Phong đả tùng quan 1* nguyệt chiếu đình, Tâm kỳ phong cảnh cộng thê thanh."
        mismatch_res = verify_han_phien_am_pair(bad_han, phien_am)
        self.assertTrue(mismatch_res["length_match"])
        self.assertEqual(len(mismatch_res["phonetic_mismatches"]), 1)
        idx, ch, syl, expected = mismatch_res["phonetic_mismatches"][0]
        self.assertEqual((idx, ch, syl), (3, "開", "quan"))
        self.assertIn("khai", expected)
        self.assertLess(mismatch_res["confidence_score"], 1.0)


class TestTextCleaner(unittest.TestCase):
    """Test non-destructive text cleaning, NFD->NFC, footnote/label removal, and segmentation."""

    def test_clean_han_and_viet_noisy_inputs(self) -> None:
        noisy_han = unicodedata.normalize(
            "NFD",
            "NGUYÊN VĂN : 祥光風好錦帆張 1*, 神仙復帝鄉 [2] (1)¹².",
        )
        cleaned_han = clean_han_text(noisy_han)
        self.assertEqual(cleaned_han, "祥光風好錦帆張，神仙復帝鄉。")
        self.assertNotIn("\t", cleaned_han)
        self.assertNotIn("\n", cleaned_han)

        noisy_viet = unicodedata.normalize(
            "NFD",
            "2   HÁN-VĂN TINH-TUÝ\n"
            "THƠ VĂN LÝ — TRẦN   21\n"
            "PHIÊN ÂM : DỊCH NGHĨA : Gió đập cổng thông 1*, trăng2* sáng [1] trước (12) sân¹²³,\n"
            "Lòng hẹn với phong-\n"
            "cảnh cùng trong\tsạch   lặng lẽ.",
        )
        cleaned_viet = clean_viet_text(noisy_viet)
        self.assertEqual(
            cleaned_viet,
            "Gió đập cổng thông, trăng sáng trước sân, Lòng hẹn với phongcảnh cùng trong sạch lặng lẽ.",
        )
        self.assertEqual(unicodedata.normalize("NFC", cleaned_viet), cleaned_viet)
        self.assertNotIn("\t", cleaned_viet)
        self.assertNotIn("\n", cleaned_viet)
        self.assertNotIn("1*", cleaned_viet)
        self.assertNotIn("[1]", cleaned_viet)
        self.assertNotIn("DỊCH NGHĨA", cleaned_viet)

    def test_sentence_splitting_with_abbreviations(self) -> None:
        han_multi = "風打松關月照庭，心期風景共淒清。箇中滋味無人識，付與山僧樂到明。"
        h_sents = split_han_sentences(han_multi)
        self.assertEqual(
            h_sents,
            [
                "風打松關月照庭，心期風景共淒清。",
                "箇中滋味無人識，付與山僧樂到明。",
            ],
        )

        viet_multi = (
            "Theo GS.TS. Nguyễn Huệ Chi (NXB. Khoa học Xã hội, Tr. 21, Tp. Hà Nội), "
            "bài thơ mở đầu rất thanh thoát. Câu thứ hai nói về thú vị thiền học!"
        )
        v_sents = split_viet_sentences(viet_multi, mode="sent")
        self.assertEqual(len(v_sents), 2)
        self.assertIn("GS.TS. Nguyễn Huệ Chi", v_sents[0])
        self.assertIn("Tr. 21", v_sents[0])
        self.assertEqual(v_sents[1], "Câu thứ hai nói về thú vị thiền học!")


class TestAligner(unittest.TestCase):
    """Test 1-1, 1-2, and 2-1 Hán-Việt alignment in interlinear and work-bounded modes."""

    def test_interlinear_alignment_1_1_and_continuations(self) -> None:
        blocks = [
            {
                "han": "鄭子產有疾，謂子太叔曰：",
                "phien_am": "Trịnh Tử-Sản hữu tật, vị tử Thái-Thúc viết :",
                "dich_nghia": "Trịnh Tử-Sản bệnh nặng, bảo con là Thái-Thúc rằng :",
            },
            {
                "han": "我死，子必爲政。",
                "phien_am": "Ngã tử, tử tất vi chính.",
                "dich_nghia": "Ta chết, con sẽ giữ chính-quyền.",
            },
            # 1-2 continuation block (empty han on continuation line)
            {
                "han": "",
                "phien_am": "",
                "dich_nghia": "Hãy cẩn trọng việc nước.",
            },
        ]
        pairs = align_interlinear_blocks(blocks)
        self.assertEqual(len(pairs), 2)
        self.assertEqual(
            pairs[0],
            (
                "鄭子產有疾，謂子太叔曰：",
                "Trịnh Tử-Sản bệnh nặng, bảo con là Thái-Thúc rằng:",
            ),
        )
        self.assertEqual(
            pairs[1],
            (
                "我死，子必爲政。",
                "Ta chết, con sẽ giữ chính-quyền. Hãy cẩn trọng việc nước.",
            ),
        )

    def test_work_sentences_alignment_1_1_and_1_2_and_2_1(self) -> None:
        # 1. Test 1-1 alignment
        han_1_1 = [
            "風打松關月照庭，心期風景共淒清。",
            "箇中滋味無人識，付與山僧樂到明。",
        ]
        viet_1_1 = [
            "Gió đập cổng thông, trăng sáng trước sân, lòng hẹn với phong cảnh cùng trong sạch lặng lẽ.",
            "Bao nhiêu thú vị trong đó không ai hay, mặc cho nhà sư trong núi vui đến sáng.",
        ]
        res_1_1 = align_work_sentences(han_1_1, viet_1_1)
        self.assertEqual(len(res_1_1), 2)
        self.assertEqual([r["align_type"] for r in res_1_1], ["1-1", "1-1"])

        # 2. Test 1-2 alignment (1 long Hán couplet translated into 2 separate Vietnamese sentences)
        han_1_2 = [
            "顧無瓊報自懷慚，極目江皋意不堪。",
            "馬首秋風吹劍鋏，屋梁落月照書庵。",
        ]
        viet_1_2 = [
            "Nghĩ không có ngọc quỳnh đáp lại, lòng tự thẹn.",
            "Trên bờ sông nhìn xa mãi xiết bao bùi ngùi.",
            "Gió thu trước đầu ngựa thổi vào thanh gươm, ánh trăng lọt qua rường nhà dọi vào phòng sách.",
        ]
        sim_1_2 = [
            [0.92, 0.90, 0.15],
            [0.12, 0.14, 0.95],
        ]
        res_1_2 = align_work_sentences(han_1_2, viet_1_2, sim_matrix=sim_1_2)
        self.assertEqual(len(res_1_2), 2)
        self.assertEqual(res_1_2[0]["align_type"], "1-2")
        self.assertEqual(res_1_2[0]["han_indices"], [0])
        self.assertEqual(res_1_2[0]["viet_indices"], [0, 1])
        self.assertEqual(res_1_2[1]["align_type"], "1-1")

        # 3. Test 2-1 alignment (2 short Hán clauses merged into 1 Vietnamese sentence)
        han_2_1 = [
            "政寬則民慢，",
            "慢則糾之以猛。",
            "政是以和。",
        ]
        viet_2_1 = [
            "Chính sách khoan hòa thì dân nhờn, nhờn thì lấy sự nghiêm mãnh mà sửa trị.",
            "Chính sự nhờ thế mà hài hòa.",
        ]
        sim_2_1 = [
            [0.91, 0.15],
            [0.93, 0.12],
            [0.14, 0.95],
        ]
        res_2_1 = align_work_sentences(han_2_1, viet_2_1, sim_matrix=sim_2_1)
        self.assertEqual(len(res_2_1), 2)
        self.assertEqual(res_2_1[0]["align_type"], "2-1")
        self.assertEqual(res_2_1[0]["han_indices"], [0, 1])
        self.assertEqual(res_2_1[0]["viet_indices"], [0])
        self.assertEqual(res_2_1[1]["align_type"], "1-1")


class TestExporterAndQAAndPilotDeliverables(unittest.TestCase):
    """Test QA validation rules and end-to-end pilot deliverables (.tsv, .xlsx, han.txt, viet.txt)."""

    def test_pilot_deliverables_end_to_end(self) -> None:
        summary = run_pilot_pipeline(ROOT_DIR)
        self.assertEqual(set(summary["books"].keys()), {"HVTT", "TLTVN", "TVLT2"})

        for book_key, info in summary["books"].items():
            self.assertGreater(info["pair_count"], 0, f"{book_key} must have aligned pairs")
            self.assertTrue(info["phonetic_all_matched"], f"{book_key} phonetic check failed")
            self.assertLessEqual(info["error_rate"], 0.20, f"{book_key} error rate exceeds 20%")
            self.assertEqual(info["error_rate"], 0.0, f"{book_key} should have 0.0 error rate on clean pilot")
            self.assertTrue(info["is_valid"])
            self.assertTrue(info["tsv_xlsx_identical"])

            tsv_path = Path(info["tsv_path"])
            xlsx_path = Path(info["xlsx_path"])
            han_txt = Path(info["han_txt"])
            viet_txt = Path(info["viet_txt"])

            self.assertTrue(tsv_path.is_file())
            self.assertTrue(xlsx_path.is_file())
            self.assertTrue(han_txt.is_file())
            self.assertTrue(viet_txt.is_file())

            # Read back TSV and XLSX (DONG_HANG sheet) and assert 100% identity
            tsv_pairs = read_tsv(str(tsv_path))
            xlsx_rows_with_header = read_xlsx_zero_dep(
                str(xlsx_path), sheet_name="DONG_HANG", include_header=True
            )
            expected_header = (
                ("Hán", "Dịch âm", "Dịch nghĩa", "Dịch thơ")
                if book_key == "HVTT"
                else ("Hán", "Việt")
            )
            self.assertEqual(xlsx_rows_with_header[0], expected_header)
            xlsx_pairs = xlsx_rows_with_header[1:]
            self.assertEqual(tsv_pairs, xlsx_pairs)

            # Verify THONG_KE sheet exists and is readable
            stats_rows = read_xlsx_zero_dep(
                str(xlsx_path), sheet_name="THONG_KE", include_header=True
            )
            self.assertEqual(stats_rows[0], ("Chỉ số", "Giá trị"))

            # Verify raw TSV line format: strictly expected tab count per line, no empty lines
            expected_tabs = 3 if book_key == "HVTT" else 1
            raw_lines = tsv_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(raw_lines), len(tsv_pairs))
            for line in raw_lines:
                self.assertEqual(line.count("\t"), expected_tabs)

    def test_hvtt_four_column_and_final_poem_empty_dich_nghia(self) -> None:
        """Verify HVTT 4-column alignment and blank Dịch nghĩa handling for the final poem."""
        tsv_path = ROOT_DIR / "deliverables" / "HVTT_HanVanTinhTuy" / "04_dong_hang" / "HVTT_HanVanTinhTuy_parallel.tsv"
        self.assertTrue(tsv_path.is_file())
        rows = read_tsv(str(tsv_path))
        self.assertGreaterEqual(len(rows), 20)

        # Check that the last 2 rows correspond to Thu dạ hoài ngâm with empty Dịch nghĩa and populated Dịch thơ
        last_row = rows[-1]
        self.assertEqual(len(last_row), 4)
        han, dich_am, dich_nghia, dich_tho = last_row
        self.assertIn("仙家別占清閒", han)
        self.assertIn("Tiên gia biệt chiếm thanh-nhàn", dich_am)
        self.assertEqual(dich_nghia, "")
        self.assertIn("Thanh-nhàn riêng một cảnh tiên", dich_tho)

        # QA validation should pass with 0 errors on clean 4-col rows
        qa_res = validate_pairs(rows)
        self.assertTrue(qa_res["is_valid"])
        self.assertEqual(qa_res["missing_count"], 0)

    def test_tvlt2_work_03_instructor_supplement(self) -> None:
        """Verify TVLT2 work #3 Thiền tông chỉ nam tự supplement file, NFC encoding, and alignment."""
        supp_path = ROOT_DIR / "deliverables" / "TVLT2_ThoVanLyTran2" / "01_nguon" / "bai_03_thien_tong_chi_nam_tu_dich_nghia.txt"
        self.assertTrue(supp_path.is_file(), "Work 03 supplement text file must exist")
        text = supp_path.read_text(encoding="utf-8")
        self.assertEqual(unicodedata.normalize("NFC", text), text, "File must be Unicode NFC")
        self.assertIn("Trẫm thầm nghĩ: Phật không có nam bắc", text)
        self.assertIn("Thiền Tông Chỉ Nam", text)

        # Verify alignment includes work 03 pairs in TVLT2 parallel deliverable
        tsv_path = ROOT_DIR / "deliverables" / "TVLT2_ThoVanLyTran2" / "04_dong_hang" / "TVLT2_ThoVanLyTran2_parallel.tsv"
        pairs = read_tsv(str(tsv_path))
        found_work_03 = any("朕竊謂佛無南北" in p[0] for p in pairs)
        self.assertTrue(found_work_03, "TVLT2 parallel TSV must contain work 03 aligned sentence")

    def test_tltvn_instructor_supplement_inventory_report(self) -> None:
        """Verify the instructor supplement statistical report is complete and well-formatted."""
        doc_path = ROOT_DIR / "docs" / "THONG_KE_BO_SUNG_GIANG_VIEN.md"
        self.assertTrue(doc_path.is_file(), "docs/THONG_KE_BO_SUNG_GIANG_VIEN.md must exist")
        doc_text = doc_path.read_text(encoding="utf-8")
        self.assertEqual(unicodedata.normalize("NFC", doc_text), doc_text)

        # Check section 1: missing original text works
        self.assertIn("Phạm Thái", doc_text)
        self.assertIn("Sơ kính tân trang", doc_text)
        self.assertIn("Tây giang nguyệt", doc_text)
        self.assertIn("Lý Đạo Tái (Huyền Quang)", doc_text)
        self.assertIn("Nguyễn Huy Oánh", doc_text)
        self.assertIn("Phạm Nguyễn Du", doc_text)

        # Check section 2: Chinese-only volumes in Appendix 3
        self.assertIn("Phụ lục 3", doc_text)
        self.assertIn("THẠC ĐÌNH DI CẢO", doc_text)
        self.assertIn("HOA THIỀU NGÂM LỤC", doc_text)
        self.assertIn("LƯU HƯƠNG KÍ", doc_text)
        self.assertIn("CỔ DUỆ TỪ", doc_text)
        self.assertIn("Nguyễn Phúc Miên Thẩm", doc_text)
        self.assertIn("108 bài từ", doc_text)

    def test_qa_validator_catches_errors(self) -> None:
        bad_pairs = [
            ("鄭子產有疾", ""),  # MISSING
            ("天地玄黃宇宙洪荒日月盈昃辰宿列張", "Trời đất."),  # OMISSION (ratio < 0.7)
            ("故寬難", "PHIÊN ÂM : Cố khoan nan 1* [1]"),  # LEFTOVER_MARKER
            ("千重萬里涉滄浪", "Sóng xanh vượt qua biển rộng."),  # NUMBER_MISMATCH (千, 萬)
        ]
        report = validate_pairs(bad_pairs)
        self.assertFalse(report["is_valid"])
        self.assertGreaterEqual(report["missing_count"], 1)
        self.assertGreaterEqual(report["omission_count"], 1)
        self.assertGreaterEqual(report["leftover_marker_count"], 1)
        self.assertGreaterEqual(report["number_mismatch_count"], 1)


class TestKaggleOCRPipelineMockMode(unittest.TestCase):
    """Test kaggle_ocr/ocr_pipeline_kaggle.py preprocessing, layout grouping, and --dry-run mode."""

    def test_header_crop_and_footnote_separator_detection(self) -> None:
        # Construct a synthetic 200x100 grayscale image (2D list of white pixels = 255)
        # with a horizontal dark rule (pixel = 20) at row y = 150 (in the lower half)
        img = [[255 for _ in range(100)] for _ in range(200)]
        for x in range(10, 85):
            img[150][x] = 20

        cropped, meta = preprocess_page_image(img, book_type="TLTVN", header_ratio=0.07)
        self.assertEqual(meta["crop_top_px"], 14)
        self.assertEqual(meta["footnote_separator_y_original"], 150)
        self.assertEqual(meta["effective_height"], 150 - 14)

    def test_dry_run_on_extracted_pilot_pngs(self) -> None:
        for book_key, folder in (
            ("HVTT", "HVTT_HanVanTinhTuy"),
            ("TVLT2", "TVLT2_ThoVanLyTran2"),
            ("TLTVN", "TLTVN_TheLoaiTuVN"),
        ):
            book_dir = ROOT_DIR / "deliverables" / folder
            han_json_dir = book_dir / "02_ocr_tho" / "han"
            viet_json_dir = book_dir / "02_ocr_tho" / "viet"
            han_jsons = sorted(han_json_dir.glob("*.json"))
            viet_jsons = sorted(viet_json_dir.glob("*.json"))
            self.assertGreaterEqual(len(han_jsons), 5, f"Missing han OCR JSONs for {book_key}")
            self.assertEqual(len(han_jsons), len(viet_jsons))

            sample_payload = json.loads(han_jsons[0].read_text(encoding="utf-8"))
            self.assertEqual(sample_payload["book_type"], book_key)
            self.assertIn("preprocess", sample_payload)
            self.assertIn("items", sample_payload)
            self.assertGreater(len(sample_payload["items"]), 0)


@unittest.skipUnless((ROOT_DIR / ".agents").is_dir() and (ROOT_DIR / "AGENTS.md").is_file(), "Agent orchestration omitted in public repository")
class TestAgentSkillsAndOrchestration(unittest.TestCase):
    """Test integrated Agent Skills (spec-to-tickets, wayfinder, subagent-driven-development, handoff)."""

    def test_skills_and_agents_md_exist(self) -> None:
        self.assertTrue((ROOT_DIR / "AGENTS.md").is_file())
        for skill_name in (
            "subagent-driven-development",
            "spec-to-tickets",
            "wayfinder",
            "handoff",
        ):
            skill_md = ROOT_DIR / ".agents" / "skills" / skill_name / "SKILL.md"
            self.assertTrue(skill_md.is_file(), f"Missing SKILL.md for {skill_name}")
            text = skill_md.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\nname: " + skill_name))

    def test_tickets_schema_and_wayfinder_and_handoff(self) -> None:
        import subprocess

        # 1. Validate tickets schema & DAG
        proc_val = subprocess.run(
            [sys.executable, str(ROOT_DIR / ".agents/skills/spec-to-tickets/scripts/validate_tickets.py")],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc_val.returncode, 0, proc_val.stderr)
        val_json = json.loads(proc_val.stdout)
        self.assertTrue(val_json["valid"])
        self.assertGreaterEqual(val_json["ticket_count"], 8)

        # 2. Check Wayfinder next unblocked ticket
        proc_wf = subprocess.run(
            [sys.executable, str(ROOT_DIR / ".agents/skills/wayfinder/scripts/wayfinder.py"), "--next"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc_wf.returncode, 0, proc_wf.stderr)
        wf_json = json.loads(proc_wf.stdout)
        self.assertIsInstance(wf_json.get("ready_tickets"), list)
        if wf_json.get("ready_tickets"):
            next_tid = wf_json["ready_tickets"][0]["id"]
            self.assertTrue(
                next_tid.startswith("T") and len(next_tid) >= 3,
                f"Invalid ticket ID format: {next_tid}",
            )
        else:
            next_tid = "T01"

        self.assertTrue((ROOT_DIR / "docs" / "WAYFINDER.md").is_file())
        self.assertTrue((ROOT_DIR / "docs" / "HANDOFF.md").is_file())

        # 3. Check dispatch packet generation for next_tid
        proc_dp = subprocess.run(
            [
                sys.executable,
                str(ROOT_DIR / ".agents/skills/subagent-driven-development/scripts/dispatch_check.py"),
                "--ticket",
                next_tid,
                "--mode",
                "prompt",
            ],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc_dp.returncode, 0, proc_dp.stderr)
        self.assertIn(f"Subagent Dispatch Packet — [{next_tid}]", proc_dp.stdout)


class TestSemanticScorerAndInspector(unittest.TestCase):
    """Test CrossLingualSemanticScorer, inspect_alignment.py, and web_app headless check."""

    def test_semantic_scorer_offline_anchor_matrix(self) -> None:
        from src.semantic_scorer import CrossLingualSemanticScorer

        scorer = CrossLingualSemanticScorer(prefer_neural=False)
        self.assertEqual(scorer.backend_name, "offline_anchor")

        han_sents = [
            "朕竊謂佛無南北均可修求，性有智愚同資覺悟。",
            "風打松關月照庭，心期風景共淒清。",
        ]
        viet_sents = [
            "Trẫm thầm nghĩ: Phật không có nam bắc, mọi người đều có thể tu cầu.",
            "Gió đập cổng thông, trăng sáng trước sân.",
        ]
        sim_mat = scorer.compute_similarity_matrix(han_sents, viet_sents)
        self.assertEqual(len(sim_mat), 2)
        self.assertEqual(len(sim_mat[0]), 2)
        # Sentence 0 has 'Phật', sentence 1 has 'trăng' (nguyệt), diagonal should be higher than cross
        self.assertGreater(sim_mat[0][0], sim_mat[0][1])

    def test_terminal_inspector_cli_tool(self) -> None:
        import subprocess

        proc = subprocess.run(
            [sys.executable, str(ROOT_DIR / "scripts/inspect_alignment.py"), "--book", "HVTT", "--summary"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("HÁN–VIỆT CORPUS ALIGNMENT REPORT — [HVTT]", proc.stdout)
        self.assertIn("Error Rate", proc.stdout)

    def test_web_app_headless_loader(self) -> None:
        from web_app.app import run_headless_check

        summary = run_headless_check()
        self.assertEqual(set(summary.keys()), {"HVTT", "TVLT2", "TLTVN"})
        for book_k, info in summary.items():
            self.assertGreater(info["row_count"], 0)
            self.assertTrue(info["is_valid"])
            self.assertEqual(info["error_rate"], 0.0)
            self.assertTrue(info["tsv_exists"])
            self.assertTrue(info["xlsx_exists"])


class TestHuggingFacePackagingAndNMTBenchmark(unittest.TestCase):
    """Test Hugging Face dataset export, split ratios, data card, and translation evaluation benchmark."""

    def test_huggingface_packaging_and_splits(self) -> None:
        from scripts.package_hf_dataset import package_dataset

        temp_export_dir = ROOT_DIR / "dataset_export"
        res = package_dataset(temp_export_dir)
        self.assertGreaterEqual(res["total_records"], 30)
        self.assertGreater(res["train"], 0)
        self.assertGreater(res["validation"], 0)
        self.assertGreater(res["test"], 0)

        # Verify files exist and are valid JSONL
        for name in ("train.jsonl", "validation.jsonl", "test.jsonl"):
            split_file = temp_export_dir / name
            self.assertTrue(split_file.is_file())
            lines = split_file.read_text(encoding="utf-8").splitlines()
            self.assertGreater(len(lines), 0)
            sample_rec = json.loads(lines[0])
            self.assertIn("classical_chinese", sample_rec)
            self.assertIn("vietnamese_translation", sample_rec)

        # Verify README data card
        readme_path = temp_export_dir / "README.md"
        self.assertTrue(readme_path.is_file())
        readme_text = readme_path.read_text(encoding="utf-8")
        self.assertIn("language:\n- lzh\n- vi", readme_text)

    def test_downstream_nmt_benchmark_evaluator(self) -> None:
        from scripts.eval_translation_benchmark import evaluate_benchmark

        test_jsonl = ROOT_DIR / "dataset_export" / "test.jsonl"
        self.assertTrue(test_jsonl.is_file())
        res = evaluate_benchmark(test_jsonl)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertGreater(res["test_samples_count"], 0)
        self.assertEqual(res["corpus_bleu"], 100.0)
        self.assertEqual(res["avg_rouge_l_f1"], 100.0)
        self.assertEqual(res["avg_chrf"], 100.0)


if __name__ == "__main__":
    unittest.main()
