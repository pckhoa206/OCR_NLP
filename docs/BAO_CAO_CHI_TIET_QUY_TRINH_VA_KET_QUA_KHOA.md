# BÁO CÁO CHI TIẾT QUY TRÌNH THỰC HIỆN, PHÂN TÍCH LỖI & THÔNG SỐ KẾT QUẢ (NHÁNH `khoa`)

- **Phạm vi báo cáo**: Toàn bộ mã nguồn lõi hệ thống, gói Pilot/Demo Giảng viên và kết quả chạy thật Kaggle GPU v4 trên **397(+1) = 398 trang** được phân công cho thành viên **Khoa** (`outputs/khoa/`).
- **Nhánh Git lưu trữ**: [`khoa`](https://github.com/pckhoa206/OCR_NLP/tree/khoa)
- **Quy chuẩn đối chiếu**: [`Guideline.pdf`](../Guideline.pdf) (Mục 1–9) & phản hồi trực tiếp của Giảng viên hướng dẫn.

---

## 1. Kế Hoạch & Kết Quả Làm Sạch Kho Mã Nguồn Trên Nhánh `khoa`

Trước khi đẩy lên nhánh `khoa`, toàn bộ workspace đã được rà soát và phân tách rõ theo 3 nhóm để vừa giữ 100% khả năng tái lập hệ thống & kiểm chứng đầu ra, vừa loại bỏ các tệp dư thừa/trùng lặp:

### 1.1. Những thư mục & tệp cốt lõi được giữ lại và đẩy lên nhánh `khoa`
| Thành phần | Vai trò trong hệ thống |
| :--- | :--- |
| `src/` (12 tệp) | Lõi xử lý ngôn ngữ, khử nhầm nét Hán–Việt (`ocr_disambiguator.py`, `phonetic_verifier.py`), làm sạch giữ nguyên bản (`text_cleaner.py`), máy trạng thái tách bài (`work_segmenter.py`), dóng hàng 4 cột (`aligner.py`, `poetic_aligner.py`, `semantic_scorer.py`, `corpus_pipeline.py`), QA/xuất `.tsv`+`.xlsx` (`exporter_and_qa.py`, `word_aligner.py`) và CAT Workbench (`workbench_editor.py`). |
| `kaggle_ocr/` (4 tệp) | Script OCR GPU (`ocr_pipeline_kaggle.py`), script điều phối Kaggle CLI (`deploy_to_kaggle.sh`) và metadata dataset/kernel. |
| `scripts/` (10 tệp) | `extract_pages.swift`, `split_member_data.py`, `run_pilot_demo.py`, `demo_1_2_pages.py`, `run_end_to_end.py`, `kaggle_full_inference.py`, `inspect_alignment.py`, `diagnose_corpus_quality.py`, `package_hf_dataset.py`, `eval_translation_benchmark.py`. |
| `config/` (3 tệp) | `book_manifest.json` (quy đổi trang & lược đồ 4 cột), `member_splits.json` (chia 4 shard), `tickets.json` (`21/21` ticket `DONE`). |
| `web_app/app.py` & `tests/` (8 tệp) | Giao diện hậu kiểm Streamlit CAT Workbench và toàn bộ 87 ca kiểm thử đơn vị/tích hợp/hồi quy. |
| `outputs/khoa/` | Toàn bộ đầu ra chạy thật 398 trang của Khoa: `alignment_summary.json`, `02_ocr_tho/{han,viet}/*.json`, `03_text_sach/{han.txt,viet.txt}`, `04_dong_hang/<CODE>_parallel.{tsv,xlsx}`, `qa_report.json`, `word_coverage_report.json`, văn bản bổ sung Bài 3 `TVLT2`, kèm `.gitkeep` tại `01_nguon/{han,viet}/`. |
| `deliverables/`, `demo_giang_vien/`, `dataset_export/`, `docs/` | Bộ Pilot 4 cột (`deliverables/`), Gói Demo Giảng viên (`demo_giang_vien/` kèm ảnh đối soát), bản xuất JSONL (`dataset_export/`), và toàn bộ báo cáo/kiểm kê (`docs/`). |

### 1.2. Các tệp trùng lặp & tạm thời đã dọn dẹp (`~8.5 MB` + cache)
- **Đã xóa 10 tệp `ocr_results.jsonl`** gộp trùng lặp hoàn toàn với các tệp trang đơn trong `02_ocr_tho/{han,viet}/*.json`:
  - `outputs/khoa/ocr_results.jsonl` (`4,052 KB`) và 3 tệp `outputs/khoa/deliverables/*/02_ocr_tho/ocr_results.jsonl` (`544 KB + 2,736 KB + 776 KB`).
  - 6 tệp `ocr_results.jsonl` cũ trong `deliverables/*/` (`~367 KB`).
- **Đã xóa `deliverables/full_ocr_summary.json`** (`0.8 KB`, tệp tóm tắt cũ không còn dùng trong pipeline 4 cột).
- **Đã xóa tệp log & cache cục bộ**: `outputs/khoa/han-viet-parallel-corpus-ocr-pipeline.log`, toàn bộ `__pycache__/`, `.pytest_cache/`, `.DS_Store`.
- Đã cập nhật `.gitignore` để ngăn tái phát sinh các tệp gộp trùng lặp (`**/ocr_results.jsonl`, `deliverables/full_ocr_summary.json`).

### 1.3. Các thành phần giữ cục bộ ngoài GitHub theo `.gitignore`
- 3 tệp PDF scan gốc trong `data/*.pdf` (~167 MB, vượt giới hạn 100 MB/tệp của GitHub).
- Ảnh PNG dung lượng lớn ngoài tập Pilot (`deliverables/**/01_nguon/*.png`, `outputs/**/*.png` ~185 MB) — cấu trúc `01_nguon/{han,viet}` vẫn được giữ trên Git bằng `.gitkeep`.
- Môi trường ảo `.venv/`, tệp điều phối agent nội bộ (`.agents/`, `.gemini/`, `AGENTS.md`), và notebook độc lập ngoài đồ án `OPRB_Qwen2_5_VL_3B_Test_Evaluation.ipynb` (được giữ nguyên trên đĩa cục bộ nhưng không đẩy lên repo).

---

## 2. Quy Trình Thực Hiện Chi Tiết (7 Giai Đoạn Kỹ Thuật)

### Giai đoạn 1 — Kiểm kê PDF, Quy đổi Trang & Phân chia Shard (`T01`, `T05`, `T19`)
1. Từ `1,996` trang PDF của 3 cổ thư trong `data/`, dùng [`scripts/extract_pages.swift`](../scripts/extract_pages.swift) (PDFKit macOS, `216 DPI` / render scale `3.0x`) tách ra **`1,584` trang PNG hợp lệ** (bảo toàn thêm trang `PDF 7` của `HVTT` là trang tiêu đề bài 1 *Tử Sản thụ chính Thái Thúc*).
2. Chuẩn hóa công thức quy đổi trong [`config/book_manifest.json`](../config/book_manifest.json):
   - **`HVTT`**: `pdf_page = book_page + 6`, phạm vi `PDF 7..381` (`375` trang).
   - **`TVLT2`**: `book_page = pdf_page + 2` (`PDF >= 7`), `795` trang (`PDF 17..861`), loại trang scan trắng `PDF 25` và 4 tác phẩm Chữ Nôm (`PDF 493..525`, `688..703`, `862..873`).
   - **`TLTVN`**: `pdf_page = book_page + 7`, chỉ dóng hàng Phần Ba (`PDF 134..547`, `414` trang).
3. Phân chia 4 thành viên trong [`config/member_splits.json`](../config/member_splits.json): shard **Khoa** nhận `397` trang trong phân công gốc cộng `PDF 7` (`HVTT`) = **`398` trang** (`HVTT`: `95` trang `PDF 7..101`; `TVLT2`: `199` trang `PDF 17..216` trừ `25`; `TLTVN`: `104` trang `PDF 134..237`).

### Giai đoạn 2 — Tiền Xử lý Hình học & Dual-OCR trên Kaggle GPU (`T02`, `T06`, `T21`)
Chạy trên Kaggle GPU thông qua [`kaggle_ocr/ocr_pipeline_kaggle.py`](../kaggle_ocr/ocr_pipeline_kaggle.py) và [`kaggle_ocr/deploy_to_kaggle.sh`](../kaggle_ocr/deploy_to_kaggle.sh):
- **Dual-OCR theo văn tự**: `PaddleOCR` (`chinese_cht`) cho chữ Hán phồn thể và `VietOCR` (`vgg_transformer`) kết hợp detector cho chữ Quốc ngữ có dấu phụ/chú thích mũ.
- **Tiền xử lý đặc thù từng sách**:
  - Cắt top `7%` running header (`crop_running_header`), phát hiện đường kẻ ngang chân trang chú thích `detect_footnote_separator` cho `TLTVN`, khử hộp bao chồng lấn (`deduplicate_overlapping_items`).
  - Với `HVTT` (`group_layout_blocks`): tách riêng **9 trang tiêu đề lẻ** (`odd_title_page`), **36 trang `Dịch thơ` đối diện** (`odd_page_dich_tho` kèm tọa độ `dich_tho_y_centers`), bỏ qua trang tiểu sử thuần văn xuôi, gộp dòng `Phiên âm` bị ngắt xuống dòng trên trang chẵn (`10/10` cụm), và tự nhận diện bài chỉ có `Hán + Phiên âm + Dịch thơ` (`has_dich_nghia = False`, ví dụ `PDF 100`, `PDF 367..381`).
  - Với `TVLT2` và `TLTVN`: trích xuất đầy đủ `dich_tho_lines` (kể cả phần *Dịch theo nguyên điệu* ở `TLTVN`) tách biệt khỏi các mục dừng thật (`KHẢO ĐÍNH`, `CHÚ THÍCH`).

### Giai đoạn 3 — Khử Nhầm Nét Chữ Hán & Đối Soát Âm Hán–Việt 1:1 (`T02`, `T17`)
- [`src/ocr_disambiguator.py`](../src/ocr_disambiguator.py): từ điển **105+ cụm chữ Hán dễ nhầm nét** (`257` ký tự, `24` chữ đa âm như `戊/戌/戍`, `己/已/巳`, `日/曰`, `侯/候`, `祇/祗`) kết hợp đối chiếu âm Hán–Việt từ cột `Phiên âm`.
- [`src/phonetic_verifier.py`](../src/phonetic_verifier.py): kiểm tra khớp âm tiết `1:1` giữa chữ Hán và `Phiên âm`, đồng thời nội suy dấu câu tiếng Hán từ dấu câu của `Phiên âm` (`project_punctuation_from_phien_am`) cho các dòng Hán in rời trong `HVTT`.

### Giai đoạn 4 — Làm Sạch Bảo Toàn Nguyên Bản & Chuẩn Hóa `UTF-8 NFC` (`T03`, `T20`)
- [`src/text_cleaner.py`](../src/text_cleaner.py): chuẩn hóa toàn bộ văn bản sang `UTF-8` dựng sẵn (`Unicode NFC`).
- **Không làm hỏng dữ liệu gốc (`Guideline Mục 4.1`)**: giữ nguyên chữ cổ, chữ dị thể, dấu gạch nối cũ, ký hiệu chữ khuyết `□`, và **bảo toàn 100% năm, niên hiệu, ngày tháng, con số** (chỉ loại ký tự mũ/chú thích `[1]`, `1*`, `(?)`, dấu `?` lỗi OCR giữa câu trước chữ thường, hoặc số trang/running header trước bước tách câu `split_viet_sentences`).

### Giai đoạn 5 — Máy Trạng Thái Phân Đoạn Tác Phẩm (`T21`)
- [`src/work_segmenter.py`](../src/work_segmenter.py) phân đoạn liên trang chính xác cấu trúc `WorkRecord` / `SubPoem`:
  - **`TVLT2` (199 trang Khoa)**: tách đúng **58 tác phẩm**, bao gồm tích hợp đủ **15 đoạn** văn xuôi bổ sung Bài 3 (*Thiền tông chỉ nam tự*, do `PDF 25` bị trắng) từ tệp Google Drive Giảng viên cung cấp, Bài 5 (*Phổ thuyết tứ sơn* gồm văn xuôi xen 5 bài `Kệ`), Bài 21 (*Niêm tụng kệ* chia **43 tiết** `SubPoem`), và chặn trích dẫn chữ Hán nằm lọt bên trong mục `CHÚ THÍCH`.
  - **`TLTVN` (104 trang Khoa)**: tách đúng **36 tác phẩm / 50 mục tiêu đề** (kể cả chùm *liên hoàn từ* `I..IV`), xử lý ngắt chân trang `p0139` và phục hồi 7 tiêu đề nằm ở mép trên `y = 0`.

### Giai đoạn 6 — Dóng Hàng 4 Cột Thống Nhất & Dòng Tiêu Đề Riêng (`T03`, `T13`, `T22`)
- [`src/aligner.py`](../src/aligner.py) & [`src/corpus_pipeline.py`](../src/corpus_pipeline.py):
  - Toàn bộ 3 bộ sách xuất cùng cấu trúc **4 cột**: `Hán | Dịch âm | Dịch nghĩa | Dịch thơ`, kèm **dòng tiêu đề riêng (`is_title`)** đứng đầu mỗi tác phẩm/tiết điệu từ (bảo vệ không cho trộn vào câu thân bài).
  - Văn xuôi và thơ dài dùng **Plateau Prior DP** (dải tỷ lệ độ dài phẳng `[0.80, 2.40]`, 10 hạt `1-1`, `1-2`, `2-1`, `1-3`, `3-1`, `2-2`, `1-4`, `4-1`, `2-3`, `3-2`), kết hợp điểm neo chữ số – dấu câu và [`CrossLingualSemanticScorer`](../src/semantic_scorer.py).
  - `HVTT` trang đối diện dùng `align_hvtt_facing_dich_tho` dựa trên trục tung $Y$ và nối vế `1-n` bằng `" / "` để không làm rơi bất kỳ câu `Dịch thơ` nào; đồng thời chiếu `Phiên âm` tuyến tính (`align_phien_am_to_han_chunks`) cho các đoạn bị tách hạt.

### Giai đoạn 7 — Kiểm Định QA, Xuất `.tsv`/`.xlsx` & CAT Workbench (`T04`, `T18`, `T20`, `T23`)
- [`src/exporter_and_qa.py`](../src/exporter_and_qa.py): kiểm tra 6 tiêu chí QA (`MISSING`, `OMISSION`, `ADDITION`, `FORMAT_ERROR`, `LEFTOVER_MARKER`, `NUMBER_MISMATCH`), xuất đồng thời `.tsv` (`UTF-8 NFC`) và `.xlsx` (2 sheet `DONG_HANG` + `THONG_KE`) khớp 100%.
- [`src/workbench_editor.py`](../src/workbench_editor.py) & [`web_app/app.py`](../web_app/app.py): cung cấp giao diện hậu kiểm trực quan từng dòng gắn cờ kèm ảnh gốc để `Edit / Split / Merge / Insert / Delete` và tái xuất nguyên tử.

---

## 3. Phân Tích Lỗi Toàn Diện (Đã Khắc Phục & Còn Tồn Đọng)

### 3.1. Các lỗi từ nhận xét Demo Giảng viên & pipeline cũ đã khắc phục triệt để (100%)
| Hạng mục lỗi trước đây | Nguyên nhân gốc | Giải pháp đã triển khai (`T19–T23`) |
| :--- | :--- | :--- |
| Thiếu tiêu đề bài đầu `HVTT` (*Tử Sản thụ chính Thái Thúc*) và bài cuối (*Thu dạ hoài ngâm*) | `book_manifest.json` bắt đầu từ `PDF 8` bỏ qua `PDF 7`; trang tiêu đề lẻ chưa gán `is_title` | Mở rộng `valid_range` từ `PDF 7` (`375` tr), tách `0007.png` + `0367.png`, sinh dòng tiêu đề riêng ở đầu mỗi bài. |
| Thiếu cột `Dịch thơ` ở bài 1 `HVTT` | Chưa có bộ dóng `Dịch thơ` trang lẻ đối diện với khối văn ngôn trang chẵn | Thêm `odd_page_dich_tho` & `align_hvtt_facing_dich_tho` dóng theo tọa độ `Y` và nối `" / "`. |
| Lệch 2 cột vs 4 cột ở `TVLT2` và `TLTVN` | Pipeline cũ xuất 2 cột `Hán | Việt`, trộn thơ/văn xuôi và bỏ sót *Dịch theo nguyên điệu* | Thống nhất chuẩn **4 cột** cho cả 3 sách, đưa `Dịch thơ` / *Dịch theo nguyên điệu* vào cột 4, để trống `""` khi là văn xuôi. |
| Mất tác phẩm nửa dưới trang hoặc cắt nhầm ở `DỊCH THƠ` | `is_stop_section_header` coi `DỊCH THƠ` là điểm dừng trang giống `KHẢO ĐÍNH` | Tách nhãn `"dich_tho"` khỏi `"stop"`, chặn trích dẫn trong `CHÚ THÍCH` bằng `src/work_segmenter.py`. |
| Xóa nhầm chữ số/niên hiệu hoặc vỡ dòng ở dấu `?` lỗi OCR | Regex làm sạch chạy sau tách câu và chưa phân biệt số chú thích với năm/niên hiệu | Làm sạch ký tự nhiễu `(?)`, `1*`, `N%` trước `split_viet_sentences`, bảo toàn chữ số 4 chữ số & ngày tháng. |
| Trùng tên tệp `HVTT_parallel.*` cạnh `HVTT_HanVanTinhTuy_parallel.*` | Demo runner cũ ghi file ngắn song song với tên chuẩn theo mã đề tài | Chuẩn hóa một tên duy nhất `<MA_DE_TAI>_<MA_TAC_PHAM>_parallel.{tsv,xlsx}` trên cả Pilot và `outputs/khoa/`. |

### 3.2. Chi tiết 141 dòng gắn cờ QA còn tồn đọng trên `outputs/khoa/` (`5.67%`)
Trên tổng số **`2,488` cặp** chạy từ OCR thật của Khoa, hệ thống đạt **`MISSING = 0`**, **`FORMAT_ERROR = 0`**, **`LEFTOVER_MARKER = 0`**, và còn **`141` dòng duy nhất** (`144` lượt cờ) bị `validate_pairs` cảnh báo để rà soát thủ công (chi tiết từng dòng xem tại [`DANH_SACH_HAU_KIEM_LOI.md`](DANH_SACH_HAU_KIEM_LOI.md)):

| Bộ sách | Tổng cặp | Dòng gắn cờ | Tỷ lệ lỗi | Phân rã theo loại cờ & Nguyên nhân chính |
| :--- | :---: | :---: | :---: | :--- |
| **`HVTT`** | `275` | **`8`** | **`2.91%`** | `8 OMISSION` (`0 ADDITION`, `0 NUMBER_MISMATCH`): chủ yếu câu dịch xuôi cô đọng (tỉnh lược hư từ `之`, `也`) + 2 lỗi chính tả dấu tiếng Việt nhẹ từ OCR (`gọc` -> `gốc` tại dòng TSV `160`, `hiều` -> `hiếu` tại dòng TSV `176`). |
| **`TVLT2`** | `1,693` | **`117`** *(118 lượt cờ)* | **`6.91%`** | - **`7 ADDITION`** (TSV `329, 334, 416, 495, 694, 725, 1032`): DP dồn nhiều câu Việt vào 1 mệnh đề Hán ngắn -> ưu tiên `Split`/`Merge` trong CAT Workbench.<br>- **`78 OMISSION`**: gồm nhãn chuyển tiết *Niêm tụng kệ* (`公頌` <-> `Tụng`), câu dịch cô đọng, và một số câu rớt từ cuối trang văn xuôi.<br>- **`33 NUMBER_MISMATCH`**: đa số do lỗi dấu thanh VietOCR ở chữ số Hán–Việt (`lứ đại`/`tứ đại`, `sảu đường`/`sáu đường`, `tử chi`/`tứ chi`, `tạm bảo`/`tam bảo`, `van`/`vạn`), nhầm chữ Hán gần nét (`八`/`入`, `九`/`凡`), hoặc dịch ước lệ (`三尺之童` <-> `đứa bé lên bảy`). |
| **`TLTVN`** | `520` | **`16`** *(18 lượt cờ)* | **`3.08%`** | `15 OMISSION`, `3 NUMBER_MISMATCH` (dòng TSV `5` và `364` trùng 2 cờ): chủ yếu 5 vị trí lệch ranh giới 1 dòng ở cột `Dịch nghĩa` (TSV `5, 125, 361, 364, 368`) và câu tiểu dẫn dài tách đôi (*Thập cửu phong*). |
| **Tổng** | **`2,488`** | **`141`** | **`5.67%`** | Sâu dưới ngưỡng nghiệm thu **$\le 30.0\%$** và mục tiêu nội bộ **$\le 20.0\%$** (`Guideline Mục 8`). |

---

## 4. Bảng Tổng Hợp Thông Số Kết Quả Đã Kiểm Chứng

### 4.1. Kết quả Shard Khoa — Kaggle GPU v4 ([`outputs/khoa/alignment_summary.json`](../outputs/khoa/alignment_summary.json))
| Bộ sách | Trang OCR thật | Tổng cặp | Dòng tiêu đề | Dòng có `Dịch thơ` | Phủ Hán TB | Tin cậy TB | `MISSING` | Tỷ lệ lỗi QA | `TSV == XLSX` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`HVTT`** | `95` (`0007..0101`) | **275** | `10` | `256` | `65.71%` | `0.6040` | `0` | **2.91%** (`0.029091`) | Khớp 100% |
| **`TVLT2`** | `199` (`0017..0216`, trừ `25`) | **1,693** | `58` | `222` | `44.09%` | `0.5004` | `0` | **6.91%** (`0.069108`) | Khớp 100% |
| **`TLTVN`** | `104` (`0134..0237`) | **520** | `50` | `377` | `53.17%` | `0.5383` | `0` | **3.08%** (`0.030769`) | Khớp 100% |
| **Tổng (`Khoa`)** | **398 trang** | **2,488** | **118** | **855** | — | — | **`0`** | **5.67%** | **100%** |

- **Đạt mốc khối lượng Guideline Mục 1**: **`2,488` cặp** ($\ge 2,000$ cặp/thành viên, vượt `+24.4%`).

### 4.2. Bộ Pilot, Gói Demo Giảng Viên & Kiểm Định Toàn Hệ Thống
| Hạng mục kiểm chứng | Thông số xác nhận |
| :--- | :--- |
| **Bộ Pilot 4 cột (`deliverables/`)** | `HVTT`: **28** cặp (`0.00%` lỗi); `TVLT2`: **15** cặp (`0.00%` lỗi); `TLTVN`: **5** cặp (`0.00%` lỗi); `TSV == XLSX` 100%. |
| **Gói Demo Giảng viên (`demo_giang_vien/`)** | `HVTT_demo`: **12** dòng (`0.00%` lỗi); `TVLT2_demo`: **12** dòng (`0.00%` lỗi); `TLTVN_demo`: **5** dòng (`0.00%` lỗi); kèm ảnh nguồn `01_nguon_demo/`. |
| **Bộ kiểm thử tự động (`.venv/bin/pytest tests/ -q`)** | **87 / 87 test PASS (`100%`)**, `0` thất bại, `0` bỏ qua. |
| **Cổng đánh giá `review_evaluator.py`** | `"status": "APPROVED"`, `"issues": []`, `"test_status": "PASS"` (`returncode: 0`). |
| **Tiến độ DAG (`config/tickets.json`)** | `21 / 21` ticket đạt `DONE` (`T01..T23`). |
