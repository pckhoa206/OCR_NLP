# Xây dựng Ngữ liệu Song hành Hán - Việt (CV04_VPO_01 - VPO_01)

**Học phần:** Xử lý Ngôn ngữ Tự nhiên (NLP)  
**Mã nhóm:** `CV04` (Trần Trung Hiếu, Lê Gia Khánh, Phạm Chấn Khoa, Cái Hoàng Bảo Kin)  
**Mã tác phẩm:** `VPO_01` (`CV04_VPO_01`)  
**Tác phẩm:** *Hán Văn Tinh Túy* — Lãng Nhân (Phùng Tất Đắc)  
**Phạm vi dữ liệu trên nhánh `kin`:** `92` trang phân công của Kin (`PDF 290..381`, gồm bài cuối *Thu dạ hoài ngâm* `PDF 367..381`) + `8` trang pilot ngoài shard (`PDF 7..13, 50`) = `100` trang OCR GPU.

---

### 1. Phương pháp và Công cụ thực hiện (Tools & Methods)

* **Trích xuất nguồn dữ liệu (`01_nguon/`):**
  * Do bản Hán và bản dịch tiếng Việt in chung trong cùng một cuốn PDF (trang chẵn in `Hán + Phiên âm + Dịch nghĩa`, trang lẻ đối diện in `Dịch thơ` hoặc trang tiêu đề bài), ảnh trang sách được trích xuất ở chuẩn **300 DPI** bằng `PyMuPDF (fitz)` (`src/pdf_extractor.py`) và lưu chung tại `01_nguon/<so_trang>.png` (các ảnh bulk được `.gitignore` loại trừ khỏi Git; chỉ track ảnh pilot trên Git).
* **Nhận dạng ký tự quang học (`02_ocr_tho/`):**
  * Chữ Hán phồn thể: **PaddleOCR (`chinese_cht`)** kết hợp hiệu chỉnh nhập nhằng thị giác qua neo ngữ âm Hán–Việt (`src/ocr_disambiguator.py`).
  * Chữ Quốc ngữ (Phiên âm, Dịch nghĩa, Dịch thơ): **VietOCR (`vgg_transformer`)** (với PaddleOCR phát hiện vùng dòng văn bản).
  * Kết quả OCR thô từng trang lưu tại `02_ocr_tho/han/*.json`, `02_ocr_tho/viet/*.json`, kèm `ocr_results.jsonl` và `ocr_run_summary.json` *(lưu ý: `ocr_run_summary.json` ghi 69 trang `308..381` của lượt chạy sau, còn đủ `92/92` trang `0290..0381` đều có file JSON trong `han/` và `viet/`)*.
* **Làm sạch và Chuẩn hóa văn bản (`03_text_sach/`):**
  * Chuẩn hóa bảng mã Unicode **UTF-8 NFC**, lọc bỏ header/footer, số trang và ký hiệu chú thích (`[1]`, `1*`, `(1)`), bảo toàn token `[MASK]` / `□` (`src/text_cleaner.py`).
  * Phóng chiếu dấu câu từ bản Dịch âm sang chữ Hán (`src/phonetic_verifier.py`). Toàn bộ tác phẩm của cuốn sách lưu chung trong `han.txt` và `viet.txt`, xuất đồng bộ từng dòng với `04_dong_hang/VPO_01_parallel.tsv` (mở đầu mỗi bài bằng dòng tiêu đề riêng).
* **Dóng hàng song ngữ 4 cột (`04_dong_hang/`):**
  * Mỗi bài bắt đầu bằng **1 dòng tiêu đề riêng** (gồm chữ Hán, Dịch âm, Dịch nghĩa, Dịch thơ nếu có), theo sau là các câu nội dung chính.
  * Dóng hàng **Hán – Dịch âm – Dịch nghĩa – Dịch thơ** từ trang chẵn và trang lẻ đối diện (`src/aligner.py`, `src/corpus_pipeline.py`); riêng bài cuối *Thu dạ hoài ngâm* (`PDF 367..381`) và các bài không có dịch nghĩa để trống cột `Dịch nghĩa` (`""`).
  * Xuất đồng bộ 2 định dạng chuẩn: `VPO_01_parallel.tsv` (UTF-8, không header) và `VPO_01_parallel.xlsx` (2 sheet `DONG_HANG` & `THONG_KE`), kèm `qa_report.json` và `word_coverage_report.json`.

---

### 2. Thống kê Chất lượng Kiểm định (QA Report — Nhánh `kin`)

* **Tổng số dòng dóng hàng (4 cột `Hán - Dịch âm - Dịch nghĩa - Dịch thơ`):** `359` *(gồm `6` dòng tiêu đề, `280` dòng có `Dịch thơ`)*
* **Số cặp hợp lệ:** `359`
* **Số cặp cảnh báo QA:** `1` (`OMISSION: 1`; `MISSING = 0`, `FORMAT_ERROR = 0`, `LEFTOVER_MARKER = 0`)
* **Tỷ lệ lỗi QA:** `0.28%` (Đạt chuẩn nghiệm thu $\le 30\%$ và mục tiêu nội bộ $\le 20\%$)
* **Độ bao phủ Hán tự trung bình:** `65.58%`
* **Điểm tin cậy dóng hàng trung bình:** `0.62 / 1.00` (`0.6192`)
* **Khớp 100% `VPO_01_parallel.tsv` == `VPO_01_parallel.xlsx` (`DONG_HANG`):** Đạt

---

### 3. Cấu trúc thư mục bàn giao

```text
CV04_VPO_01/
├── 01_nguon/           # Ảnh scan trang sách gốc 300 DPI (.png)
├── 02_ocr_tho/         # Kết quả OCR thô ban đầu (han/, viet/, ocr_results.jsonl, ocr_run_summary.json)
├── 03_text_sach/       # Văn bản đã làm sạch (han.txt, viet.txt)
├── 04_dong_hang/       # VPO_01_parallel.tsv, VPO_01_parallel.xlsx, qa_report.json, word_coverage_report.json
└── README.md           # Tài liệu thuyết minh phương pháp & kết quả
```
