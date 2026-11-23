# Xây dựng Ngữ liệu Song hành Hán - Việt (CV04_VPO_02 - VPO_02)

**Học phần:** Xử lý Ngôn ngữ Tự nhiên (NLP)  
**Mã nhóm:** `CV04` (Trần Trung Hiếu, Lê Gia Khánh, Phạm Chấn Khoa, Cái Hoàng Bảo Kin)  
**Mã tác phẩm:** `VPO_02` (`CV04_VPO_02`)  
**Tác phẩm:** *Thể loại từ Việt Nam thời trung đại* — Phạm Văn Ánh / Nguyễn Xuân Diện – Nguyễn Quảng Tuân  
**Phạm vi dữ liệu trên nhánh `kin`:** `103` trang phân công của Kin ở Phần Ba (`PDF 445..547`) + `7` trang pilot (`PDF 134..138, 200, 300`) = `110` trang OCR GPU.

---

### 1. Phương pháp và Công cụ thực hiện (Tools & Methods)

* **Trích xuất nguồn dữ liệu (`01_nguon/`):**
  * Do lớp text PDF có sẵn bị lỗi mất chữ Hán và văn bản Hán – Việt in tuần tự trong cùng cuốn sách, toàn bộ ảnh trang sách Phần Ba được trích xuất ở chuẩn **300 DPI** bằng `PyMuPDF (fitz)` (`src/pdf_extractor.py`) và lưu tại `01_nguon/<so_trang>.png` (các ảnh bulk được `.gitignore` loại trừ khỏi Git; chỉ track ảnh pilot trên Git).
* **Nhận dạng ký tự quang học (`02_ocr_tho/`):**
  * Chữ Hán phồn thể: **PaddleOCR (`chinese_cht`)** kết hợp hiệu chỉnh nhập nhằng thị giác qua neo ngữ âm Hán–Việt (`src/ocr_disambiguator.py`).
  * Chữ Quốc ngữ (Phiên âm, Dịch nghĩa, Dịch theo nguyên điệu): **VietOCR (`vgg_transformer`)** có cắt bỏ 7% running header trên cùng và phát hiện đường kẻ ngang để loại bỏ khối chú thích chân trang.
  * Kết quả OCR thô từng trang lưu tại `02_ocr_tho/han/*.json`, `02_ocr_tho/viet/*.json`, kèm `ocr_results.jsonl` và `ocr_run_summary.json`.
* **Làm sạch và Chuẩn hóa văn bản (`03_text_sach/`):**
  * Chuẩn hóa bảng mã Unicode **UTF-8 NFC**, lọc bỏ header/footer, số trang và ký hiệu chú thích (`[1]`, `1*`, `(1)`), bảo toàn ký hiệu `[MASK]` / `□` (`src/text_cleaner.py`).
  * Toàn bộ các bài từ được gộp chung trong `han.txt` và `viet.txt`, xuất đồng bộ từng dòng với `04_dong_hang/VPO_02_parallel.tsv` (mỗi bài và tiểu phẩm liên hoàn từ bắt đầu bằng dòng tiêu đề riêng).
* **Dóng hàng song ngữ 4 cột (`04_dong_hang/`):**
  * Phân đoạn tác phẩm xuyên trang bằng `src/work_segmenter.py`, gán `Phiên âm` $\rightarrow$ `Dịch âm`, `Dịch nghĩa` $\rightarrow$ `Dịch nghĩa`, và *Dịch theo nguyên điệu* $\rightarrow$ `Dịch thơ` bằng thuật toán Quy hoạch động Gale-Church + neo từ vựng (`src/aligner.py`, `src/corpus_pipeline.py`).
  * Xuất đồng bộ 2 định dạng chuẩn: `VPO_02_parallel.tsv` (UTF-8, không header) và `VPO_02_parallel.xlsx` (2 sheet `DONG_HANG` & `THONG_KE`), kèm `qa_report.json` và `word_coverage_report.json`.

---

### 2. Thống kê Chất lượng Kiểm định (QA Report — Nhánh `kin`)

* **Tổng số dòng dóng hàng (4 cột `Hán - Dịch âm - Dịch nghĩa - Dịch thơ`):** `499` *(gồm `36` dòng tiêu đề, `297` dòng có `Dịch thơ`)*
* **Số cặp hợp lệ:** `499`
* **Số cặp cảnh báo QA:** `17` (`OMISSION: 11`, `ADDITION: 6`; `MISSING = 0`, `FORMAT_ERROR = 0`, `LEFTOVER_MARKER = 0`)
* **Tỷ lệ lỗi QA:** `3.41%` (Đạt chuẩn nghiệm thu $\le 30\%$ và mục tiêu nội bộ $\le 20\%$)
* **Độ bao phủ Hán tự trung bình:** `55.35%`
* **Điểm tin cậy dóng hàng trung bình:** `0.55 / 1.00` (`0.5495`)
* **Khớp 100% `VPO_02_parallel.tsv` == `VPO_02_parallel.xlsx` (`DONG_HANG`):** Đạt

---

### 3. Cấu trúc thư mục bàn giao

```text
CV04_VPO_02/
├── 01_nguon/           # Ảnh scan trang sách gốc 300 DPI (.png)
├── 02_ocr_tho/         # Kết quả OCR thô ban đầu (han/, viet/, ocr_results.jsonl, ocr_run_summary.json)
├── 03_text_sach/       # Văn bản đã làm sạch (han.txt, viet.txt)
├── 04_dong_hang/       # VPO_02_parallel.tsv, VPO_02_parallel.xlsx, qa_report.json, word_coverage_report.json
└── README.md           # Tài liệu thuyết minh phương pháp & kết quả
```
