#!/usr/bin/env python3
"""TDD tests for T21: section classification, deduplication, HVTT layout grouping, and TVLT2/TLTVN work segmentation."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kaggle_ocr.ocr_pipeline_kaggle import (  # noqa: E402
    build_mock_ocr_for_page,
    classify_section_header,
    deduplicate_overlapping_items,
    group_layout_blocks,
    is_stop_section_header,
)
from src.work_segmenter import (  # noqa: E402
    SubPoem,
    WorkRecord,
    segment_book_works,
)

DELIVERABLES_ROOT = REPO_ROOT / "outputs" / "khoa" / "deliverables"


def _load_book_pages(folder_name: str) -> List[Dict[str, Any]]:
    ocr_dir = DELIVERABLES_ROOT / folder_name / "02_ocr_tho"
    pages: List[Dict[str, Any]] = []
    for han_file in sorted((ocr_dir / "han").glob("*.json")):
        han_payload = json.loads(han_file.read_text(encoding="utf-8"))
        viet_file = ocr_dir / "viet" / han_file.name
        viet_payload = json.loads(viet_file.read_text(encoding="utf-8")) if viet_file.is_file() else {"items": []}
        pages.append(
            {
                "page_id": han_payload.get("page_id", han_file.stem),
                "page_num": int(han_payload.get("page_num", han_file.stem)),
                "han_items": han_payload.get("items", []),
                "viet_items": viet_payload.get("items", []),
                "preprocess": han_payload.get("preprocess", {}),
            }
        )
    return pages


def _item(text: str, x1: float, y1: float, x2: float, y2: float, conf: float = 0.98, **extra: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "text": text,
        "box_xyxy": [x1, y1, x2, y2],
        "bbox": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
        "confidence": conf,
    }
    out.update(extra)
    return out


class TestSectionHeaderAndDedup(unittest.TestCase):
    def test_dich_tho_separated_from_true_stop_headers(self) -> None:
        for txt in (
            "DỊCH THƠ :",
            "Dịch theo nguyên điệu:",
            "DIGH THO :",
            "DICH TRƠ :",
            "DICH THEO NGUYEN DIEU :",
        ):
            self.assertEqual(classify_section_header(txt), "dich_tho", msg=txt)
            self.assertFalse(is_stop_section_header(txt), msg=txt)

        for txt in (
            "KHẢO ĐÍNH :",
            "KHAO HINH",
            "KI AO DINH :",
            "VĂN BẢN KHẢO ĐÍNH",
            "CÁC DỊ BẢN: KHL1",
            "CHÚ THÍCH :",
            "CHÚ : THÍCH",
            "GHU THICH",
            "CÁC THÍCH",
            "LỜI BÀN",
            "BÌNH CHÚ",
        ):
            self.assertEqual(classify_section_header(txt), "stop", msg=txt)
            self.assertTrue(is_stop_section_header(txt), msg=txt)

        for txt in ("PHIÊN ÂM:", "PH1EN ANH:", "Phiên âm :"):
            self.assertEqual(classify_section_header(txt), "phien_am", msg=txt)
        for txt in ("DỊCH NGHĨA :", "D1CH NGITA:", "DỊCH XUÔI:"):
            self.assertEqual(classify_section_header(txt), "dich_nghia", msg=txt)

    def test_deduplicate_overlapping_items_keeps_distinct_columns(self) -> None:
        items = [
            _item("Cử :", 180, 200, 260, 240, conf=0.80),
            _item("Cử :", 183, 206, 262, 246, conf=0.96),
            _item("Hảo", 200, 300, 300, 340, conf=0.95),
            _item("Hảo", 900, 302, 1000, 342, conf=0.95),
        ]
        deduped = deduplicate_overlapping_items(items, y_threshold=12.0)
        self.assertEqual(len(deduped), 3)
        self.assertEqual(deduped[0]["confidence"], 0.96)


class TestHVTTLayoutGrouping(unittest.TestCase):
    def test_odd_title_page_and_mock_pages(self) -> None:
        for pnum in (7, 367):
            han_items, viet_items = build_mock_ocr_for_page(f"{pnum:04d}", "HVTT", pnum, {"effective_width": 1188})
            res = group_layout_blocks(han_items, viet_items, "HVTT", page_num=pnum, page_width=1188)
            self.assertEqual(res["layout_mode"], "odd_title_page")
            self.assertEqual(res["interlinear_triplets"], [])
            self.assertEqual(res["dich_tho_lines"], [])
            self.assertTrue(res["title_block"]["chu_han"])
            self.assertTrue(res["title_block"]["phien_am"])
            self.assertTrue(res["title_block"]["dich_nghia"])
            self.assertNotIn("TIỂU", res["title_block"]["dich_nghia"].upper())

        # Wrapped 2-line title_dich_nghia + right-aligned author skip + TIỂU-DÂN typo stop
        han_0029 = [
            _item("叔向賀宣子貧", 360, 140, 740, 210),
            _item("左 丘 明", 710, 420, 920, 465),
        ]
        viet_0029 = [
            _item("THÚC-HƯỚNG HẠ TUYÊN-TỬ BẦN", 300, 235, 810, 275),
            _item("THÚC-HƯỚNG CHÚC MỪNG", 320, 290, 790, 330),
            _item("TUYÊN-TỬ NGHÈO", 380, 340, 720, 380),
            _item("Tả Khâu Minh", 680, 480, 920, 520),
            _item("TIỂU-DÂN. — Thúc-Hướng tên là...", 140, 560, 990, 600),
        ]
        res_29 = group_layout_blocks(han_0029, viet_0029, "HVTT", page_num=29, page_width=1188)
        self.assertEqual(res_29["layout_mode"], "odd_title_page")
        self.assertEqual(
            res_29["title_block"],
            {
                "chu_han": "叔向賀宣子貧",
                "phien_am": "THÚC-HƯỚNG HẠ TUYÊN-TỬ BẦN",
                "dich_nghia": "THÚC-HƯỚNG CHÚC MỪNG TUYÊN-TỬ NGHÈO",
            },
        )

    def test_odd_facing_dich_tho_and_bio_prose_skip(self) -> None:
        # Shifted page running header + garbled page number 'ss' + Dịch thơ
        viet_facing = [
            _item("ss", 120, 130, 160, 165),
            _item("HÁN-VĂN TINH-TUÝ", 910, 132, 1100, 168),
            _item("Sương rơi cửa trúc lạnh lùng,", 240, 240, 760, 280),
            _item("Gió thu thổi mãi bên song.", 240, 300, 750, 340),
        ]
        res_dt = group_layout_blocks([], viet_facing, "HVTT", page_num=9, page_width=1188)
        self.assertEqual(res_dt["layout_mode"], "odd_page_dich_tho")
        self.assertEqual(len(res_dt["dich_tho_lines"]), 2)
        self.assertEqual(len(res_dt["dich_tho_y_centers"]), 2)

        # Full-width bio prose (>= 12 lines, median x1 < 0.20*w, max x2 > 0.80*w) -> skipped
        viet_bio = [
            _item("67", 110, 35, 160, 70),
            _item("HÁN-VĂN TINH-TUÝ", 920, 36, 1110, 72),
        ] + [
            _item(f"Dòng tiểu sử tác giả số {i} rất dài.", 170, 120 + i * 50, 990, 160 + i * 50)
            for i in range(13)
        ]
        res_bio = group_layout_blocks([], viet_bio, "HVTT", page_num=73, page_width=1188)
        self.assertEqual(res_bio["layout_mode"], "odd_page_bio_prose_skipped")
        self.assertEqual(res_bio["dich_tho_lines"], [])

    def test_even_wrapped_phien_am_merge_and_no_dich_nghia_detection(self) -> None:
        han_items = [
            _item("夫 火 烈 民 望 而 畏 之 故 鮮 死 焉", 180, 200, 980, 240),
            _item("水 懦 弱 民 狎 而 翫 之 則 多 死 焉", 180, 400, 980, 440),
        ]
        viet_items = [
            _item("4", 110, 100, 145, 130),
            _item("HÁN-VĂN TINH-TUÝ", 665, 102, 1020, 132),
            # Band 0: wrapped Phiên âm (x2 >= 0.80*1188=950.4, L1 x1 <= L0.x1-18 and L1 x1 <= L2.x1-18)
            _item("Phù hỏa liệt, dân vọng nhi úy chi, cố tiển", 220, 255, 985, 290),
            _item("tử yên.", 170, 295, 310, 330),
            _item("Như lửa cháy, dân trông thấy là sợ, nên ít kẻ chết.", 215, 340, 920, 375),
            # Band 1: normal 2-line triplet
            _item("Thủy nhu nhược, dân hạp nhi ngoạn chi, tắc đa tử yên.", 215, 455, 930, 490),
            _item("Nước mềm yếu, dân nhờn mà đùa cợt, nên chết nhiều.", 215, 505, 920, 540),
        ]
        res = group_layout_blocks(han_items, viet_items, "HVTT", page_num=8, page_width=1188)
        self.assertEqual(res["layout_mode"], "interlinear_3line_even_page")
        self.assertTrue(res["has_dich_nghia"])
        self.assertEqual(
            res["interlinear_triplets"][0]["phien_am"],
            "Phù hỏa liệt, dân vọng nhi úy chi, cố tiển tử yên.",
        )
        self.assertEqual(
            res["interlinear_triplets"][0]["dich_nghia_gloss"],
            "Như lửa cháy, dân trông thấy là sợ, nên ít kẻ chết.",
        )

        # Page 100 (Thạch Hào lại): only 1 Viet line per band -> has_dich_nghia=False
        viet_p100 = [
            _item("Phù hỏa liệt, dân vọng nhi úy chi, cố tiển tử yên.", 215, 255, 910, 290),
            _item("Thủy nhu nhược, dân hạp nhi ngoạn chi, tắc đa tử yên.", 215, 455, 920, 490),
        ]
        res_100 = group_layout_blocks(han_items, viet_p100, "HVTT", page_num=100, page_width=1188)
        self.assertFalse(res_100["has_dich_nghia"])
        self.assertEqual(res_100["dich_nghia_lines"], [])
        self.assertEqual(res_100["interlinear_triplets"][0]["dich_nghia_gloss"], "")

    def test_even_non_han_skipped(self) -> None:
        res = group_layout_blocks([], [_item("66", 110, 40, 150, 75)], "HVTT", page_num=72, page_width=1188)
        self.assertEqual(res["layout_mode"], "even_page_non_han_skipped")
        self.assertFalse(res["has_dich_nghia"])

    @unittest.skipUnless((DELIVERABLES_ROOT / "HVTT_HanVanTinhTuy" / "02_ocr_tho").is_dir(), "HVTT real OCR not present")
    def test_real_hvtt_95_pages(self) -> None:
        pages = _load_book_pages("HVTT_HanVanTinhTuy")
        self.assertEqual(len(pages), 95)
        title_pages = []
        bio_odd = []
        skipped_even = []
        p100_layout = None
        p08_layout = None
        p54_layout = None
        for p in pages:
            pw = int((p.get("preprocess") or {}).get("effective_width") or 1188)
            lay = group_layout_blocks(p["han_items"], p["viet_items"], "HVTT", page_num=p["page_num"], page_width=pw)
            if lay["layout_mode"] == "odd_title_page":
                title_pages.append(p["page_num"])
            elif lay["layout_mode"] == "odd_page_bio_prose_skipped":
                bio_odd.append(p["page_num"])
            elif lay["layout_mode"] == "even_page_non_han_skipped":
                skipped_even.append(p["page_num"])
            if p["page_num"] == 100:
                p100_layout = lay
            elif p["page_num"] == 8:
                p08_layout = lay
            elif p["page_num"] == 54:
                p54_layout = lay

        self.assertEqual(title_pages, [7, 17, 29, 41, 53, 65, 71, 85, 89, 97])
        self.assertEqual(bio_odd, [73, 99])
        self.assertEqual(len(skipped_even), 11)
        self.assertIsNotNone(p100_layout)
        self.assertFalse(p100_layout["has_dich_nghia"])
        self.assertIn("tử yên", p08_layout["interlinear_triplets"][4]["phien_am"])
        self.assertIn("hậu", p54_layout["interlinear_triplets"][4]["phien_am"])


class TestSinglePageDichThoExtraction(unittest.TestCase):
    def test_tvlt2_and_tltvn_group_layout_blocks_extract_dich_tho(self) -> None:
        han, viet = build_mock_ocr_for_page("0020", "TVLT2", 20)
        res = group_layout_blocks(han, viet, "TVLT2", page_num=20, page_width=2000)
        self.assertEqual(res["layout_mode"], "two_column_poetry")
        self.assertEqual(len(res["chu_han_lines"]), 4)
        self.assertEqual(len(res["phien_am_lines"]), 4)
        self.assertEqual(len(res["dich_nghia_lines"]), 4)
        self.assertEqual(len(res["dich_tho_lines"]), 1)

        han_tl, viet_tl = build_mock_ocr_for_page("0135", "TLTVN", 135)
        res_tl = group_layout_blocks(han_tl, viet_tl, "TLTVN", page_num=135, page_width=2000)
        self.assertEqual(len(res_tl["dich_tho_lines"]), 1)


class TestWorkSegmenterTVLT2(unittest.TestCase):
    def test_synthetic_small_pages_segment_cleanly(self) -> None:
        pages = [
            {
                "page_num": 17,
                "han_items": [
                    _item("風打松關月照庭", 100, 100, 450, 140),
                    _item("箇中滋味無人識", 100, 160, 450, 200),
                ],
                "viet_items": [
                    _item("Phong đả tùng quan nguyệt chiếu đình", 600, 100, 950, 140),
                    _item("Cá trung tư vị vô nhân thức", 600, 160, 950, 200),
                ],
            },
            {
                "page_num": 18,
                "han_items": [],
                "viet_items": [
                    _item("DỊCH NGHĨA :", 100, 80, 300, 120),
                    _item("Gió đập cổng thông, trăng sáng trước sân.", 100, 140, 800, 180),
                    _item("Thú vị trong đó không ai biết.", 100, 200, 800, 240),
                ],
            },
        ]
        works = segment_book_works("TVLT2", pages, workspace_root=REPO_ROOT)
        self.assertEqual(len(works), 1)
        self.assertEqual(works[0].han_lines, ["風打松關月照庭", "箇中滋味無人識"])
        self.assertEqual(len(works[0].dn_lines), 2)

    def test_synthetic_chu_thich_guard_and_midpage_work_transition(self) -> None:
        pages = [
            {
                "page_num": 19,
                "preprocess": {"effective_width": 1590, "effective_height": 2056},
                "han_items": [
                    _item("寄清風庵僧德山", 188, 157, 715, 238),
                    _item("風打松關月照庭", 198, 234, 722, 300),
                    _item("安南雖小文章在", 518, 820, 1036, 870),  # CHÚ THÍCH quote (h=50 < 58, not work start)
                    _item("送北使張顯鄉", 197, 1437, 652, 1516),
                    _item("顧無瓊報自懷慚", 189, 1530, 726, 1601),
                ],
                "viet_items": [
                    _item("19", 180, 0, 220, 25),
                    _item("THƠ VĂN LÝ TRẦN", 610, 0, 980, 28),
                    _item("KÝ THANH PHONG AM TĂNG ĐỨC SƠN", 767, 173, 1407, 217),
                    _item("Phong đả tùng quan nguyệt chiếu đình", 764, 243, 1399, 292),
                    _item("DỊCH NGHĨA :", 180, 480, 360, 515),
                    _item("Gió đập cổng thông trăng chiếu sân.", 400, 540, 1100, 580),
                    _item("NGUYỄN ĐỒNG CHÍ", 724, 610, 1097, 650),
                    _item("CHÚ THÍCH", 171, 720, 360, 760),
                    _item("An-nam tuy tiểu văn chương tại", 571, 880, 1014, 915),
                    _item("2", 768, 1359, 811, 1411),
                    _item("TIỄN BẮC SỨ", 960, 1441, 1196, 1490),
                    _item("TRƯƠNG HIỀN KHANH", 891, 1492, 1264, 1532),
                    _item("Cố vô quỳnh báo tự hoài tàm", 790, 1559, 1297, 1604),
                    _item("kham", 1120, 1610, 1210, 1645),
                ],
            }
        ]
        works = segment_book_works("TVLT2", pages, workspace_root=REPO_ROOT)
        self.assertEqual(len(works), 2)
        self.assertEqual(works[0].work_id, 1)
        self.assertNotIn("安南雖小文章在", works[0].han_lines)
        self.assertEqual(works[1].work_id, 2)
        self.assertEqual(works[1].pa_title, "TIỄN BẮC SỨ TRƯƠNG HIỀN KHANH")
        self.assertEqual(works[1].pa_lines, ["Cố vô quỳnh báo tự hoài tàm kham"])

    @unittest.skipUnless((DELIVERABLES_ROOT / "TVLT2_ThoVanLyTran2" / "02_ocr_tho").is_dir(), "TVLT2 real OCR not present")
    def test_real_tvlt2_199_pages_58_works(self) -> None:
        pages = _load_book_pages("TVLT2_ThoVanLyTran2")
        self.assertEqual(len(pages), 199)
        works = segment_book_works("TVLT2", pages, workspace_root=REPO_ROOT)
        self.assertEqual(len(works), 58)
        self.assertEqual([w.work_id for w in works], list(range(1, 59)))

        # Work #2 wrapped PA title & CHÚ THÍCH quote not leaked
        w2 = works[1]
        self.assertIn("TỔNG BẮC SỬ", w2.pa_title)
        self.assertEqual(len(w2.pa_lines), 8)
        self.assertFalse(any("安南雖小文章在" in ln for ln in w2.han_lines))

        # Work #3 supplement: exact 15 Dịch nghĩa paragraphs + partial p0024 Phiên âm preserved
        w3 = works[2]
        self.assertEqual(w3.dn_title, "TỰA THIỀN TÔNG CHỈ NAM")
        self.assertEqual(len(w3.dn_lines), 15)
        self.assertGreater(len(w3.pa_lines), 80)

        # Work #5 Khóa hư lục mixed prose + Kệ: NÚI THỨ ... transitions DICH_THO -> DICH_NGHIA
        w5 = works[4]
        self.assertTrue(any("NÚI THỨ NHẤT" in ln for ln in w5.dn_lines))
        self.assertTrue(any("NÚI THỨ TƯ" in ln for ln in w5.dn_lines))
        self.assertGreater(len(w5.dt_lines), 20)

        # Work #21 Niêm tụng kệ sub-segmentation (~43 tiết)
        w21 = works[20]
        self.assertEqual(len(w21.sub_poems), 43)
        self.assertIsInstance(w21.sub_poems[0], SubPoem)
        self.assertGreater(len(w21.sub_poems[0].han_lines), 0)
        self.assertGreater(len(w21.sub_poems[0].pa_lines), 0)
        self.assertGreater(len(w21.sub_poems[0].dn_lines), 0)

        # Missing-number prose works (#6, #7, #34, #57) & #58 cross-page number 0214->0215
        self.assertIn("普說色身", works[5].han_title)
        self.assertIn("普勸發菩提心", works[6].han_title)
        self.assertIn("中日祝香", works[33].han_title)
        self.assertIn("啟白", works[56].han_title)
        self.assertIn("懺悔意根罪", works[57].han_title)


class TestWorkSegmenterTLTVN(unittest.TestCase):
    def test_synthetic_fn_sep_none_cutoff_and_cropped_y0_recovery(self) -> None:
        fn_pages = [
            {
                "page_num": 138,
                "preprocess": {"effective_width": 1122, "effective_height": 1520},
                "han_items": [
                    _item("春來春去幾時休", 140, 200, 420, 245),
                ],
                "viet_items": [
                    _item("Phiên âm:", 140, 300, 300, 340),
                    _item("Xuân lai xuân khứ kỷ thì hưu", 140, 355, 620, 395),
                    _item("1.00.000", 400, 500, 520, 530),
                ],
            },
            {
                "page_num": 139,
                "preprocess": {"effective_width": 1122, "effective_height": 1520},
                "han_items": [],
                "viet_items": [
                    _item("Dịch nghĩa:", 140, 80, 300, 120),
                    _item("Điệu Tây giang nguyệt", 140, 130, 480, 170),
                    _item("Xuân đến xuân đi bao giờ dứt?", 140, 185, 640, 225),
                    _item("Xét từ phổ, điệu Tây giang nguyệt gồm hai đoạn.", 144, 308, 1020, 342),
                    _item("39", 950, 1400, 990, 1435),
                ],
            },
        ]
        fn_works = segment_book_works("TLTVN", fn_pages)
        self.assertEqual(len(fn_works), 1)
        self.assertEqual(fn_works[0].pa_lines, ["Xuân lai xuân khứ kỷ thì hưu"])
        self.assertEqual(fn_works[0].dn_title, "Điệu Tây giang nguyệt")
        self.assertEqual(fn_works[0].dn_lines, ["Xuân đến xuân đi bao giờ dứt?"])
        self.assertFalse(any("Xét từ phổ" in ln for ln in fn_works[0].dn_lines))

        # Cropped y=0 Dịch nghĩa header recovery after PA (e.g. p0227) + p0237 guard
        cropped_pages = [
            {
                "page_num": 226,
                "preprocess": {"effective_width": 1122, "effective_height": 1520},
                "han_items": [_item("清平樂", 140, 200, 380, 245)],
                "viet_items": [
                    _item("Phiên âm:", 140, 300, 300, 340),
                    _item("Thanh bình lạc", 140, 355, 420, 395),
                    _item("Công thành danh toại qui lai.", 140, 410, 620, 450),
                ],
            },
            {
                "page_num": 227,
                "preprocess": {"effective_width": 1122, "effective_height": 1520},
                "han_items": [],
                "viet_items": [
                    _item("VIẾT VỀ NỖI NIỀM TRONG LÒNG", 160, 0, 720, 37),
                    _item("(Điệu Thanh bình lạc)", 161, 49, 499, 87),
                    _item("Công thành, danh thỏa,", 160, 105, 650, 145),
                ],
            },
        ]
        cropped_works = segment_book_works("TLTVN", cropped_pages)
        self.assertEqual(len(cropped_works), 1)
        self.assertEqual(cropped_works[0].dn_title, "VIẾT VỀ NỖI NIỀM TRONG LÒNG (Điệu Thanh bình lạc)")
        self.assertEqual(cropped_works[0].dn_lines, ["Công thành, danh thỏa,"])

        # p0237 clipped y=0 prose wrap must be skipped + multi-poem DICH_THO -> DICH_NGHIA transition
        suite_pages = [
            {
                "page_num": 200,
                "preprocess": {"effective_width": 1122, "effective_height": 1520},
                "han_items": [
                    _item("秋月照書軒", 140, 200, 420, 245),
                    _item("春風吹花落", 140, 260, 420, 305),
                ],
                "viet_items": [
                    _item("Phiên âm:", 140, 350, 300, 390),
                    _item("I.", 140, 400, 175, 440),
                    _item("Thu nguyệt chiếu thư hiên,", 140, 450, 520, 490),
                    _item("II.", 140, 500, 180, 540),
                    _item("Xuân phong xuy hoa lạc.", 140, 550, 520, 590),
                    _item("Dịch nghĩa:", 140, 620, 300, 660),
                    _item("I.", 140, 670, 175, 710),
                    _item("Trăng thu rọi hiên sách,", 140, 720, 520, 760),
                    _item("Dịch theo nguyên điệu:", 140, 790, 480, 830),
                    _item("Trăng thu rọi phòng văn,", 140, 840, 520, 880),
                ],
            },
            {
                "page_num": 201,
                "preprocess": {"effective_width": 1122, "effective_height": 1520},
                "han_items": [],
                "viet_items": [
                    _item("Vỗ gối ngủ sao yên,", 140, 80, 480, 120),
                    _item("II.", 140, 140, 180, 180),
                    _item("Điệu Vũ trung hoa", 140, 190, 460, 230),
                    _item("Gió xuân thổi hoa rơi.", 140, 240, 520, 280),
                    _item("Dịch theo nguyên điệu:", 140, 300, 480, 340),
                    _item("Gió xuân thổi cánh hoa.", 140, 350, 520, 390),
                ],
            },
        ]
        suite_works = segment_book_works("TLTVN", suite_pages)
        self.assertEqual(len(suite_works), 1)
        self.assertEqual([s.label for s in suite_works[0].sub_poems], ["I", "II"])
        self.assertEqual(suite_works[0].dn_lines, ["Trăng thu rọi hiên sách,", "Gió xuân thổi hoa rơi."])
        self.assertEqual(suite_works[0].dt_lines, ["Trăng thu rọi phòng văn,", "Vỗ gối ngủ sao yên,", "Gió xuân thổi cánh hoa."])

        # p0237 clipped y=0 prose wrap must be filtered cleanly without leaking into PA or DT
        p237_pages = [
            {
                "page_num": 236,
                "preprocess": {"effective_width": 1122, "effective_height": 1520},
                "han_items": [_item("觀瀾巢十詞", 140, 200, 420, 245)],
                "viet_items": [
                    _item("Phiên âm:", 140, 300, 300, 340),
                    _item("Quan lan sào thập từ", 140, 355, 480, 395),
                ],
            },
            {
                "page_num": 237,
                "preprocess": {"effective_width": 1122, "effective_height": 1520},
                "han_items": [],
                "viet_items": [
                    _item("NHƯ ÂU CÓ NNHÀNH VIỆT CỨU, TỪ NNAT AJCN AIỆN, PHỤC VÌ INẠP TỪ, NI", 87, 0, 1048, 19),
                    _item("dung thi trung vị tận chi ý, dĩ tả du du chi tình vân nhĩ.", 88, 28, 880, 62),
                    _item("Dịch nghĩa:", 145, 73, 330, 111),
                    _item("Chùm từ về mười cảnh Quan lan sào cùng lời dẫn", 176, 115, 959, 158),
                    _item("ĐẶNG TRẦN CÔN (THẾ KỈ XVIII)", 319, 300, 850, 345),
                ],
            },
        ]
        p237_works = segment_book_works("TLTVN", p237_pages)
        self.assertEqual(len(p237_works), 1)
        self.assertFalse(any("NNHÀNH" in ln for ln in p237_works[0].pa_lines + p237_works[0].dn_lines))
        self.assertIn("Chùm từ về mười cảnh Quan lan sào cùng lời dẫn", p237_works[0].dn_lines)

    @unittest.skipUnless((DELIVERABLES_ROOT / "TLTVN_TheLoaiTuVN" / "02_ocr_tho").is_dir(), "TLTVN real OCR not present")
    def test_real_tltvn_104_pages(self) -> None:
        pages = _load_book_pages("TLTVN_TheLoaiTuVN")
        self.assertEqual(len(pages), 104)
        works = segment_book_works("TLTVN", pages)
        self.assertEqual(len(works), 36)

        # p0139 footnote cleanly omitted from W02
        w2 = works[1]
        self.assertFalse(any("Xét từ phổ" in ln for ln in w2.dn_lines))

        # 7 cropped y=0 headers properly separate PA vs DN (no dn=0 collapse on W26, W30, W31, W33)
        for wid in (26, 30, 31, 33):
            w = works[wid - 1]
            self.assertGreater(len(w.dn_lines), 0, msg=f"TLTVN W{wid} dn_lines should not be empty")
            self.assertEqual(len(w.pa_lines), len(w.dn_lines), msg=f"TLTVN W{wid} PA/DN counts should match")

        # p0237 clipped y=0 prose wrap guarded cleanly (no garbled NHƯ ÂU CÓ NNHÀNH...)
        self.assertFalse(any("NNHÀNH" in ln for ln in works[-2].pa_lines + works[-1].pa_lines))

        # Multi-poem suites split cleanly in Roman numeral order I, II, III, IV
        w19 = works[18]
        self.assertEqual([s.label for s in w19.sub_poems], ["I", "II", "III", "IV"])
        w24 = works[23]
        self.assertEqual([s.label for s in w24.sub_poems], ["I", "II", "III"])


if __name__ == "__main__":
    unittest.main()
