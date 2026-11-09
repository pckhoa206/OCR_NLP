"""Tests for CAT Workbench Editor Engine (`src/workbench_editor.py`)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.exporter_and_qa import read_tsv, read_xlsx_zero_dep
from src.workbench_editor import (
    delete_row,
    edit_row,
    insert_row,
    load_corpus,
    merge_rows,
    save_and_reexport_corpus,
    split_row,
)


class TestWorkbenchEditor(unittest.TestCase):
    """Verify interactive row editing, splitting, merging, and round-trip re-export."""

    def test_load_corpus_real_books(self) -> None:
        """Verify load_corpus successfully reads valid TSV files for all 3 books."""
        for book in ["HVTT", "TVLT2", "TLTVN"]:
            rows = load_corpus(book, ROOT_DIR)
            self.assertGreater(len(rows), 0)
            self.assertIsInstance(rows[0], tuple)

    def test_edit_row_and_text_sanitization(self) -> None:
        """Verify edit_row modifies content while sanitizing and cleaning NFC text."""
        initial_rows = [
            ("風打松關", "Gió đập cổng thông"),
            ("月照庭", "Trăng sáng trước sân"),
        ]
        updated = edit_row(initial_rows, 0, ("風打松關\u200b", "Gió đập cổng thông  "))
        self.assertEqual(len(updated), 2)
        # Zero-width space should be stripped by clean_han_text
        self.assertNotIn("\u200b", updated[0][0])
        self.assertEqual(updated[0][1], "Gió đập cổng thông")

        with self.assertRaises(IndexError):
            edit_row(initial_rows, 5, ("test", "test"))

    def test_split_row_atomic_boundary(self) -> None:
        """Verify split_row divides 1 pair into 2 distinct aligned pairs."""
        initial_rows = [
            ("風打松關月照庭", "Gió đập cổng thông, trăng sáng trước sân"),
        ]
        # Split Han at char 4 ("風打松關" / "月照庭"), Viet at char 19 ("Gió đập cổng thông," / "trăng sáng trước sân")
        split_res = split_row(initial_rows, 0, han_split_pos=4, viet_split_pos=20)
        self.assertEqual(len(split_res), 2)
        self.assertEqual(split_res[0][0], "風打松關")
        self.assertEqual(split_res[1][0], "月照庭")
        self.assertIn("Gió đập cổng thông", split_res[0][1])
        self.assertIn("trăng sáng trước sân", split_res[1][1])

    def test_merge_rows_adjacent(self) -> None:
        """Verify merge_rows combines 2 adjacent rows with proper punctuation glue."""
        initial_rows = [
            ("風打松關", "Gió đập cổng thông"),
            ("月照庭", "trăng sáng trước sân"),
        ]
        merged = merge_rows(initial_rows, 0, 1)
        self.assertEqual(len(merged), 1)
        self.assertIn("風打松關", merged[0][0])
        self.assertIn("月照庭", merged[0][0])
        self.assertIn("Gió đập cổng thông", merged[0][1])
        self.assertIn("trăng sáng trước sân", merged[0][1])

        # Non-adjacent merge should raise ValueError
        three_rows = initial_rows + [("心期風景", "Lòng hẹn phong cảnh")]
        with self.assertRaises(ValueError):
            merge_rows(three_rows, 0, 2)

    def test_insert_and_delete_row(self) -> None:
        """Verify insertion and deletion maintain valid indexing and CJK cleaning."""
        rows = [("風", "Gió"), ("庭", "Sân")]
        with_inserted = insert_row(rows, 1, ("月", "Trăng"))
        self.assertEqual(len(with_inserted), 3)
        self.assertEqual(with_inserted[1][0], "月")
        self.assertEqual(with_inserted[1][1], "Trăng")

        deleted = delete_row(with_inserted, 1)
        self.assertEqual(deleted, rows)

    def test_save_and_reexport_roundtrip(self) -> None:
        """Verify atomic save_and_reexport writes matching TSV, XLSX, and QA report."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            sample_rows = [
                ("風打松關月照庭，心期風景共淒清。", "Gió đập cổng thông, trăng sáng trước sân, Lòng hẹn với phong cảnh cùng trong sạch lặng lẽ."),
                ("箇中滋味無人識，付與山僧樂到明。", "Bao nhiêu thú vị trong đó không ai hay, Mặc cho nhà sư trong núi vui đến sáng."),
            ]

            res = save_and_reexport_corpus("TVLT2", sample_rows, tmp_root)
            self.assertEqual(res["status"], "SUCCESS")
            self.assertTrue(res["is_valid"])
            self.assertEqual(res["error_rate"], 0.0)

            # Check that TSV and XLSX were created and have identical content
            tsv_path = Path(res["tsv_path"])
            xlsx_path = Path(res["xlsx_path"])
            self.assertTrue(tsv_path.is_file())
            self.assertTrue(xlsx_path.is_file())

            roundtrip_tsv = read_tsv(str(tsv_path))
            roundtrip_xlsx = read_xlsx_zero_dep(str(xlsx_path))
            self.assertEqual(roundtrip_tsv, roundtrip_xlsx)
            self.assertEqual(len(roundtrip_tsv), 2)


if __name__ == "__main__":
    unittest.main()
