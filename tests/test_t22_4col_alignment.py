"""Unit and integration tests for Ticket T22: 4-column alignment, titles, facing Dịch thơ, and demos."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path
from typing import Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.aligner import (
    align_hvtt_facing_dich_tho,
    align_interlinear_4col_blocks,
    align_phien_am_to_han_chunks,
)
from src.corpus_pipeline import run_corpus_from_ocr
from src.exporter_and_qa import read_tsv, read_xlsx_zero_dep, validate_pairs


def _write_ocr_pair(
    ocr_root: Path,
    book_dir: str,
    page_id: str,
    book_type: str,
    han_lines: List[str],
    viet_lines: List[str],
    layout_summary: Dict,
    han_boxes: Optional[List[List[int]]] = None,
    viet_boxes: Optional[List[List[int]]] = None,
) -> None:
    han_dir = ocr_root / "deliverables" / book_dir / "02_ocr_tho" / "han"
    viet_dir = ocr_root / "deliverables" / book_dir / "02_ocr_tho" / "viet"
    han_dir.mkdir(parents=True, exist_ok=True)
    viet_dir.mkdir(parents=True, exist_ok=True)

    han_items = []
    for i, txt in enumerate(han_lines):
        box = han_boxes[i] if han_boxes and i < len(han_boxes) else [100, 100 + i * 70, 800, 145 + i * 70]
        han_items.append({"line_id": f"{page_id}_han_{i:03d}", "box_xyxy": box, "text": txt, "confidence": 0.99})

    viet_items = []
    for i, txt in enumerate(viet_lines):
        box = viet_boxes[i] if viet_boxes and i < len(viet_boxes) else [100, 100 + i * 70, 900, 145 + i * 70]
        viet_items.append({"line_id": f"{page_id}_viet_{i:03d}", "box_xyxy": box, "text": txt, "confidence": 0.99})

    (han_dir / f"{page_id}.json").write_text(
        json.dumps(
            {
                "page_id": page_id,
                "book_type": book_type,
                "page_num": int(page_id),
                "preprocess": {"original_width": 1188, "effective_width": 1188, "effective_height": 1607},
                "items": han_items,
                "layout_summary": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (viet_dir / f"{page_id}.json").write_text(
        json.dumps(
            {
                "page_id": page_id,
                "book_type": book_type,
                "page_num": int(page_id),
                "preprocess": {"original_width": 1188, "effective_width": 1188, "effective_height": 1607},
                "items": viet_items,
                "layout_summary": layout_summary,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


class TestFacingDichThoAnd4ColHelpers(unittest.TestCase):
    def test_empty_dich_tho_returns_blank_slots(self) -> None:
        rows = [{"han": "A。", "dich_am": "a", "dich_nghia": "aa"}] * 3
        self.assertEqual(align_hvtt_facing_dich_tho(rows, []), ["", "", ""])

    def test_one_to_one_facing_dich_tho(self) -> None:
        rows = [
            {"han": "鄭子產有疾。", "dich_am": "Trịnh Tử-Sản hữu tật.", "dich_nghia": "Bệnh nặng."},
            {"han": "我死子必為政。", "dich_am": "Ngã tử tử tất vi chính.", "dich_nghia": "Con cầm quyền."},
        ]
        dt = ["Tử-Sản bệnh nặng,", "Con giữ chính quyền."]
        self.assertEqual(align_hvtt_facing_dich_tho(rows, dt), dt)

    def test_one_to_many_spread_joins_with_slash_and_drops_zero_lines(self) -> None:
        rows = [
            {"han": "鄭子產有疾，謂子太叔曰：", "dich_am": "Trịnh Tử-Sản hữu tật...", "dich_nghia": "Bảo Thái-Thúc rằng:"},
            {"han": "我死，子必為政。", "dich_am": "Ngã tử, tử tất vi chính.", "dich_nghia": "Ta chết con cầm quyền."},
            {"han": "惟有德者，能以寬服民。", "dich_am": "Duy hữu đức giả...", "dich_nghia": "Có đức lấy khoan phục dân."},
        ]
        dt = [
            "Tử-Sản bệnh, khó bề bình-phục",
            "Bèn dặn con, Thái-Thúc, mấy lời:",
            "Khi cha khuất bóng đi rồi,",
            "Chính-quyền nước Trịnh sẽ dời về con.",
            "Có đức thì hãy dụng khoan hòa,",
            "Lòng dân mến-phục sâu-xa.",
        ]
        out = align_hvtt_facing_dich_tho(rows, dt)
        self.assertEqual(len(out), 3)
        joined_all = " / ".join(out)
        for line in dt:
            self.assertIn(line, joined_all)
        self.assertIn(" / ", out[0])

    def test_many_to_one_with_y_centers_preserves_every_line(self) -> None:
        rows = [
            {"han": "不忍猛而寬。", "dich_am": "Bất nhẫn mãnh nhi khoan.", "dich_nghia": "Không nỡ mạnh nên khoan."},
            {"han": "鄭國多盜。", "dich_am": "Trịnh-quốc đa đạo.", "dich_nghia": "Nước Trịnh nhiều trộm cướp."},
            {"han": "取人於萑苻之澤。", "dich_am": "Thủ nhân ư hoàn bồ chi trạch.", "dich_nghia": "Bắt người ở bãi chằm."},
        ]
        dt = ["Con lên mở lượng khoan-hồng,", "Thế là giặc cướp nổi cùng khắp nơi."]
        out = align_hvtt_facing_dich_tho(
            rows,
            dt,
            han_y_centers=[200.0, 450.0, 750.0],
            dt_y_centers=[210.0, 500.0],
        )
        self.assertEqual(len(out), 3)
        combined = " ".join(out)
        for line in dt:
            self.assertIn(line, combined)

    def test_is_title_blocks_never_merge_with_body_rows(self) -> None:
        blocks = [
            {
                "han": "子產授政太叔",
                "dich_am": "TỬ-SẢN THỤ CHÍNH THÁI-THÚC",
                "dich_nghia": "TỬ SẢN DẶN CON PHÉP TRỊ DÂN",
                "dich_tho": "",
                "is_title": True,
            },
            {
                "han": "",
                "dich_am": "",
                "dich_nghia": "Tiểu dẫn không được gộp vào dòng tiêu đề.",
                "dich_tho": "",
                "is_title": False,
            },
            {
                "han": "鄭子產有疾，",
                "dich_am": "Trịnh Tử-Sản hữu tật,",
                "dich_nghia": "Trịnh Tử-Sản ốm,",
                "dich_tho": "",
            },
            {
                "han": "",
                "dich_am": "",
                "dich_nghia": "bảo Thái-Thúc rằng.",
                "dich_tho": "",
            },
        ]
        rows = align_interlinear_4col_blocks(blocks)
        self.assertEqual(rows[0], ("子產授政太叔", "TỬ-SẢN THỤ CHÍNH THÁI-THÚC", "TỬ SẢN DẶN CON PHÉP TRỊ DÂN", ""))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][2], "Trịnh Tử-Sản ốm, bảo Thái-Thúc rằng.")

    def test_phien_am_truncated_prefix_projection(self) -> None:
        han_chunks = ["朕竊謂佛無南北。", "性有智愚。", "師曰山本無佛。"]
        pa_lines = ["Trẫm thiết vị Phật vô Nam Bắc.", "Tính hữu trí ngu."]
        projected = align_phien_am_to_han_chunks(han_chunks, pa_lines)
        self.assertEqual(len(projected), 3)
        self.assertEqual(projected[0], "Trẫm thiết vị Phật vô Nam Bắc.")
        self.assertEqual(projected[1], "Tính hữu trí ngu.")
        self.assertEqual(projected[2], "")


class TestCorpusPipeline4ColIntegration(unittest.TestCase):
    def test_hvtt_title_facing_dich_tho_and_no_dich_nghia_page(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            manifest_path = tmp_path / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "books": {
                            "HVTT": {
                                "book_id": "HVTT",
                                "code": "HVTT_HanVanTinhTuy",
                                "deliverable_dir": "deliverables/HVTT_HanVanTinhTuy",
                                "clean_text_dir": "deliverables/HVTT_HanVanTinhTuy/03_text_sach",
                                "alignment_dir": "deliverables/HVTT_HanVanTinhTuy/04_dong_hang",
                                "valid_range": {"pdf_page_start": 7, "pdf_page_end": 102},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            stale_dir = tmp_path / "deliverables/HVTT_HanVanTinhTuy/04_dong_hang"
            stale_dir.mkdir(parents=True, exist_ok=True)
            (stale_dir / "HVTT_parallel.tsv").write_text("stale\n", encoding="utf-8")
            (stale_dir / "HVTT_parallel.xlsx").write_text("stale\n", encoding="utf-8")

            _write_ocr_pair(
                tmp_path,
                "HVTT_HanVanTinhTuy",
                "0007",
                "HVTT",
                ["子產授政太叔"],
                ["TỬ-SẢN THỤ CHÍNH THÁI-THÚC", "TỬ SẢN DẶN CON PHÉP TRỊ DÂN", "Tả Khâu Minh"],
                {"layout_mode": "odd_title_page"},
                han_boxes=[[403, 328, 843, 380]],
                viet_boxes=[[297, 397, 879, 449], [285, 501, 902, 552], [748, 673, 986, 708]],
            )
            _write_ocr_pair(
                tmp_path,
                "HVTT_HanVanTinhTuy",
                "0008",
                "HVTT",
                ["鄭子產有疾，謂子太叔曰", "我死，子必為政。"],
                [
                    "Trịnh Tử-Sản hữu tật, vị tử Thái-Thúc viết",
                    "Trịnh Tử-Sản bệnh nặng, bảo con là Thái-Thúc rằng",
                    "Ngã tử, tử tất vi chính.",
                    "Ta chết, con sẽ giữ chính-quyền.",
                ],
                {"layout_mode": "even_page_interlinear"},
                han_boxes=[[160, 200, 980, 245], [160, 500, 980, 545]],
                viet_boxes=[
                    [160, 260, 980, 305],
                    [160, 320, 980, 365],
                    [160, 560, 980, 605],
                    [160, 620, 980, 665],
                ],
            )
            _write_ocr_pair(
                tmp_path,
                "HVTT_HanVanTinhTuy",
                "0009",
                "HVTT",
                [],
                ["Tử-Sản bệnh, khó bề bình-phục", "Khi cha khuất bóng đi rồi."],
                {"layout_mode": "odd_page_dich_tho"},
                viet_boxes=[[220, 220, 900, 265], [220, 520, 900, 565]],
            )
            _write_ocr_pair(
                tmp_path,
                "HVTT_HanVanTinhTuy",
                "0100",
                "HVTT",
                ["存者且偷生，", "死者長已矣。"],
                ["Tồn giả thả thâu sinh,", "Tử giả trường dĩ hĩ."],
                {"layout_mode": "even_page_interlinear"},
                han_boxes=[[160, 200, 980, 245], [160, 500, 980, 545]],
                viet_boxes=[[160, 265, 980, 310], [160, 565, 980, 610]],
            )
            _write_ocr_pair(
                tmp_path,
                "HVTT_HanVanTinhTuy",
                "0101",
                "HVTT",
                [],
                ["Kẻ sống chạy lấy thân,", "Người chết đành vùi đó."],
                {"layout_mode": "odd_page_dich_tho"},
                viet_boxes=[[220, 220, 900, 265], [220, 520, 900, 565]],
            )

            summary = run_corpus_from_ocr(workspace_root=tmp_path, ocr_root=tmp_path, manifest_path=manifest_path)
            hvtt = summary["books"]["HVTT"]
            self.assertEqual(hvtt["missing_count"], 0)
            self.assertGreaterEqual(hvtt["title_rows"], 1)
            self.assertEqual(hvtt["dich_tho_populated"], 4)
            self.assertTrue(hvtt["tsv_xlsx_identical"])
            self.assertFalse((stale_dir / "HVTT_parallel.tsv").exists())
            self.assertFalse((stale_dir / "HVTT_parallel.xlsx").exists())

            rows = read_tsv(hvtt["tsv_path"])
            self.assertEqual(rows[0], ("子產授政太叔", "TỬ-SẢN THỤ CHÍNH THÁI-THÚC", "TỬ SẢN DẶN CON PHÉP TRỊ DÂN", ""))
            self.assertEqual(rows[1][3], "Tử-Sản bệnh, khó bề bình-phục")
            self.assertEqual(rows[-2], ("存者且偷生，", "Tồn giả thả thâu sinh,", "", "Kẻ sống chạy lấy thân,"))

    def test_tltvn_4col_suite_and_dich_theo_nguyen_dieu(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            manifest_path = tmp_path / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "books": {
                            "TLTVN": {
                                "book_id": "TLTVN",
                                "code": "TLTVN_TheLoaiTuVN",
                                "deliverable_dir": "deliverables/TLTVN_TheLoaiTuVN",
                                "clean_text_dir": "deliverables/TLTVN_TheLoaiTuVN/03_text_sach",
                                "alignment_dir": "deliverables/TLTVN_TheLoaiTuVN/04_dong_hang",
                                "valid_range": {"pdf_page_start": 134, "pdf_page_end": 547},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            _write_ocr_pair(
                tmp_path,
                "TLTVN_TheLoaiTuVN",
                "0134",
                "TLTVN",
                ["阮郎歸", "祥光風好錦帆張，", "神仙復帝鄉。"],
                [],
                {"layout_mode": "han_only"},
            )
            _write_ocr_pair(
                tmp_path,
                "TLTVN_TheLoaiTuVN",
                "0135",
                "TLTVN",
                [],
                [
                    "Phiên âm:",
                    "Nguyễn lang quy",
                    "Tường quang phong hảo cẩm phàm trương,",
                    "Thần tiên phục đế hương.",
                ],
                {"layout_mode": "tltvn_viet"},
            )
            _write_ocr_pair(
                tmp_path,
                "TLTVN_TheLoaiTuVN",
                "0136",
                "TLTVN",
                [],
                [
                    "Dịch nghĩa:",
                    "Điệu Nguyễn lang quy",
                    "Ánh sáng tốt lành, gió thuận, căng cánh buồm gấm,",
                    "Thần tiên trở về quê hương của hoàng đế.",
                    "Dịch theo nguyên điệu:",
                    "Trời trong gió mát cánh buồm giương,",
                    "Thần tiên về đế hương.",
                ],
                {"layout_mode": "tltvn_viet"},
            )

            summary = run_corpus_from_ocr(workspace_root=tmp_path, ocr_root=tmp_path, manifest_path=manifest_path)
            tltvn = summary["books"]["TLTVN"]
            self.assertEqual(tltvn["missing_count"], 0)
            self.assertTrue(tltvn["tsv_xlsx_identical"])
            rows = read_tsv(tltvn["tsv_path"])
            self.assertTrue(all(len(r) == 4 for r in rows))
            self.assertEqual(rows[0][0], "阮郎歸")
            self.assertEqual(
                rows[1],
                (
                    "祥光風好錦帆張，",
                    "Tường quang phong hảo cẩm phàm trương,",
                    "Ánh sáng tốt lành, gió thuận, căng cánh buồm gấm,",
                    "Trời trong gió mát cánh buồm giương,",
                ),
            )

    def test_khoa_397_plus_1_and_demo_giang_vien_deliverables(self) -> None:
        summary_file = ROOT_DIR / "outputs/khoa/alignment_summary.json"
        self.assertTrue(summary_file.is_file())
        summary = json.loads(summary_file.read_text(encoding="utf-8"))
        self.assertGreaterEqual(summary["total_pairs"], 2000)
        self.assertEqual(
            summary["total_pairs"],
            sum(summary["books"][bk]["pair_count"] for bk in ("HVTT", "TVLT2", "TLTVN")),
        )

        expected_header = ("Hán", "Dịch âm", "Dịch nghĩa", "Dịch thơ")
        for bk, code in (
            ("HVTT", "HVTT_HanVanTinhTuy"),
            ("TVLT2", "TVLT2_ThoVanLyTran2"),
            ("TLTVN", "TLTVN_TheLoaiTuVN"),
        ):
            info = summary["books"][bk]
            self.assertEqual(info["missing_count"], 0)
            self.assertLessEqual(info["error_rate"], 0.25)
            self.assertTrue(info["is_valid"])
            self.assertTrue(info["tsv_xlsx_identical"])

            tsv_path = ROOT_DIR / info["tsv_path"]
            xlsx_path = ROOT_DIR / info["xlsx_path"]
            self.assertTrue(tsv_path.is_file())
            self.assertTrue(xlsx_path.is_file())
            self.assertEqual(tsv_path.name, f"{code}_parallel.tsv")
            self.assertEqual(xlsx_path.name, f"{code}_parallel.xlsx")

            rows = read_tsv(tsv_path)
            xlsx_with_header = read_xlsx_zero_dep(str(xlsx_path), sheet_name="DONG_HANG", include_header=True)
            self.assertEqual(xlsx_with_header[0], expected_header)
            self.assertEqual(rows, xlsx_with_header[1:])
            self.assertTrue(all(len(r) == 4 for r in rows))
            stats_rows = read_xlsx_zero_dep(str(xlsx_path), sheet_name="THONG_KE", include_header=True)
            self.assertEqual(stats_rows[0], ("Chỉ số", "Giá trị"))

            align_dir = tsv_path.parent
            self.assertFalse((align_dir / f"{bk}_parallel.tsv").exists())
            self.assertFalse((align_dir / f"{bk}_parallel.xlsx").exists())

            khoa_book_dir = ROOT_DIR / "outputs/khoa/deliverables" / code
            for sub in (
                "01_nguon/han",
                "01_nguon/viet",
                "02_ocr_tho/han",
                "02_ocr_tho/viet",
            ):
                sub_dir = khoa_book_dir / sub
                self.assertTrue(sub_dir.is_dir(), f"Missing {sub_dir}")
                self.assertGreater(len(list(sub_dir.iterdir())), 0, f"Empty {sub_dir}")
            for txt_rel in ("03_text_sach/han.txt", "03_text_sach/viet.txt"):
                txt_path = khoa_book_dir / txt_rel
                self.assertTrue(txt_path.is_file(), f"Missing {txt_path}")
                self.assertEqual(len(txt_path.read_text(encoding="utf-8").splitlines()), len(rows))

        # Assert zero credential/cookie/token files exist anywhere under deliverables/ or outputs/
        for base_dir in (ROOT_DIR / "deliverables", ROOT_DIR / "outputs"):
            if not base_dir.exists():
                continue
            for p in base_dir.rglob("*"):
                if p.is_file():
                    lower_name = p.name.lower()
                    self.assertFalse(
                        any(tok in lower_name for tok in (".cookie", "token", "credential", "kaggle.json")),
                        f"Credential/cookie artifact must not exist in deliverables/outputs: {p}",
                    )

        demo_dir = ROOT_DIR / "demo_giang_vien"
        for demo_name in ("HVTT_demo", "TVLT2_demo", "TLTVN_demo"):
            tsv_rows = read_tsv(demo_dir / f"{demo_name}.tsv")
            xlsx_header_rows = read_xlsx_zero_dep(
                str(demo_dir / f"{demo_name}.xlsx"), sheet_name="DONG_HANG", include_header=True
            )
            self.assertEqual(xlsx_header_rows[0], expected_header)
            self.assertEqual(tsv_rows, xlsx_header_rows[1:])
            self.assertTrue(all(len(r) == 4 for r in tsv_rows))
            stats_rows = read_xlsx_zero_dep(
                str(demo_dir / f"{demo_name}.xlsx"), sheet_name="THONG_KE", include_header=True
            )
            self.assertEqual(stats_rows[0], ("Chỉ số", "Giá trị"))
            qa = validate_pairs(tsv_rows)
            self.assertEqual(qa["error_pairs"], 0)
            self.assertEqual(qa["error_rate"], 0.0)

        hvtt_demo = read_tsv(demo_dir / "HVTT_demo.tsv")
        self.assertEqual(
            hvtt_demo[0],
            ("子產授政太叔", "TỬ-SẢN THỤ CHÍNH THÁI-THÚC", "TỬ SẢN DẶN CON PHÉP TRỊ DÂN", ""),
        )
        self.assertTrue(any(r[3].strip() for r in hvtt_demo[1:9]))
        self.assertTrue(
            any(r[0] == "秋夜旅懷吟" and r[1] == "THU DẠ HOÀI NGÂM" and r[3] == "" for r in hvtt_demo)
        )
        self.assertTrue(any(r[0].startswith("仙家") and r[2] == "" and r[3].strip() for r in hvtt_demo))

        tvlt2_demo = read_tsv(demo_dir / "TVLT2_demo.tsv")
        self.assertEqual(tvlt2_demo[0][0], "寄清風庵僧德山")
        self.assertTrue(any(r[3].strip() for r in tvlt2_demo[:8]))
        self.assertTrue(any(r[0] == "禪宗指南序" and r[3] == "" for r in tvlt2_demo))
        self.assertTrue(any("朕竊謂佛無南北" in r[0] and r[2].strip() and r[3] == "" for r in tvlt2_demo))

        tltvn_demo = read_tsv(demo_dir / "TLTVN_demo.tsv")
        self.assertEqual(tltvn_demo[0], ("阮郎歸", "Nguyễn lang quy", "Điệu Nguyễn lang quy", ""))
        self.assertTrue(all(r[3].strip() for r in tltvn_demo[1:]))

        for p in ("0007.png", "0008.png", "0009.png", "0367.png", "0368.png", "0369.png"):
            self.assertTrue((demo_dir / "01_nguon_demo/HVTT" / p).is_file())

        for bk, code in (("HVTT", "HVTT_HanVanTinhTuy"), ("TVLT2", "TVLT2_ThoVanLyTran2"), ("TLTVN", "TLTVN_TheLoaiTuVN")):
            align_dir = ROOT_DIR / "deliverables" / code / "04_dong_hang"
            self.assertTrue((align_dir / f"{code}_parallel.tsv").is_file())
            self.assertTrue((align_dir / f"{code}_parallel.xlsx").is_file())
            self.assertFalse((align_dir / f"{bk}_parallel.tsv").exists())
            self.assertFalse((align_dir / f"{bk}_parallel.xlsx").exists())

    def test_smoke_demo_1_2_pages_subprocess_in_temp_copy(self) -> None:
        """Smoke-test scripts/demo_1_2_pages.py CLI in an isolated workspace copy."""
        with tempfile.TemporaryDirectory() as td:
            tmp_ws = Path(td)
            shutil.copytree(ROOT_DIR / "src", tmp_ws / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            (tmp_ws / "scripts").mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT_DIR / "scripts" / "demo_1_2_pages.py", tmp_ws / "scripts" / "demo_1_2_pages.py")

            demo_png_map = {
                "HVTT_HanVanTinhTuy": ("0007.png", "0008.png", "0009.png", "0010.png", "0367.png", "0368.png", "0369.png"),
                "TVLT2_ThoVanLyTran2": ("0019.png", "0020.png", "0022.png", "0024.png", "0026.png"),
                "TLTVN_TheLoaiTuVN": ("0134.png", "0135.png", "0136.png", "0137.png", "0138.png"),
            }
            for code, png_names in demo_png_map.items():
                src_align = ROOT_DIR / "deliverables" / code / "04_dong_hang"
                dst_align = tmp_ws / "deliverables" / code / "04_dong_hang"
                dst_align.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_align / f"{code}_parallel.tsv", dst_align / f"{code}_parallel.tsv")

                dst_src = tmp_ws / "deliverables" / code / "01_nguon"
                dst_src.mkdir(parents=True, exist_ok=True)
                for png_name in png_names:
                    src_png = ROOT_DIR / "deliverables" / code / "01_nguon" / png_name
                    if src_png.is_file():
                        try:
                            os.link(src_png, dst_src / png_name)
                        except OSError:
                            shutil.copy2(src_png, dst_src / png_name)

            proc = subprocess.run(
                [sys.executable, str(tmp_ws / "scripts" / "demo_1_2_pages.py"), "--book", "ALL"],
                cwd=str(tmp_ws),
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)

            out_demo = tmp_ws / "demo_giang_vien"
            report_md = out_demo / "BAO_CAO_DEMO_GIANG_VIEN.md"
            self.assertTrue(report_md.is_file())
            report_txt = report_md.read_text(encoding="utf-8")
            self.assertEqual(unicodedata.normalize("NFC", report_txt), report_txt)

            expected_header = ("Hán", "Dịch âm", "Dịch nghĩa", "Dịch thơ")
            for name in ("HVTT_demo", "TVLT2_demo", "TLTVN_demo"):
                tsv_rows = read_tsv(out_demo / f"{name}.tsv")
                xlsx_dong_hang = read_xlsx_zero_dep(
                    str(out_demo / f"{name}.xlsx"), sheet_name="DONG_HANG", include_header=True
                )
                xlsx_thong_ke = read_xlsx_zero_dep(
                    str(out_demo / f"{name}.xlsx"), sheet_name="THONG_KE", include_header=True
                )
                self.assertEqual(xlsx_dong_hang[0], expected_header)
                self.assertEqual(tsv_rows, xlsx_dong_hang[1:])
                self.assertEqual(xlsx_thong_ke[0], ("Chỉ số", "Giá trị"))
                self.assertTrue(all(len(r) == 4 for r in tsv_rows))
                qa = validate_pairs(tsv_rows)
                self.assertEqual(qa["error_pairs"], 0)
                self.assertEqual(qa["error_rate"], 0.0)

            hvtt_rows = read_tsv(out_demo / "HVTT_demo.tsv")
            self.assertEqual(hvtt_rows[0][0], "子產授政太叔")
            self.assertTrue(any(r[3].strip() for r in hvtt_rows[1:9]))
            self.assertTrue(any(r[0] == "秋夜旅懷吟" and r[3] == "" for r in hvtt_rows))
            self.assertTrue(any(r[0].startswith("仙家") and r[2] == "" and r[3].strip() for r in hvtt_rows))

            tvlt2_rows = read_tsv(out_demo / "TVLT2_demo.tsv")
            self.assertTrue(any(r[0] == "寄清風庵僧德山" and r[3] == "" for r in tvlt2_rows))
            self.assertTrue(any(r[0] == "禪宗指南序" and r[3] == "" for r in tvlt2_rows))
            self.assertTrue(any("朕竊謂佛無南北" in r[0] and r[2].strip() and r[3] == "" for r in tvlt2_rows))

            tltvn_rows = read_tsv(out_demo / "TLTVN_demo.tsv")
            self.assertEqual(tltvn_rows[0], ("阮郎歸", "Nguyễn lang quy", "Điệu Nguyễn lang quy", ""))
            self.assertTrue(all(r[3].strip() for r in tltvn_rows[1:]))


if __name__ == "__main__":
    unittest.main()
