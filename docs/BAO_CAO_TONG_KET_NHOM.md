# BÁO CÁO TỔNG HỢP ĐỒ ÁN: SỐ HÓA, OCR & DÓNG HÀNG NGỮ LIỆU SONG NGỮ HÁN – VIỆT

- **Nhóm thực hiện (04 thành viên)**: **Khoa**, **Hiếu**, **Khánh**, **Kin**
- **Ngày cập nhật báo cáo**: `2026-11-22`
- **Kho mã nguồn**: [github.com/pckhoa206/OCR_NLP](https://github.com/pckhoa206/OCR_NLP)
- **Quy chuẩn áp dụng**: [`Guideline.pdf`](../Guideline.pdf) (Mục 1–9) & chỉ đạo cụ thể của Giảng viên hướng dẫn

---

## 1. Mục tiêu đề tài & Quy chuẩn nghiệm thu (Guideline Mục 1–3, 7–8)

Theo [`Guideline.pdf`](../Guideline.pdf):
- **Chỉ tiêu khối lượng nhóm 4 thành viên (tài liệu PDF Scan cần OCR)**: Tối thiểu **2.000 cặp câu hợp lệ/thành viên** ($\ge$ **8.000 cặp hợp lệ/nhóm**).
- **Lược đồ thống nhất 4 cột toàn hệ thống**: Toàn bộ cả 3 bộ sách (`HVTT`, `TVLT2`, `TLTVN`) đều được chuẩn hóa về cấu trúc **4 cột thống nhất**: `Hán | Dịch âm | Dịch nghĩa | Dịch thơ`, kèm **dòng tiêu đề tách riêng cho từng tác phẩm/tiết bài** và xử lý cột khuyết hợp lệ theo nguyên bản (ví dụ bài thơ chỉ có `Dịch thơ` để trống `Dịch nghĩa = ""`, văn xuôi không có thơ để trống `Dịch thơ = ""`).
- **Quy cách tệp nộp chuẩn**: Xuất đồng thời `<MA_DE_TAI>_<MA_TAC_PHAM>_parallel.tsv` (`UTF-8 NFC`, phân cách bằng ký tự Tab `\t`, không dùng nhiều dấu cách thay Tab, không chứa `\t`/`\n` nội ô) và `<MA_DE_TAI>_<MA_TAC_PHAM>_parallel.xlsx` (sheet 1 `DONG_HANG` có hàng 1 là tiêu đề `Hán | Dịch âm | Dịch nghĩa | Dịch thơ`, hàng $i+1$ khớp **100%** dòng $i$ của `.tsv`; sheet 2 `THONG_KE`); không giữ file ngắn trùng tên (`HVTT_parallel.*`, `TVLT2_parallel.*`, `TLTVN_parallel.*`).
- **Ngưỡng chất lượng (Mục 8)**: Tỷ lệ lỗi tối đa cho phép $\le \mathbf{30.0\%}$ (mục tiêu biên an toàn nội bộ $\le \mathbf{20.0\%}$), kiểm tra theo `MISSING`, `OMISSION`, `ADDITION`, `FORMAT_ERROR`, `LEFTOVER_MARKER`, `NUMBER_MISMATCH`.
- **Quy tắc bảo toàn văn bản (Mục 4.1–4.2)**: Không tự ý hiện đại hóa chữ cổ/dị thể, bảo toàn chữ khuyết (`□`), giữ nguyên niên hiệu/năm/ngày tháng/con số theo nguồn, chuẩn hóa `UTF-8 NFC`.

---

## 2. Kiểm kê nguồn tài liệu & Tuân thủ cấu trúc thư mục (Guideline Mục 2 & 4)

Từ **1.996 trang PDF scan gốc** trong thư mục `data/`, hệ thống tách ảnh PNG 300 DPI bằng [`scripts/extract_pages.swift`](../scripts/extract_pages.swift), loại trừ bìa/mục lục/khảo đính/Chữ Nôm/scan trắng để giữ lại **1.584 trang nội dung hợp lệ** (gồm `1.583` trang trong phân công gốc cộng thêm `0007.png` trang tiêu đề bài 1 `HVTT` bổ sung ở giai đoạn T19):

| Mã sách | Tên tác phẩm | Tổng trang PDF | Trang PNG hợp lệ (`01_nguon/`) | Công thức quy đổi trang | Quy cách 4 cột & Phạm vi đặc thù |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **`HVTT`** | *Hán Văn Tinh Túy* (Lãng Nhân) | 386 | **375** (`0007..0381`) | `pdf_page = book_page + 6` | Trang lẻ chứa **tiêu đề tác phẩm** (`0007`, `0017`, ..., `0367`) hoặc **Dịch thơ đối diện**; trang chẵn chứa xen kẽ `Hán + Phiên âm + Dịch nghĩa`. Bài *Thạch Hào lại* (`PDF 100`) và bài cuối *Thu dạ hoài ngâm* (`PDF 367–381`) để trống cột `Dịch nghĩa` (`""`), giữ nguyên `Hán`, `Dịch âm`, `Dịch thơ`. |
| **`TVLT2`** | *Thơ văn Lý – Trần, Tập II* (Nguyễn Huệ Chi chủ biên) | 965 | **795** (`0017..0861`) | `book_page = pdf_page + 2` *(PDF $\ge$ 7)* | Loại trang scan trắng `PDF 25` và **4 tác phẩm Chữ Nôm** (`PDF 493..525`, `688..703`, `862..873`). Tích hợp bản dịch bổ sung bài 3 (*Thiền tông chỉ nam tự*) tại `deliverables/TVLT2_ThoVanLyTran2/01_nguon/bai_03_thien_tong_chi_nam_tu_dich_nghia.txt`. Văn xuôi để `Dịch thơ = ""`; thơ/kệ điền đủ cột `Dịch thơ`. |
| **`TLTVN`** | *Thể loại từ Việt Nam thời trung đại* (Nguyễn Xuân Diện – Nguyễn Quảng Tuân) | 645 | **414** (`0134..0547`) | `pdf_page = book_page + 7` *(sách 1..593)* | Chỉ dóng hàng **Phần Ba: Tuyển tập từ Việt Nam thời trung đại** (sách `127..540`). Xuất đủ 4 cột gồm tiêu đề điệu từ (kể cả liên hoàn từ `I, II, III...`) và đưa *Dịch theo nguyên điệu* vào cột `Dịch thơ`. Thống kê các bài khuyết gốc & Phụ lục 3 tại [`docs/THONG_KE_BO_SUNG_GIANG_VIEN.md`](THONG_KE_BO_SUNG_GIANG_VIEN.md). |
| **Tổng** | **03 bộ cổ thư** | **1.996** | **1.584 trang PNG** | — | Chuẩn hóa 100% cấu trúc bàn giao theo Guideline Mục 2. |

### Tuân thủ cây thư mục bàn giao (Guideline Mục 2 & Bước 3)
Với kết quả chạy thật của thành viên Khoa (`outputs/khoa/deliverables/<MA_DE_TAI>_<MA_TAC_PHAM>/`), đầy đủ các thư mục bắt buộc đều tồn tại và đồng bộ:
- `01_nguon/han/` và `01_nguon/viet/`: chứa ảnh trang gốc tách theo vai trò (ví dụ Khoa: `HVTT` 57 trang có Hán / 95 trang có Việt; `TVLT2` 199/199; `TLTVN` 104/104).
- `02_ocr_tho/han/` và `02_ocr_tho/viet/`: lưu nguyên trạng JSON OCR thô từng trang (`0007.json`...) để truy vết tọa độ bounding-box 1–1.
- `03_text_sach/han.txt` và `03_text_sach/viet.txt`: văn bản Hán và Việt đã làm sạch `UTF-8 NFC`, khớp từng dòng với bảng dóng hàng.
- `04_dong_hang/`: chỉ chứa tên tệp chuẩn `<MA_DE_TAI>_<MA_TAC_PHAM>_parallel.{tsv,xlsx}` kèm `qa_report.json` và `word_coverage_report.json`.
- **Bảo mật tuyệt đối**: Không chứa bất kỳ tệp `.cookie`, token, credential hay `kaggle.json` nào trong toàn bộ `deliverables/` và `outputs/`.

---

## 3. Phân chia dữ liệu 4 thành viên & Tiến độ thực thi thực tế

Toàn bộ kho trang hợp lệ được chia cân bằng theo từng quyển trong [`config/member_splits.json`](../config/member_splits.json) (bảo toàn cặp trang đối diện `(chẵn, lẻ)` trong `HVTT`, kèm trang tiêu đề `0007.png` bổ sung vào phần việc của Khoa nâng tổng số trang chạy thực tế của Khoa lên **`397(+1) = 398` trang**):

| Thành viên | Mã shard | `HVTT` | `TVLT2` | `TLTVN` | Tổng trang thực thi | Trạng thái Kaggle GPU v4 |
| :--- | :---: | :--- | :--- | :--- | :---: | :--- |
| **Khoa** | `khoa` | **95 tr** (`PDF 7–101`) | **199 tr** (`PDF 17–216`) | **104 tr** (`PDF 134–237`) | **398 trang** *(397+1)* | **Đã hoàn tất & nghiệm thu (`2.488` cặp)** |
| **Hiếu** | `hieu` | 94 tr (`PDF 102–195`) | 199 tr (`PDF 217–415`) | 104 tr (`PDF 238–341`) | 397 trang | Đã phân shard chuẩn bị đẩy Kaggle GPU |
| **Khánh** | `khanh` | 94 tr (`PDF 196–289`) | 199 tr (`PDF 416–647`) | 103 tr (`PDF 342–444`) | 396 trang | Đã phân shard chuẩn bị đẩy Kaggle GPU |
| **Kin** | `kin` | 92 tr (`PDF 290–381`) | 198 tr (`PDF 648–861`) | 103 tr (`PDF 445–547`) | 393 trang | Đã phân shard chuẩn bị đẩy Kaggle GPU |

---

## 4. Kết quả thực nghiệm định lượng (Pilot & Chạy thật Kaggle GPU v4)

### 4.1. Kết quả chạy thật trên Kaggle GPU v4 — Shard Khoa (`outputs/khoa/`, 398 trang)

Kết xuất trực tiếp từ `outputs/khoa/alignment_summary.json` (`ocr_mode = kaggle_gpu`, `source_mode = ocr_json`):

| Bộ sách | Số trang OCR thật | Tổng số cặp | Dòng tiêu đề | Dòng có `Dịch thơ` | `MISSING` | `OMISSION` | `ADDITION` | `NUMBER_MISMATCH` | Tỷ lệ lỗi QA | Phủ Hán TB | Tin cậy TB | `TSV == XLSX` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`HVTT`** | **95** | **275** | **10** | **256** | **0** | 8 | 0 | 0 | **2.91%** (`0.029091`) | 65.71% | 0.6040 | Khớp 100% |
| **`TVLT2`** | **199** | **1.693** | **58** | **222** | **0** | 78 | 7 | 33 | **6.91%** (`0.069108`) | 44.09% | 0.5004 | Khớp 100% |
| **`TLTVN`** | **104** | **520** | **50** | **377** | **0** | 15 | 0 | 3 | **3.08%** (`0.030769`) | 53.17% | 0.5383 | Khớp 100% |
| **Tổng (`Khoa`)** | **398** | **2.488** | **118** | **855** | **0** | **101** | **7** | **36** | **5.67%** *(141/2.488)* | — | — | **Khớp 100%** |

- **Đạt và vượt chỉ tiêu Guideline Mục 1**: Một thành viên (`Khoa`) đã đạt **`2.488` cặp hợp lệ** ($\ge 2.000$ cặp yêu cầu, vượt `+24.4%`).
- **Đạt sâu ngưỡng chất lượng Guideline Mục 8**: Tỷ lệ lỗi QA từng quyển đạt **`2.91% – 6.91%`** (sâu dưới ngưỡng nghiệm thu $\le 30.0\%$ và mục tiêu nội bộ $\le 20.0\%$), **`MISSING = 0`**, **`FORMAT_ERROR = 0`**, **`LEFTOVER_MARKER = 0`**.

### 4.2. Kết quả Pilot Deliverables (`deliverables/`) & Gói Demo Giảng viên (`demo_giang_vien/`)

| Tập dữ liệu | Bộ sách | Cấu trúc | Số cặp | Lỗi QA | Ghi chú kiểm chứng |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Pilot (`deliverables/`)** | `HVTT` | 4 cột | **28** | **0.00%** | Gồm tiêu đề bài 1 (`子產授政太叔`), `24` dòng có `Dịch thơ`, bài cuối trống `Dịch nghĩa`; phủ Hán TB `96.79%`, tin cậy TB `0.8156`. |
| **Pilot (`deliverables/`)** | `TVLT2` | 4 cột | **15** | **0.00%** | Gồm tiêu đề 3 bài (`寄清風庵僧德山`, `送北使張顯卿`, `禪宗指南序`), `6` dòng có `Dịch thơ`, bài 3 văn xuôi GDrive; phủ Hán TB `81.00%`, tin cậy TB `0.7745`. |
| **Pilot (`deliverables/`)** | `TLTVN` | 4 cột | **5** | **0.00%** | Gồm tiêu đề điệu từ (`阮郎歸`), `4` dòng có *Dịch theo nguyên điệu*; phủ Hán TB `100.00%`, tin cậy TB `0.8131`. |
| **Demo (`demo_giang_vien/`)** | 3 bộ `*_demo` | 4 cột | **12 + 12 + 5** | **0.00%** | Sinh bởi [`scripts/demo_1_2_pages.py`](../scripts/demo_1_2_pages.py), kèm ảnh nguồn đối soát `01_nguon_demo/` và báo cáo [`BAO_CAO_DEMO_GIANG_VIEN.md`](../demo_giang_vien/BAO_CAO_DEMO_GIANG_VIEN.md). |

### 4.3. Kiểm thử tự động toàn hệ thống & Hạ tầng phân chia
- **Bộ kiểm thử tự động (`./.venv/bin/pytest tests/ -v`)**: **87 / 87 test PASS (`100%`)**, không có test bị bỏ qua hay thất bại; bao gồm kiểm thử đơn vị, tích hợp 4 cột, smoke test `demo_1_2_pages.py`, kiểm tra tính bất biến `outputs/khoa/alignment_summary.json` và cổng [`review_evaluator.py`](file:///Users/khoa/.gemini/config/skills/subagent-plan-reviewer/scripts/review_evaluator.py).
- **Kiểm tra chia shard 4 thành viên (`python3 scripts/split_member_data.py --verify`)**: `"status": "VERIFIED"`, `0` trang trùng lặp.

---

## 5. Phương pháp đề xuất & Đối chiếu đầy đủ 5 tiêu chí (Guideline Mục 9)

Hệ thống đề xuất chuỗi pipeline tự động kết hợp hậu kiểm tương tác dựa trên 5 trụ cột kỹ thuật sau:

1. **Lựa chọn OCR & Kết quả thực nghiệm (`kaggle_ocr/ocr_pipeline_kaggle.py`, `src/ocr_disambiguator.py`)**:
   - Kết hợp hai mô hình chuyên biệt theo chữ viết: **PaddleOCR (`chinese_cht`)** cho chữ Hán phồn thể in mộc bản/typo và **VietOCR (`vgg_transformer`)** (kết hợp detector của PaddleOCR) cho tiếng Việt nhiều dấu phụ và chú thích mũ.
   - Tiền xử lý chuyên biệt: cắt top 7% running header (`crop_running_header`), phát hiện đường kẻ chân trang (`detect_footnote_separator`) cho `TLTVN`, khử trùng lặp hộp bao (`deduplicate_overlapping_items`), và khử **105+ cụm chữ Hán dễ nhầm nét** (257 ký tự, 24 chữ đa âm như `戊/戌/戍`, `己/已/巳`, `日/曰`, `侯/候`, `祇/祗`) bằng đối chiếu âm Hán–Việt 1:1 (`src/phonetic_verifier.py`).
   - Kết quả thực nghiệm thực tế: xử lý ổn định **398 trang ảnh trên Kaggle GPU** đạt `MISSING = 0` và độ khớp âm Hán–Việt 100% trên toàn bộ mẫu chuẩn.

2. **Tách câu & Phân đoạn tác phẩm (`src/work_segmenter.py`, `src/text_cleaner.py`)**:
   - **Tách tác phẩm xuyên trang (`WorkRecord` / `SubPoem`)**: Máy trạng thái hữu hạn trong `src/work_segmenter.py` phân tách 58 tác phẩm `TVLT2` (kể cả *Niêm tụng kệ* 43 tiết, *Phổ thuyết tứ sơn* 5 bài kệ, Bài 3 bổ sung) và 50 đơn vị `TLTVN` (kể cả liên hoàn từ `I..IV`), phân biệt chính xác mục `DỊCH THƠ` với điểm dừng thật (`KHẢO ĐÍNH`, `CHÚ THÍCH`), chặn chú thích đánh số cuối trang và giữ nguyên trích dẫn chữ Hán nằm giữa đoạn Việt.
   - **Tách bố cục `HVTT` (`group_layout_blocks`)**: Phân tách trang tiêu đề lẻ (`odd_title_page`), trang `Dịch thơ` đối diện (`odd_page_dich_tho`), gộp dòng `Phiên âm` bị xuống dòng theo dải tọa độ dọc trên trang chẵn và tự động nhận diện bài thiếu `Dịch nghĩa` (`has_dich_nghia = False`).
   - **Tách câu nhận biết ngữ cảnh (`split_han_sentences`, `split_viet_sentences`)**: Bảo vệ danh sách viết tắt học thuật (`GS.TS.`, `NXB.`, `Tr.`, `Tp.`, `v.v.`) trước khi tách câu tiếng Việt; giữ tách câu Hán mềm dẻo theo `。！？；` và dấu câu nội suy từ `Phiên âm`.

3. **Thuật toán dóng hàng (`src/aligner.py`, `src/poetic_aligner.py`, `src/semantic_scorer.py`)**:
   - Quy hoạch động **Plateau Prior DP** trong phạm vi từng tác phẩm với vùng tỷ lệ độ dài phẳng $[0.80, 2.40]$ (tỷ lệ chuẩn 1 chữ Hán $\approx$ 1.8 từ Việt), hỗ trợ đầy đủ 10 loại hạt (`1-1`, `1-2`, `2-1`, `1-3`, `3-1`, `2-2`, `1-4`, `4-1`, `2-3`, `3-2` — tương ứng `1-1`, `1-n`, `n-1`, `n-m` trong Guideline Mục 3.1).
   - Kết hợp điểm neo từ vựng – số đếm – dấu câu, điểm tương đồng ngữ nghĩa đa ngữ (`CrossLingualSemanticScorer` hỗ trợ BGE-M3/LaBSE và fallback anchor offline), dóng hàng song đối thơ Đường luật, dóng hàng `Dịch thơ` trang đối diện theo trục tung $Y$ (`align_hvtt_facing_dich_tho`), và chiếu tuyến tính `Phiên âm` (`align_phien_am_to_han_chunks`).

4. **Kiểm soát lỗi, làm sạch bảo toàn nguyên bản & CAT Workbench (`src/text_cleaner.py`, `src/exporter_and_qa.py`, `src/workbench_editor.py`, `web_app/app.py`)**:
   - Làm sạch **không phá hủy nguyên bản**: chuyển toàn bộ về `UTF-8 NFC`, giữ nguyên chữ cổ/dị thể và ký hiệu chữ khuyết `□`, **bảo toàn 100% năm, niên hiệu, ngày tháng và con số** (chỉ xóa ký tự mũ/chú thích `[1]`, `1*`, `(?)`, dấu `?` lỗi OCR giữa câu trước chữ thường).
   - Hệ thống kiểm định tự động `validate_pairs` phát hiện 6 nhóm lỗi (`MISSING`, `OMISSION < 0.7`, `ADDITION > 4.5`, `FORMAT_ERROR`, `LEFTOVER_MARKER`, `NUMBER_MISMATCH`) và đo phủ từ vựng ở mức từ (`src/word_aligner.py`).
   - Giao diện **CAT Workbench** (`web_app/app.py` + `src/workbench_editor.py`) cho phép hậu kiểm viên đối chiếu ảnh gốc và thực hiện nguyên tử các thao tác `edit`, `split`, `merge`, `insert`, `delete`, tự động tái xuất đồng bộ `.tsv`, `.xlsx` 2 sheet và `qa_report.json`.

5. **Đánh giá chất lượng & Hậu kiểm lỗi thủ công (`docs/DANH_SACH_HAU_KIEM_LOI.md`)**:
   - Đánh giá định lượng đồng thời theo tỷ lệ lỗi QA (`2.91% – 6.91%` trên Kaggle v4, `0.00%` trên Pilot/Demo), độ phủ từ vựng (`word_aligner.py`), tính toàn vẹn định dạng (`TSV == XLSX`, `MISSING = 0`) và điểm dịch máy tham chiếu (`eval_translation_benchmark.py`).
   - Toàn bộ **141 dòng còn gắn cờ** (`8` ở `HVTT`, `117` ở `TVLT2`, `16` ở `TLTVN`) đã được xuất bảng kê chi tiết kèm vị trí dòng TSV/XLSX và hướng dẫn sửa tay tại [`docs/DANH_SACH_HAU_KIEM_LOI.md`](DANH_SACH_HAU_KIEM_LOI.md) theo đúng yêu cầu Guideline Mục 8.

### Tổng hợp đối chiếu 5 yêu cầu giải trình bắt buộc của Guideline Mục 9

| Tiêu chí Guideline Mục 9 | Nội dung giải trình của phương pháp đề xuất |
| :--- | :--- |
| **1. Lý do lựa chọn** | Sách scan Hán–Việt cổ có lớp text ẩn hỏng (`TLTVN`), đan xen chữ Hán phồn thể và Quốc ngữ nhiều dấu phụ (`VietOCR` vượt trội Tesseract trên chữ Việt in cổ), bố cục biến thiên theo quyển (`HVTT` xen dòng & đối trang, `TVLT2`/`TLTVN` theo khối xuyên trang). Do đó cần kết hợp dual-OCR + khử nhầm nét dựa trên `Phiên âm` + máy trạng thái tách bài + Plateau DP + CAT Workbench để vừa đạt độ chính xác cao vừa kiểm soát chặt ranh giới tác phẩm. |
| **2. Dữ liệu đầu vào và đầu ra** | **Đầu vào**: 3 bộ PDF scan (`data/*.pdf`) $\rightarrow$ ảnh PNG 300 DPI (`01_nguon/*.png`) + bảng cấu hình `config/book_manifest.json` + bản dịch bổ sung bài 3 `TVLT2`. **Đầu ra**: OCR thô JSON theo trang (`02_ocr_tho/{han,viet}/*.json`), văn bản sạch `UTF-8 NFC` (`03_text_sach/{han.txt,viet.txt}`), bảng dóng hàng 4 cột đồng bộ `<BOOK>_parallel.tsv` và `<BOOK>_parallel.xlsx` (2 sheet `DONG_HANG`, `THONG_KE`), `qa_report.json`, và danh sách hậu kiểm [`docs/DANH_SACH_HAU_KIEM_LOI.md`](DANH_SACH_HAU_KIEM_LOI.md). |
| **3. Cách kiểm chứng** | (i) Tự động kiểm thử toàn trình qua **87/87 pytest cases PASS** (`./.venv/bin/pytest tests/ -v`) và cổng `review_evaluator.py` (`APPROVED`, `PASS`); (ii) Kiểm định QA 6 tiêu chí (`validate_pairs`) xác nhận `MISSING = 0`, `FORMAT_ERROR = 0`, `error_rate = 2.91%–6.91%`; (iii) Đối chiếu vòng tròn `read_tsv == read_xlsx_zero_dep`; (iv) Thống kê phủ từ vựng mức ký tự Hán (`word_aligner.py`) và xuất danh sách hậu kiểm tay. |
| **4. Rủi ro và phương án dự phòng** | (i) *Thiếu GPU cục bộ / giới hạn phiên Kaggle*: chia shard 4 thành viên (`split_member_data.py`), hỗ trợ `--mock` offline để kiểm thử logic và chạy tiếp từ `02_ocr_tho` (`--skip-ocr`); (ii) *Mất/lỗi trang scan gốc* (`PDF 25 TVLT2`, bài khuyết `TLTVN`): cơ chế nạp bổ sung văn bản ngoài (`bai_03_...txt`) và lập bảng kê gửi Giảng viên; (iii) *Nhầm chữ Hán gần nét hoặc sai dấu câu OCR Việt*: sửa tự động bằng 105+ cụm nhầm lẫn + tách câu linh hoạt ở mệnh đề; (iv) *Còn sót lệch dòng cục bộ (~5.67%)*: cô lập bằng `qa_report.json` và hiệu đính trực tiếp qua CAT Workbench (`web_app/app.py`). |
| **5. Khả năng tái lập bởi người khác** | Toàn bộ mã nguồn, cấu hình (`config/book_manifest.json`, `config/member_splits.json`), môi trường Python (`.venv`, không phụ thuộc thư viện đóng gói ngoài cho TSV/XLSX), script tách ảnh Swift, script đẩy/tải Kaggle (`kaggle_ocr/deploy_to_kaggle.sh`), và lệnh chạy 1 bước (`scripts/run_end_to_end.py --skip-ocr`, `scripts/run_pilot_demo.py`, `scripts/demo_1_2_pages.py`) đều được đóng gói tự động, xác định (deterministic) và kiểm chứng bằng bộ test tự động. |

---

## 6. Thống kê các phần đề xuất Giảng viên hỗ trợ bổ sung (`TLTVN`)

Chi tiết đầy đủ xem tại [`docs/THONG_KE_BO_SUNG_GIANG_VIEN.md`](THONG_KE_BO_SUNG_GIANG_VIEN.md); tóm tắt 2 nhóm cần bổ sung:
1. **Bài khuyết văn bản gốc trong Phần Ba**:
   - **04 bài Nôm của Phạm Thái** (*Sơ kính tân trang*, `tr. 371–373` / `PDF 378–380`): chỉ có Quốc ngữ, khuyết hoàn toàn chữ gốc Hán/Nôm và Dịch nghĩa.
   - **03 bài tàn khuyết một phần chữ Hán**: Lý Đạo Tái (`tr. 131–133` / `PDF 138–140`, mất hạ phiến), Nguyễn Huy Oánh (`tr. 214–218` / `PDF 221–225`, khuyết 1 chữ `□`), Phạm Nguyễn Du (`tr. 296–297` / `PDF 303–304`, mất hạ phiến).
2. **Các quyển chỉ có chữ Hán trong Phụ lục 3 (`tr. 545–596` / `PDF 552–604`)**:
   - *Thạc Đình di cảo* (9/9 bài từ đã dịch), *Hoa thiều ngâm lục* (8/8 bài từ đã dịch, còn 9 bài thơ thất ngôn kèm theo chưa dịch), *Lưu Hương kí* (4/4 bài từ đã dịch, còn bài *Thu tứ ca* chưa dịch).
   - Trọng tâm là tập ***Cổ duệ từ*** của Nguyễn Phúc Miên Thẩm (`tr. 572–596` / `PDF 579–604`): gồm 114 bài từ nhưng Phần Ba mới dịch 6 bài, còn **108 bài từ (98 đề mục) chỉ có nguyên bản chữ Hán chưa có bản dịch**.
