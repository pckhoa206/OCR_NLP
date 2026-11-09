---
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
Bộ ngữ liệu song ngữ **Hán văn cổ (Classical / Literary Chinese - `lzh`) $\leftrightarrow$ Tiếng Việt (`vi`)** chuẩn xác cao, được số hóa và dóng hàng câu theo quy chuẩn học thuật nghiêm ngặt từ 3 bộ cổ thư tiêu biểu:
1. **Hán Văn Tinh Túy** (*Lãng Nhân Phùng Tất Đắc*, Nam Chi Tùng Thư).
2. **Thơ văn Lý – Trần (Tập II)** (*GS. Nguyễn Huệ Chi chủ biên*, NXB Khoa học Xã hội).
3. **Thể loại từ Việt Nam thời trung đại** (*TS. Nguyễn Xuân Diện – Nguyễn Quảng Tuân*, NXB Khoa học Xã hội).

Mỗi mẫu dữ liệu hỗ trợ **4 tầng ngữ liệu đối chiếu**:
- `classical_chinese`: Nguyên văn chữ Hán phồn thể (chuẩn Unicode NFC).
- `sino_vietnamese_reading`: Phiên âm Hán-Việt từng âm tiết.
- `vietnamese_prose_translation`: Bản dịch nghĩa xuôi tiếng Việt.
- `vietnamese_verse_translation`: Bản dịch thơ (Lục bát / Song thất lục bát / Thơ Đường).

## Cấu trúc Phân chia (Splits)
- **Tổng số mẫu**: 42
- **Tập Train**: 33 mẫu
- **Tập Validation**: 4 mẫu
- **Tập Test**: 5 mẫu

## Lược đồ Dữ liệu (Schema)
```json
{
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
}
```

## Bản quyền & Trích dẫn
Dữ liệu được số hóa phục vụ nghiên cứu học thuật, giáo dục và bảo tồn di sản văn hóa phi vật thể Hán–Nôm.
