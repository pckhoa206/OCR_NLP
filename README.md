# Hệ Thống Số Hóa, OCR & Dóng Hàng Ngữ Liệu Song Ngữ Hán – Việt
### Sino-Vietnamese Classical OCR, Disambiguation & 4-Column Parallel Alignment System

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-87%20passed%20(100%25)-brightgreen.svg)]()
[![Khoa QA Error Rate](https://img.shields.io/badge/Khoa%20QA%20Error-2.91%25--6.91%25-success.svg)]()
[![Pilot & Demo QA](https://img.shields.io/badge/Pilot%20%26%20Demo%20QA-0.00%25-brightgreen.svg)]()
[![Schema](https://img.shields.io/badge/Schema-4%20C%E1%BB%99t%20%2B%20Ti%C3%AAu%20%C4%90%E1%BB%81-informational.svg)]()
[![Streamlit UI](https://img.shields.io/badge/UI-Streamlit%20CAT%20Workbench-FF4B4B.svg)](https://streamlit.io/)
[![Zero-Dependency XLSX](https://img.shields.io/badge/OpenXML-Pure%20Standard%20Library-orange.svg)]()

---

## 1. Tổng Quan Dự Án

Dự án xây dựng pipeline khép kín phục vụ **Số hóa tài liệu Hán–Việt cổ**, **OCR đa mô hình trên Kaggle GPU (PaddleOCR + VietOCR)**, **khử nhầm nét chữ Hán nhờ đối soát âm Hán–Việt 1:1**, **phân đoạn tác phẩm bằng máy trạng thái hữu hạn**, **dóng hàng câu 4 cột**, và **hậu kiểm tương tác qua CAT Workbench (Streamlit)** cho 3 bộ cổ thư văn học trung đại Việt Nam theo đúng quy chuẩn [`Guideline.pdf`](Guideline.pdf).

### Lược đồ thống nhất 4 cột & Nguyên tắc bảo toàn
- **Cấu trúc cột thống nhất trên cả 3 bộ sách**:
  `Hán` | `Dịch âm` | `Dịch nghĩa` | `Dịch thơ`
- **Dòng tiêu đề tác phẩm tách riêng (`is_title`)**: Mỗi bài thơ, bài văn xuôi, bài kệ hoặc tiểu phẩm trong chùm *liên hoàn từ* có dòng tiêu đề riêng đặt trước thân bài; không gộp tiêu đề vào câu mở đầu.
- **Bảo toàn nguyên bản (`Guideline Mục 4.1–4.2`)**: Không tự ý hiện đại hóa chữ cổ/dị thể hay dấu nối cũ, bảo toàn chữ khuyết `□`, giữ nguyên năm/niên hiệu/ngày tháng/con số, để trống `""` khi nguyên bản khuyết cột (ví dụ bài thơ không có `Dịch nghĩa` hoặc văn xuôi không có `Dịch thơ`), chuẩn hóa toàn bộ văn bản ở `UTF-8 NFC`.
- **Xuất song song `.tsv` và `.xlsx` chuẩn (`Guideline Mục 7`)**: Xuất đồng thời `<MA_DE_TAI>_<MA_TAC_PHAM>_parallel.tsv` và `<MA_DE_TAI>_<MA_TAC_PHAM>_parallel.xlsx` (2 sheet `DONG_HANG` và `THONG_KE`), khớp 100% từng ô, không phụ thuộc `pandas`/`openpyxl` để đọc/ghi `.xlsx`.

---

## 2. Ba Bộ Cổ Thư Mục Tiêu

Từ **1.996 trang PDF scan**, hệ thống trích xuất **1.584 trang hợp lệ** (loại bìa, mục lục, khảo đính, scan trắng, 4 tác phẩm Chữ Nôm):

| Mã sách | Tên tác phẩm | Tổng trang PDF | Trang hợp lệ (`01_nguon`) | Quy đổi trang | Đặc thù bố cục & Xử lý |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **`HVTT`** | *Hán Văn Tinh Túy* (Lãng Nhân) | 386 | **375** (`PDF 7..381`) | `pdf_page = book_page + 6` | Trang lẻ chứa **tiêu đề tác phẩm** (`0007`, `0017`, ..., `0367`) hoặc **Dịch thơ đối diện**; trang chẵn chứa xen kẽ `Hán + Phiên âm + Dịch nghĩa`. Bài *Thạch Hào lại* (`PDF 100`) và bài cuối *Thu dạ hoài ngâm* (`PDF 367–381`) giữ đủ 4 cột và để trống `Dịch nghĩa = ""`. |
| **`TVLT2`** | *Thơ văn Lý – Trần, Tập II* (Nguyễn Huệ Chi chủ biên) | 965 | **795** (`PDF 17..861`) | `book_page = pdf_page + 2` *(PDF >= 7)* | Loại trang trắng `PDF 25` và **4 tác phẩm Chữ Nôm** (`PDF 493..525`, `688..703`, `862..873`). Tích hợp bản dịch bài 3 (*Thiền tông chỉ nam tự*) tại `deliverables/TVLT2_ThoVanLyTran2/01_nguon/bai_03_thien_tong_chi_nam_tu_dich_nghia.txt`. Tách 58 tác phẩm bằng `src/work_segmenter.py` (gồm *Niêm tụng kệ*, *Phổ thuyết tứ sơn* `Kệ`). |
| **`TLTVN`** | *Thể loại từ Việt Nam thời trung đại* (Nguyễn Xuân Diện – Nguyễn Quảng Tuân) | 645 | **414** (`PDF 134..547`) | `pdf_page = book_page + 7` *(sách 1..593)* | Chỉ xử lý **Phần Ba** (sách `127..540`). Cắt top 7% running header, phát hiện chân trang chú thích, xử lý *liên hoàn từ* (`I..IV`), đưa *Dịch theo nguyên điệu* vào cột `Dịch thơ`. Thống kê bài khuyết gốc & Phụ lục 3 tại [`docs/THONG_KE_BO_SUNG_GIANG_VIEN.md`](docs/THONG_KE_BO_SUNG_GIANG_VIEN.md). |

---

## 3. Cấu Trúc Thư Mục Hệ Thống & Quy Chuẩn Bàn Giao

### 3.1. Cây mã nguồn chính
```text
.
├── config/                    # book_manifest.json, member_splits.json, tickets.json
├── src/                       # Lõi xử lý ngôn ngữ & dóng hàng
│   ├── aligner.py             # Plateau Prior DP (1-1/1-n/n-1/n-m), facing Dịch thơ, chiếu Phiên âm
│   ├── work_segmenter.py      # Máy trạng thái tách tác phẩm / liên hoàn từ / Niêm tụng kệ
│   ├── corpus_pipeline.py     # Điều phối dóng hàng toàn quyển từ 02_ocr_tho -> 03_text_sach & 04_dong_hang
│   ├── text_cleaner.py        # Làm sạch UTF-8 NFC, giữ nguyên chữ cổ, năm/niên hiệu/con số
│   ├── ocr_disambiguator.py   # Khử 105+ cụm chữ Hán dễ nhầm nét + đối chiếu đa âm
│   ├── phonetic_verifier.py   # Đối chiếu âm Hán–Việt 1:1 & chiếu dấu câu từ Phiên âm
│   ├── poetic_aligner.py      # Dóng hàng thơ/từ khúc và song đối Đường luật
│   ├── semantic_scorer.py     # Chấm điểm ngữ nghĩa đa ngữ (BGE-M3/LaBSE + fallback offline)
│   ├── word_aligner.py        # Đo độ phủ ký tự/từ mức mịn
│   ├── exporter_and_qa.py     # Kiểm định QA 6 tiêu chí + xuất .tsv & .xlsx 2 sheet không thư viện ngoài
│   └── workbench_editor.py    # Backend cho CAT Workbench (edit/split/merge/insert/delete)
├── kaggle_ocr/                # Pipeline chạy OCR GPU trên Kaggle & script điều phối CLI
│   ├── ocr_pipeline_kaggle.py # PaddleOCR (chinese_cht) + VietOCR + phân tích bố cục trang
│   ├── deploy_to_kaggle.sh    # Đóng gói dataset, đẩy kernel, kiểm tra trạng thái, tải output
│   ├── dataset-metadata.json
│   └── kernel-metadata.json
├── scripts/                   # Kịch bản CLI chạy cục bộ, demo, chia shard, kiểm tra, benchmark
│   ├── extract_pages.swift    # Tách ảnh PNG từ PDF bằng PDFKit trên macOS
│   ├── run_pilot_demo.py      # Sinh lại bộ Pilot chuẩn (deliverables/)
│   ├── demo_1_2_pages.py      # Sinh gói Demo Giảng viên 4 cột (demo_giang_vien/)
│   ├── run_end_to_end.py      # Chạy pipeline hoàn chỉnh (--skip-ocr, --gpu, --book, --pilot-only)
│   ├── split_member_data.py   # Kiểm chứng & đóng gói shard cho 4 thành viên (Khoa, Hiếu, Khánh, Kin)
│   ├── kaggle_full_inference.py # Tải JSON/lịch sử và điều phối suy luận Kaggle toàn quyển
│   ├── inspect_alignment.py   # Kiểm tra nhanh các cặp dóng hàng & báo cáo QA từ terminal
│   ├── diagnose_corpus_quality.py # Sinh docs/BAO_CAO_CHAN_DOAN_CHAT_LUONG.md
│   ├── package_hf_dataset.py  # Đóng gói Hugging Face JSONL splits (dataset_export/)
│   └── eval_translation_benchmark.py # Đánh giá BLEU/chrF tham chiếu
├── web_app/app.py             # Giao diện Streamlit CAT Workbench hậu kiểm song ngữ + ảnh gốc
├── tests/                     # Bộ 87 unit/integration/smoke tests (unittest & pytest)
├── deliverables/              # Cây đầu ra Pilot chuẩn 4 cột theo Guideline Mục 2
├── demo_giang_vien/           # Gói Demo 1-2 trang 4 cột kèm ảnh đối soát & BAO_CAO_DEMO_GIANG_VIEN.md
├── outputs/khoa/              # Kết quả chạy thật Kaggle GPU v4 shard Khoa (398 trang, 2.488 cặp)
├── dataset_export/            # Xuất dữ liệu train/validation/test JSONL
├── docs/                      # Toàn bộ kiểm kê nguồn, báo cáo tổng kết, danh sách hậu kiểm lỗi
├── Guideline.pdf              # Tài liệu yêu cầu chính thức của đồ án
└── requirements.txt
```

### 3.2. Cấu trúc bàn giao chuẩn mỗi bộ sách (`Guideline Mục 2`)
```text
<root>/deliverables/<MA_DE_TAI>_<MA_TAC_PHAM>/
├── 01_nguon/
│   ├── han/                   # Ảnh nguồn các trang có chữ Hán
│   └── viet/                  # Ảnh nguồn các trang có bản dịch tiếng Việt
├── 02_ocr_tho/
│   ├── han/                   # JSON OCR thô chữ Hán từng trang kèm tọa độ
│   └── viet/                  # JSON OCR thô chữ Việt / Dịch thơ từng trang
├── 03_text_sach/
│   ├── han.txt                # Văn bản Hán đã làm sạch UTF-8 NFC
│   └── viet.txt               # Văn bản Việt đã làm sạch UTF-8 NFC
└── 04_dong_hang/
    ├── <CODE>_parallel.tsv    # Bảng 4 cột phân cách Tab (\t)
    ├── <CODE>_parallel.xlsx   # Sheet DONG_HANG + sheet THONG_KE (khớp 100% TSV)
    ├── qa_report.json
    └── word_coverage_report.json
```

### 3.3. Thành phần được loại trừ trong `.gitignore`
Để giữ dung lượng repository gọn và tuân thủ giới hạn 100 MB/tệp của GitHub:
- Ba tệp PDF nguồn (`data/*.pdf`, ~167 MB) và phần lớn ảnh PNG đã tách ngoài tập pilot (`deliverables/**/01_nguon/*.png`, `outputs/**/*.png`).
- Log chạy nền (`outputs/**/*.log`), môi trường ảo (`.venv/`), cache Python.
- Tệp điều phối agent nội bộ (`.agents/`, `.gemini/`, `AGENTS.md`) — do đó nếu clone mới mà chưa có các tệp cục bộ này, test `test_skills_and_agents_md_exist` và kiểm tra thư mục ảnh `outputs/khoa/deliverables/*/01_nguon/{han,viet}` trong `tests/test_t22_4col_alignment.py` sẽ cần tái tạo ảnh hoặc chạy chọn lọc theo hướng dẫn ở Mục 4.

---

## 4. Cài Đặt & Hướng Dẫn Chạy Hệ Thống

### 4.1. Thiết lập môi trường
Yêu cầu Python 3.10+ (và `swift` + PDF nguồn đặt trong `data/` nếu tự trích xuất lại PNG trên macOS):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4.2. Các lệnh vận hành chính

1. **Trích xuất ảnh trang sách từ PDF (tùy chọn khi có 3 tệp PDF trong `data/`):**
   ```bash
   swift -module-cache-path /tmp/clang_cache scripts/extract_pages.swift --pilot --book ALL --dpi 216
   # Hoặc trích xuất trang cụ thể (ví dụ trang tiêu đề bài 1 HVTT):
   swift -module-cache-path /tmp/clang_cache scripts/extract_pages.swift --book HVTT --pages 7 --dpi 216
   ```

2. **Tái tạo Gói Demo Giảng viên (`demo_giang_vien/`) & Bộ Pilot (`deliverables/`):**
   ```bash
   python3 scripts/demo_1_2_pages.py --book ALL
   python3 scripts/run_pilot_demo.py
   ```

3. **Chạy pipeline dóng hàng từ dữ liệu OCR JSON (`02_ocr_tho`, không cần GPU):**
   ```bash
   python3 scripts/run_end_to_end.py --skip-ocr
   # Hoặc chạy kèm cờ: --book {HVTT,TVLT2,TLTVN}, --pilot-only, --no-downstream
   ```

4. **Kiểm tra chia shard 4 thành viên & Đẩy chạy OCR trên Kaggle GPU:**
   > Lưu ý: Người dùng tự cấu hình khóa API cá nhân tại `~/.kaggle/kaggle.json` (tuyệt đối không đưa lên repository).
   ```bash
   python3 scripts/split_member_data.py --verify
   ./kaggle_ocr/deploy_to_kaggle.sh --stage-images
   ./kaggle_ocr/deploy_to_kaggle.sh --push-dataset
   ./kaggle_ocr/deploy_to_kaggle.sh --push-kernel
   ./kaggle_ocr/deploy_to_kaggle.sh --status
   ./kaggle_ocr/deploy_to_kaggle.sh --pull-output
   ```

5. **Khởi chạy CAT Workbench để hậu kiểm các dòng bị gắn cờ:**
   ```bash
   streamlit run web_app/app.py
   ```

6. **Chẩn đoán chất lượng, đóng gói Hugging Face JSONL & đánh giá benchmark:**
   ```bash
   python3 scripts/diagnose_corpus_quality.py
   python3 scripts/package_hf_dataset.py
   python3 scripts/eval_translation_benchmark.py
   ```

7. **Chạy toàn bộ bộ kiểm thử tự động:**
   ```bash
   .venv/bin/pytest tests/ -v
   ```

---

## 5. Kết Quả Thực Nghiệm Đã Kiểm Chứng

### 5.1. Kết quả chạy thật trên Kaggle GPU v4 — Shard Khoa (`outputs/khoa/`, 398 trang)
Nguồn kiểm chứng: [`outputs/khoa/alignment_summary.json`](outputs/khoa/alignment_summary.json)

| Bộ sách | Số trang OCR thật | Tổng số cặp | Dòng tiêu đề | Dòng có `Dịch thơ` | `MISSING` | Lỗi QA | `TSV == XLSX` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`HVTT`** | `95` (`0007..0101`) | **275** | `10` | `256` | `0` | **2.91%** (`8` dòng) | Khớp 100% |
| **`TVLT2`** | `199` (`0017..0216`, trừ `25`) | **1.693** | `58` | `222` | `0` | **6.91%** (`117` dòng) | Khớp 100% |
| **`TLTVN`** | `104` (`0134..0237`) | **520** | `50` | `377` | `0` | **3.08%** (`16` dòng) | Khớp 100% |
| **Tổng (`Khoa`)** | **398 trang** | **2.488** | **118** | **855** | **0** | **5.67%** *(141/2.488)* | **100%** |

- Vượt mức chỉ tiêu khối lượng tối thiểu **>= 2.000 cặp/thành viên** theo Guideline Mục 1 (**2.488 cặp**).
- Tỷ lệ lỗi QA nằm sâu dưới ngưỡng nghiệm thu **<= 30%** (và mục tiêu **<= 20%**), **`MISSING = 0`**, **`FORMAT_ERROR = 0`**, **`LEFTOVER_MARKER = 0`**.

### 5.2. Pilot (`deliverables/`), Demo Giảng viên (`demo_giang_vien/`) & Kiểm thử
- **Bộ Pilot 4 cột**: `HVTT` **28** cặp, `TVLT2` **15** cặp, `TLTVN` **5** cặp — **0.00%** lỗi QA, khớp 100% `.tsv`/`.xlsx`.
- **Gói Demo Giảng viên**: `HVTT_demo` **12** dòng, `TVLT2_demo` **12** dòng, `TLTVN_demo` **5** dòng — **0.00%** lỗi QA.
- **Kiểm thử tự động trên workspace đầy đủ**: **87 / 87 test PASS (100%)** (`0` thất bại, `0` bỏ qua).

---

## 6. Tài Liệu Dự Án Liên Quan

- Báo cáo chi tiết quy trình, lỗi & thông số kết quả nhánh `khoa`: [`docs/BAO_CAO_CHI_TIET_QUY_TRINH_VA_KET_QUA_KHOA.md`](docs/BAO_CAO_CHI_TIET_QUY_TRINH_VA_KET_QUA_KHOA.md)
- Báo cáo tổng kết nhóm & 5 tiêu chí Guideline Mục 9: [`docs/BAO_CAO_TONG_KET_NHOM.md`](docs/BAO_CAO_TONG_KET_NHOM.md)
- Bảng kê chi tiết 141 dòng hậu kiểm thủ công (Guideline Mục 8): [`docs/DANH_SACH_HAU_KIEM_LOI.md`](docs/DANH_SACH_HAU_KIEM_LOI.md)
- Báo cáo demo theo yêu cầu Giảng viên: [`demo_giang_vien/BAO_CAO_DEMO_GIANG_VIEN.md`](demo_giang_vien/BAO_CAO_DEMO_GIANG_VIEN.md)
- Kiểm kê nguồn tài liệu & công thức quy đổi trang: [`docs/BANG_KIEM_KE_NGUON.md`](docs/BANG_KIEM_KE_NGUON.md)
- Thống kê các bài khuyết gốc & Phụ lục 3 (`TLTVN`): [`docs/THONG_KE_BO_SUNG_GIANG_VIEN.md`](docs/THONG_KE_BO_SUNG_GIANG_VIEN.md)
- Phân công shard 4 thành viên & nghiên cứu SOTA: [`docs/PHAN_CONG_4_THANH_VIEN.md`](docs/PHAN_CONG_4_THANH_VIEN.md), [`docs/NGHIEN_CUU_VA_TOI_UU_SOTA.md`](docs/NGHIEN_CUU_VA_TOI_UU_SOTA.md)
- Trạng thái DAG & bàn giao phiên làm việc: [`docs/WAYFINDER.md`](docs/WAYFINDER.md), [`docs/HANDOFF.md`](docs/HANDOFF.md)
