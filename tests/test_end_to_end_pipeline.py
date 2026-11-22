"""Integration & unit tests for the End-to-End OCR-to-Alignment Pipeline."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from kaggle_ocr.ocr_pipeline_kaggle import (
    classify_section_header,
    group_layout_blocks,
    is_stop_section_header,
    resolve_ocr_output_dirs,
)
from scripts.run_end_to_end import run_end_to_end
from src.corpus_pipeline import run_corpus_from_ocr
from src.exporter_and_qa import read_tsv, read_xlsx_zero_dep


class TestEndToEndCorpusPipeline(unittest.TestCase):
    """Verify full end-to-end orchestration strictly from OCR JSON outputs."""

    def test_hvtt_four_column_and_facing_dich_tho_grouping(self) -> None:
        han_items = [
            {"bbox": [[100, 100], [900, 100], [900, 140], [100, 140]], "text": "鄭子產有疾"}
        ]
        viet_items = [
            {"bbox": [[100, 150], [900, 150], [900, 190], [100, 190]], "text": "Trịnh Tử Sản hữu tật", "role": "phien_am"},
            {"bbox": [[100, 200], [900, 200], [900, 240], [100, 240]], "text": "Trịnh Tử Sản ốm", "role": "dich_nghia_gloss"},
            {"bbox": [[100, 300], [900, 300], [900, 340], [100, 340]], "text": "DỊCH THƠ : Tử Sản lâm bệnh"},
        ]
        res_even = group_layout_blocks(han_items, viet_items, book_type="HVTT", page_num=12)
        self.assertEqual(res_even["dich_tho_lines"], ["Tử Sản lâm bệnh"])
        self.assertEqual(res_even["dich_nghia_lines"], ["Trịnh Tử Sản ốm"])

        # Final poem pages (>= 367) must strip Dich nghia while keeping Dich tho
        res_final = group_layout_blocks(han_items, viet_items, book_type="HVTT", page_num=368)
        self.assertEqual(res_final["dich_nghia_lines"], [])
        self.assertEqual(res_final["dich_tho_lines"], ["Tử Sản lâm bệnh"])

    def test_resolve_ocr_output_dirs_prevents_double_nesting(self) -> None:
        book_root = Path("/tmp/deliverables/HVTT_HanVanTinhTuy")
        han_dir, viet_dir = resolve_ocr_output_dirs(book_root, book_folder="HVTT_HanVanTinhTuy")
        self.assertEqual(han_dir, book_root / "02_ocr_tho" / "han")
        self.assertEqual(viet_dir, book_root / "02_ocr_tho" / "viet")

    def test_cross_page_buffering_in_sequential_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            ocr_han = tmp_root / "deliverables" / "TVLT2_ThoVanLyTran2" / "02_ocr_tho" / "han"
            ocr_viet = tmp_root / "deliverables" / "TVLT2_ThoVanLyTran2" / "02_ocr_tho" / "viet"
            ocr_han.mkdir(parents=True)
            ocr_viet.mkdir(parents=True)

            # Page 17 has only Classical Chinese; Page 18 has the Dịch nghĩa translation
            (ocr_han / "0017.json").write_text(json.dumps({
                "page_num": 17,
                "book_type": "TVLT2",
                "preprocess": {"effective_width": 2000},
                "items": [{"bbox": [[100, 100], [900, 100], [900, 140], [100, 140]], "text": "風打松關月照庭。"}],
            }), encoding="utf-8")
            (ocr_viet / "0017.json").write_text(json.dumps({
                "page_num": 17,
                "book_type": "TVLT2",
                "items": [],
            }), encoding="utf-8")

            (ocr_han / "0018.json").write_text(json.dumps({
                "page_num": 18,
                "book_type": "TVLT2",
                "preprocess": {"effective_width": 2000},
                "items": [],
            }), encoding="utf-8")
            (ocr_viet / "0018.json").write_text(json.dumps({
                "page_num": 18,
                "book_type": "TVLT2",
                "items": [
                    {"bbox": [[100, 200], [500, 200], [500, 240], [100, 240]], "text": "DỊCH NGHĨA :"},
                    {"bbox": [[100, 260], [1600, 260], [1600, 300], [100, 300]], "text": "Gió đập cổng thông, trăng chiếu trước sân."},
                ],
            }), encoding="utf-8")

            summary = run_corpus_from_ocr(
                workspace_root=tmp_root,
                ocr_root=tmp_root,
                book_filter="TVLT2",
                pilot_only=False,
            )
            tvlt_info = summary["books"]["TVLT2"]
            self.assertEqual(tvlt_info["pair_count"], 1)
            self.assertTrue(tvlt_info["is_valid"])
            self.assertTrue(tvlt_info["tsv_xlsx_identical"])
            rows = read_tsv(tvlt_info["tsv_path"])
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(rows[0]), 4)
            self.assertEqual(rows[0][0], "風打松關月照庭。")
            self.assertEqual(rows[0][1], "")
            self.assertEqual(rows[0][2], "Gió đập cổng thông, trăng chiếu trước sân.")
            self.assertEqual(rows[0][3], "")

    def test_hvtt_running_header_and_vertical_band_triplet_grouping(self) -> None:
        han_items = [
            {"bbox": [[98, 93], [967, 93], [967, 183], [98, 183]], "text": "鄭子產有疾謂子太叔曰"},
            {"bbox": [[128, 296], [627, 296], [627, 358], [128, 358]], "text": "我死子必為政"},
        ]
        viet_items = [
            {"bbox": [[648, 0], [1053, 0], [1053, 34], [648, 34]], "text": "HAN-VAN TINH-TUY"},
            {"bbox": [[83, 157], [1048, 157], [1048, 233], [83, 233]], "text": "Trịnh Tử-Sản hữu tật, vị tử Thái-Thúc viết :"},
            {"bbox": [[82, 213], [1047, 213], [1047, 287], [82, 287]], "text": "Trịnh Tử-Sản bệnh nặng, bảo con là Thái-Thúc rằng :"},
            {"bbox": [[109, 353], [594, 353], [594, 408], [109, 408]], "text": "Ngã tử, tử tất vi chính."},
            {"bbox": [[107, 403], [687, 403], [687, 460], [107, 460]], "text": "Ta chết, con sẽ giữ chính-quyền."},
        ]
        res = group_layout_blocks(han_items, viet_items, book_type="HVTT", page_num=8)
        self.assertEqual(len(res["interlinear_triplets"]), 2)
        self.assertEqual(res["interlinear_triplets"][0]["chu_han"], "鄭子產有疾謂子太叔曰")
        self.assertEqual(res["interlinear_triplets"][0]["phien_am"], "Trịnh Tử-Sản hữu tật, vị tử Thái-Thúc viết :")
        self.assertEqual(res["interlinear_triplets"][0]["dich_nghia_gloss"], "Trịnh Tử-Sản bệnh nặng, bảo con là Thái-Thúc rằng :")
        self.assertEqual(res["interlinear_triplets"][1]["phien_am"], "Ngã tử, tử tất vi chính.")
        self.assertEqual(res["interlinear_triplets"][1]["dich_nghia_gloss"], "Ta chết, con sẽ giữ chính-quyền.")

    def test_noisy_folded_section_header_classification(self) -> None:
        self.assertEqual(classify_section_header("DICH NGITA"), "dich_nghia")
        self.assertEqual(classify_section_header("DICH NGH1A :"), "dich_nghia")
        self.assertEqual(classify_section_header("Phien am:"), "phien_am")
        self.assertEqual(classify_section_header("DIGH THO :"), "dich_tho")
        self.assertFalse(is_stop_section_header("DIGH THO :"))
        self.assertEqual(classify_section_header("KHẢO ĐÍNH :"), "stop")
        self.assertTrue(is_stop_section_header("CHU THICH :"))

    def test_inline_cjk_exclusion_and_tltvn_numbered_footnote_cutoff(self) -> None:
        han_items = [
            {"bbox": [[100, 10], [500, 10], [500, 50], [100, 50]], "text": "祥光風好錦帆張"},
            {"bbox": [[60, 424], [1000, 424], [1000, 468], [60, 468]], "text": "thi Lê ghi là Ngọc lang quy (玉郎歸), bản thời Nguyễn"},
        ]
        viet_items = [
            {"bbox": [[100, 68], [281, 68], [281, 114], [100, 114]], "text": "Phien am:"},
            {"bbox": [[110, 120], [780, 120], [780, 170], [110, 170]], "text": "Tường quang phong hảo cẩm phàm trương,"},
            {"bbox": [[100, 180], [281, 180], [281, 220], [100, 220]], "text": "Dịch nghĩa:"},
            {"bbox": [[110, 225], [820, 225], [820, 270], [110, 270]], "text": "Ánh sáng tốt lành, gió thuận căng buồm gấm."},
            {"bbox": [[125, 383], [1073, 383], [1073, 432], [125, 432]], "text": "1 Ngọc lang quy: Nguyên bài này trong Thiền uyển."},
        ]
        res = group_layout_blocks(han_items, viet_items, book_type="TLTVN", page_num=135)
        self.assertEqual(res["chu_han_lines"], ["祥光風好錦帆張"])
        self.assertEqual(res["phien_am_lines"], ["Tường quang phong hảo cẩm phàm trương,"])
        self.assertEqual(res["dich_nghia_lines"], ["Ánh sáng tốt lành, gió thuận căng buồm gấm."])

    def test_run_corpus_detects_kaggle_gpu_from_page_engine_without_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            ocr_han = tmp_root / "deliverables" / "TVLT2_ThoVanLyTran2" / "02_ocr_tho" / "han"
            ocr_viet = tmp_root / "deliverables" / "TVLT2_ThoVanLyTran2" / "02_ocr_tho" / "viet"
            ocr_han.mkdir(parents=True)
            ocr_viet.mkdir(parents=True)

            (ocr_han / "0019.json").write_text(json.dumps({
                "page_num": 19,
                "book_type": "TVLT2",
                "engine": "paddleocr_chinese_cht",
                "preprocess": {"effective_width": 1600},
                "items": [{"bbox": [[100, 100], [600, 100], [600, 140], [100, 140]], "text": "風打松關月照庭。"}],
            }), encoding="utf-8")
            (ocr_viet / "0019.json").write_text(json.dumps({
                "page_num": 19,
                "book_type": "TVLT2",
                "engine": "vietocr_vgg_transformer",
                "items": [
                    {"bbox": [[100, 200], [300, 200], [300, 240], [100, 240]], "text": "DICH NGITA"},
                    {"bbox": [[100, 260], [1200, 260], [1200, 300], [100, 300]], "text": "Gió đập cổng thông, trăng chiếu trước sân."},
                ],
            }), encoding="utf-8")

            summary = run_corpus_from_ocr(
                workspace_root=tmp_root,
                ocr_root=tmp_root,
                book_filter="TVLT2",
                pilot_only=False,
            )
            info = summary["books"]["TVLT2"]
            self.assertEqual(info["ocr_mode"], "kaggle_gpu")
            self.assertEqual(info["pair_count"], 1)

    def test_run_end_to_end_pilot_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            (tmp_root / "config").mkdir(parents=True, exist_ok=True)
            manifest = json.loads((ROOT_DIR / "config" / "book_manifest.json").read_text(encoding="utf-8"))
            shutil.copy2(ROOT_DIR / "config" / "book_manifest.json", tmp_root / "config" / "book_manifest.json")

            for cfg in manifest["books"].values():
                src_dir = ROOT_DIR / cfg["source_dir"]
                dst_dir = tmp_root / cfg["source_dir"]
                dst_dir.mkdir(parents=True, exist_ok=True)
                for pnum in cfg.get("pilot_pages", []):
                    src_png = src_dir / f"{int(pnum):04d}.png"
                    if src_png.is_file():
                        dst_png = dst_dir / src_png.name
                        try:
                            os.link(src_png, dst_png)
                        except OSError:
                            shutil.copy2(src_png, dst_png)

            supp_rel = Path("deliverables/TVLT2_ThoVanLyTran2/01_nguon/bai_03_thien_tong_chi_nam_tu_dich_nghia.txt")
            if (ROOT_DIR / supp_rel).is_file():
                (tmp_root / supp_rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT_DIR / supp_rel, tmp_root / supp_rel)

            res = run_end_to_end(
                workspace_root=tmp_root,
                pilot_only=True,
                run_downstream=False,
            )
            self.assertEqual(res["status"], "SUCCESS")
            books = res["alignment_stage"]["books"]
            expected_header = ("Hán", "Dịch âm", "Dịch nghĩa", "Dịch thơ")
            for b_key in ("HVTT", "TVLT2", "TLTVN"):
                self.assertIn(b_key, books)
                self.assertTrue(books[b_key]["is_valid"])
                self.assertEqual(books[b_key]["error_rate"], 0.0)
                self.assertTrue(books[b_key]["tsv_xlsx_identical"])
                self.assertGreater(books[b_key]["pair_count"], 0)
                self.assertGreater(books[b_key]["dich_tho_populated"], 0)
                tsv_rows = read_tsv(books[b_key]["tsv_path"])
                xlsx_with_header = read_xlsx_zero_dep(
                    books[b_key]["xlsx_path"],
                    sheet_name="DONG_HANG",
                    include_header=True,
                )
                self.assertEqual(xlsx_with_header[0], expected_header)
                self.assertEqual(tsv_rows, xlsx_with_header[1:])
                self.assertTrue(all(len(r) == 4 for r in tsv_rows))

            hvtt_rows = read_tsv(books["HVTT"]["tsv_path"])
            self.assertGreaterEqual(books["HVTT"]["title_rows"], 2)
            self.assertTrue(any(r[0] == "秋夜旅懷吟" and r[3] == "" for r in hvtt_rows))
            self.assertTrue(any(r[2] == "" and r[3].strip() for r in hvtt_rows))


if __name__ == "__main__":
    unittest.main()
