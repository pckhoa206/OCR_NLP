#!/usr/bin/env python3
"""Package Parallel Hán–Việt Deliverables into Hugging Face Dataset Format.

Generates standard Hugging Face Dataset repository structure:
- `dataset_export/train.jsonl`
- `dataset_export/validation.jsonl`
- `dataset_export/test.jsonl`
- `dataset_export/dataset_info.json`
- `dataset_export/README.md` (Dataset Card with YAML frontmatter)
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.exporter_and_qa import read_tsv

BOOKS = [
    {
        "id": "HVTT",
        "title": "Hán Văn Tinh Túy",
        "author": "Lãng Nhân Phùng Tất Đắc",
        "tsv": ROOT_DIR / "deliverables" / "HVTT_HanVanTinhTuy" / "04_dong_hang" / "HVTT_HanVanTinhTuy_parallel.tsv",
        "genre": "classical_prose_and_verse",
        "period": "cổ đại – cận đại",
    },
    {
        "id": "TVLT2",
        "title": "Thơ văn Lý – Trần (Tập II)",
        "author": "Nguyễn Huệ Chi (chủ biên)",
        "tsv": ROOT_DIR / "deliverables" / "TVLT2_ThoVanLyTran2" / "04_dong_hang" / "TVLT2_ThoVanLyTran2_parallel.tsv",
        "genre": "buddhist_philosophy_and_poetry",
        "period": "thế kỷ XI – XIV (Lý - Trần)",
    },
    {
        "id": "TLTVN",
        "title": "Thể loại từ VN thời trung đại",
        "author": "Nguyễn Xuân Diện – Nguyễn Quảng Tuân",
        "tsv": ROOT_DIR / "deliverables" / "TLTVN_TheLoaiTuVN" / "04_dong_hang" / "TLTVN_TheLoaiTuVN_parallel.tsv",
        "genre": "lyric_poetry_ci",
        "period": "thế kỷ X – XIX (Trung đại)",
    },
]


def load_all_records() -> List[Dict[str, Any]]:
    """Gather all aligned pairs from the 3 deliverables into unified dictionary records."""
    records: List[Dict[str, Any]] = []
    global_idx = 1

    for b in BOOKS:
        tsv_path = b["tsv"]
        if not tsv_path.is_file():
            # Fallback to short name
            tsv_path = tsv_path.parent / f"{b['id']}_parallel.tsv"

        if not tsv_path.is_file():
            print(f"[!] Warning: TSV for {b['id']} not found at {tsv_path}")
            continue

        rows = read_tsv(str(tsv_path))
        for row in rows:
            rec: Dict[str, Any] = {
                "id": f"{b['id']}_{global_idx:05d}",
                "source_book": b["id"],
                "book_title": b["title"],
                "author": b["author"],
                "genre": b["genre"],
                "period": b["period"],
                "classical_chinese": row[0],
            }
            if len(row) >= 4:
                rec["sino_vietnamese_reading"] = row[1]
                rec["vietnamese_prose_translation"] = row[2]
                rec["vietnamese_verse_translation"] = row[3]
                # Canonical target text (prose translation if present, otherwise verse translation)
                rec["vietnamese_translation"] = row[2] if row[2].strip() else row[3]
            else:
                rec["sino_vietnamese_reading"] = ""
                rec["vietnamese_prose_translation"] = row[1] if len(row) > 1 else ""
                rec["vietnamese_verse_translation"] = ""
                rec["vietnamese_translation"] = row[1] if len(row) > 1 else ""

            records.append(rec)
            global_idx += 1

    return records


def split_dataset(
    records: List[Dict[str, Any]],
    train_ratio: float = 0.80,
    val_ratio: float = 0.10,
    seed: int = 42,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split records into train, validation, and test splits deterministically."""
    rng = random.Random(seed)
    shuffled = list(records)
    rng.shuffle(shuffled)

    n = len(shuffled)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)

    train_set = shuffled[:n_train]
    val_set = shuffled[n_train : n_train + n_val]
    test_set = shuffled[n_train + n_val :]

    # Edge-case fallback for tiny sets
    if not val_set and len(train_set) > 2:
        val_set = [train_set.pop()]
    if not test_set and len(train_set) > 2:
        test_set = [train_set.pop()]

    return train_set, val_set, test_set


def build_readme_card(total_records: int, train_cnt: int, val_cnt: int, test_cnt: int) -> str:
    """Generate Hugging Face Dataset Card with YAML frontmatter."""
    return f"""---
language:
- lzh
- vi
license: cc-by-nc-sa-4.0
size_categories:
- 1K<n<10K
task_categories:
- translation
- text-generation
pretty_name: Sino-Vietnamese Classical Parallel Corpus (Ngữ liệu Song ngữ Hán – Việt)
tags:
- classical-chinese
- literary-chinese
- sino-vietnamese
- parallel-corpus
- digital-humanities
- vietnam-literature
---

# Sino-Vietnamese Classical Parallel Corpus (1400–1900)

## Giới thiệu (Dataset Summary)
Bộ ngữ liệu song ngữ **Hán văn cổ (Classical / Literary Chinese - `lzh`) $\\leftrightarrow$ Tiếng Việt (`vi`)** chuẩn xác cao, được số hóa và dóng hàng câu theo quy chuẩn học thuật nghiêm ngặt từ 3 bộ cổ thư tiêu biểu:
1. **Hán Văn Tinh Túy** (*Lãng Nhân Phùng Tất Đắc*, Nam Chi Tùng Thư).
2. **Thơ văn Lý – Trần (Tập II)** (*GS. Nguyễn Huệ Chi chủ biên*, NXB Khoa học Xã hội).
3. **Thể loại từ Việt Nam thời trung đại** (*TS. Nguyễn Xuân Diện – Nguyễn Quảng Tuân*, NXB Khoa học Xã hội).

Mỗi mẫu dữ liệu hỗ trợ **4 tầng ngữ liệu đối chiếu**:
- `classical_chinese`: Nguyên văn chữ Hán phồn thể (chuẩn Unicode NFC).
- `sino_vietnamese_reading`: Phiên âm Hán-Việt từng âm tiết.
- `vietnamese_prose_translation`: Bản dịch nghĩa xuôi tiếng Việt.
- `vietnamese_verse_translation`: Bản dịch thơ (Lục bát / Song thất lục bát / Thơ Đường).

## Cấu trúc Phân chia (Splits)
- **Tổng số mẫu**: {total_records}
- **Tập Train**: {train_cnt} mẫu
- **Tập Validation**: {val_cnt} mẫu
- **Tập Test**: {test_cnt} mẫu

## Lược đồ Dữ liệu (Schema)
```json
{{
  "id": "HVTT_00001",
  "source_book": "HVTT",
  "book_title": "Hán Văn Tinh Túy",
  "author": "Lãng Nhân Phùng Tất Đắc",
  "genre": "classical_prose_and_verse",
  "period": "cổ đại – cận đại",
  "classical_chinese": "鄭子產有疾，謂子太叔曰：",
  "sino_vietnamese_reading": "Trịnh Tử-Sản hữu tật, vị tử Thái-Thúc viết:",
  "vietnamese_prose_translation": "Trịnh Tử-Sản bệnh nặng, bảo con là Thái-Thúc rằng:",
  "vietnamese_verse_translation": "",
  "vietnamese_translation": "Trịnh Tử-Sản bệnh nặng, bảo con là Thái-Thúc rằng:"
}}
```

## Bản quyền & Trích dẫn
Dữ liệu được số hóa phục vụ nghiên cứu học thuật, giáo dục và bảo tồn di sản văn hóa phi vật thể Hán–Nôm.
"""


def package_dataset(output_dir: Path = ROOT_DIR / "dataset_export") -> Dict[str, Any]:
    """Export dataset splits, info json, and README card."""
    output_dir.mkdir(parents=True, exist_ok=True)
    records = load_all_records()
    if not records:
        raise ValueError("No records loaded from deliverables.")

    train_set, val_set, test_set = split_dataset(records)

    # Write JSONL splits
    for name, split_data in (
        ("train.jsonl", train_set),
        ("validation.jsonl", val_set),
        ("test.jsonl", test_set),
    ):
        file_path = output_dir / name
        with file_path.open("w", encoding="utf-8") as f:
            for item in split_data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    # Write dataset_info.json
    info_data: Dict[str, Any] = {
        "dataset_name": "sino-vietnamese-parallel-corpus",
        "version": "1.0.0",
        "total_records": len(records),
        "splits": {
            "train": len(train_set),
            "validation": len(val_set),
            "test": len(test_set),
        },
        "features": [
            "id",
            "source_book",
            "book_title",
            "author",
            "genre",
            "period",
            "classical_chinese",
            "sino_vietnamese_reading",
            "vietnamese_prose_translation",
            "vietnamese_verse_translation",
            "vietnamese_translation",
        ],
    }
    (output_dir / "dataset_info.json").write_text(
        json.dumps(info_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # Write README.md Data Card
    readme_text = build_readme_card(
        len(records), len(train_set), len(val_set), len(test_set)
    )
    (output_dir / "README.md").write_text(readme_text, encoding="utf-8")

    return {
        "output_dir": str(output_dir),
        "total_records": len(records),
        "train": len(train_set),
        "validation": len(val_set),
        "test": len(test_set),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Package aligned deliverables into Hugging Face Dataset format."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(ROOT_DIR / "dataset_export"),
        help="Target output directory for Hugging Face dataset export.",
    )
    args = parser.parse_args(argv)
    res = package_dataset(Path(args.output_dir))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
