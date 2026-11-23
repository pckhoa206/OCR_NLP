# Dóng Hàng Hán – Việt (Nhóm CV04)

Xây dựng kho ngữ liệu song ngữ văn học Hán – Việt (thơ ca & văn xuôi) ở cấp câu/đoạn phục vụ đồ án giữa kỳ môn **Xử lý Ngôn ngữ Tự nhiên (NLP)**.

- **Mã nhóm / Đề tài**: `CV04`
- **Thành viên nhóm**:
  1. **Trần Trung Hiếu** *(Nhóm trưởng)* — Nhánh `hieu` (`397` trang phân công)
  2. **Lê Gia Khánh** — Nhánh `khanh` (`396` trang phân công)
  3. **Phạm Chấn Khoa** — Nhánh `khoa` / `mac` (`397` trang phân công)
  4. **Cái Hoàng Bảo Kin** — Nhánh `kin` (`393` trang phân công)
- **Giảng viên / Trợ giảng hướng dẫn**: Chị **Lưu Như**
- **Hạn nộp bài**: `30/11`

---

## 1. Phạm Vi Tư Liệu & Phân Công Thực Hiện

Từ **1.996 trang PDF scan gốc** của 3 bộ sách trong `raw_data/`, nhóm `CV04` đã kiểm kê và xác định **1.584 trang hợp lệ** trong [`config/book_manifest.json`](config/book_manifest.json) (trong đó **1.583 trang** được chia đều cho 4 thành viên trong [`config/member_splits.json`](config/member_splits.json) và [`docs/3_PHAN_CONG_4_NGUOI.md`](docs/3_PHAN_CONG_4_NGUOI.md); trang chênh lệch là `PDF 0007` — trang tiêu đề bài 1 của `VPO_01` nằm trong tập `pilot_pages`):

| Mã thư mục / Mã sách | Tên tác phẩm & Tác giả | Tổng PDF | Phạm vi hợp lệ & Quy đổi trang | Ghi chú xử lý đặc thù |
| :--- | :--- | :---: | :--- | :--- |
| **`CV04_VPO_01`** (`VPO_01` / `HVTT`) | *Hán Văn Tinh Túy* — Lãng Nhân (Phùng Tất Đắc) | `386` | Sách `1..375` (`PDF 7..381`, `375` tr; phân công `374` tr `PDF 8..381`)<br>`pdf_page = book_page + 6` | Trang chẵn in xen kẽ `Hán + Phiên âm + Dịch nghĩa`, trang lẻ đối diện in `Dịch thơ` (riêng các trang lẻ đầu bài như `0007, 0017...` là trang tiêu đề). Bài *Thạch Hào lại* (`PDF 100`) và bài cuối *Thu dạ hoài ngâm* (`PDF 367..381`) để trống cột `Dịch nghĩa` (`""`). |
| **`CV04_VPO_02`** (`VPO_02` / `TLTVN`) | *Thể loại từ Việt Nam thời trung đại* — Phạm Văn Ánh / Nguyễn Xuân Diện – Nguyễn Quảng Tuân | `645` | **Phần Ba** sách `127..540` (`PDF 134..547`, phân công `414` tr; trừ 3 trang khuyết gốc `378..380` còn `411` tr khi dóng hàng)<br>`pdf_page = book_page + 7` | Bỏ qua lớp text PDF bị mất chữ Hán, OCR toàn bộ ảnh 300 DPI (cắt 7% running header + tách đường kẻ ngang chú thích chân trang). Đưa *Phiên âm* $\rightarrow$ `Dịch âm`, *Dịch nghĩa* $\rightarrow$ `Dịch nghĩa`, *Dịch theo nguyên điệu* $\rightarrow$ `Dịch thơ`. Chi tiết bài khuyết gốc & Phụ lục 3 tại [`docs/2_THONG_KE_BO_SUNG.md`](docs/2_THONG_KE_BO_SUNG.md). |
| **`CV04_VPO_03`** (`VPO_03` / `TVLT2`) | *Thơ văn Lý – Trần (Tập II – Quyển Thượng)* — Nguyễn Huệ Chi chủ biên | `965` | Sách `19..863` (`PDF 17..861`, `795` tr hợp lệ)<br>`book_page = pdf_page + 2` *(từ PDF 7)* | Loại trang trắng `PDF 25` và **4 tác phẩm Chữ Nôm** (`PDF 493..525`, `688..703`, `862..873`). Tích hợp bản dịch nghĩa bài 3 (*Thiền tông chỉ nam tự*) của chị Lưu Như tại [`CV04_VPO_03/01_nguon/bai_03_thien_tong_chi_nam_tu_dich_nghia.txt`](CV04_VPO_03/01_nguon/bai_03_thien_tong_chi_nam_tu_dich_nghia.txt). Thơ/kệ điền đủ 4 cột; văn xuôi để trống `Dịch thơ = ""`. |

---

## 2. Trạng Thái Hiện Tại Trên Các Nhánh Git & Máy Local

> **Lưu ý quan trọng về trạng thái dữ liệu hiện tại**: Toàn bộ mã nguồn (`src/`, `web_app/`, `tests/`, `config/`, `main.py`, `docs/`) đồng bộ giữa nhánh **`khanh`** và **`kin`**, trong khi thư mục dữ liệu **`CV04_VPO_01..03/` trên mỗi nhánh đang lưu riêng kết quả OCR & dóng hàng của thành viên đó** (chưa hợp nhất chung cả 4 thành viên vào 1 bộ tổng):

1. **Trên máy local hiện tại (`01_nguon/` & nhánh `khanh`)**:
   - **`01_nguon/*.png`** (các ảnh bulk 300 DPI được `.gitignore` loại trừ khỏi Git, chỉ track các ảnh `pilot_pages`): Trên ổ đĩa local hiện có **đầy đủ ảnh 300 DPI của cả Khánh (`396` trang) lẫn Kin (`393` trang)** cùng các trang pilot (`CV04_VPO_01`: `194` ảnh; `CV04_VPO_02`: `213` ảnh; `CV04_VPO_03`: `406` ảnh + file `.txt` bổ sung bài 3).
   - **`02_ocr_tho/`, `03_text_sach/`, `04_dong_hang/` trên nhánh `khanh`**: Lưu **toàn bộ kết quả OCR GPU (`paddleocr_chinese_cht` + `vietocr_vgg_transformer`) và dóng hàng 4 cột của Khánh (`396/396` trang phân công)** cùng bộ trang `pilot_pages` (lưu ý `CV04_VPO_01` có 5 trang pilot `312, 326, 367, 368, 369` thuộc dải trang Kin do nằm trong `pilot_pages` của `book_manifest.json`). **Không** chứa toàn bộ dữ liệu OCR/dóng hàng của Kin.
2. **Trên nhánh `kin`**:
   - **`02_ocr_tho/`, `03_text_sach/`, `04_dong_hang/`**: Lưu **toàn bộ kết quả OCR GPU (`paddleocr_chinese_cht` + `vietocr_vgg_transformer`) và dóng hàng 4 cột của Kin (`393/393` trang phân công)** cùng các trang `pilot_pages` ngoài shard (`8` trang ở `VPO_01`, `7` trang ở `VPO_02`, `9` trang ở `VPO_03`). *(Ghi chú: trong `CV04_VPO_01/02_ocr_tho/ocr_run_summary.json` của nhánh `kin` chỉ ghi log `69` trang của lượt chạy `308..381`, nhưng toàn bộ `92/92` trang `0290..0381` đều đã có đủ file JSON GPU trong `02_ocr_tho/{han,viet}/`.)*
3. **Các nhánh khác trên `origin`**:
   - **`khoa` / `mac`**: Hoàn thành OCR GPU & dóng hàng cho shard `khoa` (`397` trang phân công; trên nhánh `origin/khoa` lưu tại `outputs/khoa/` với `2.488` dòng từ `398` trang OCR, lỗi QA `5.67%`).
   - **`hieu`**: Đã có kết quả OCR GPU cho shard `hieu` (`397` trang phân công) trong cấu trúc thư mục cũ `deliverables/` (`109 + 115 + 212` JSON), chờ hợp nhất sang `CV04_VPO_01..03`.

### Số liệu đã kiểm chứng trên nhánh `khanh` và nhánh `kin`

| Nhánh | Thư mục / Tác phẩm | JSON OCR (`han`/`viet`) | Dòng dóng hàng | Dòng tiêu đề | Dòng có `Dịch thơ` | Lỗi QA *(ngưỡng $\le 30\%$)* | `MISSING` / `FORMAT_ERROR` | `TSV == XLSX` |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`khanh`** | `CV04_VPO_01` (`94` tr Khánh + `13` pilot) | `107` | `405` | `7` | `331` | `5.43%` (`22` cảnh báo) | `0` / `0` | Khớp 100% |
| **`khanh`** | `CV04_VPO_02` (`103` tr Khánh + `7` pilot) | `110` | `535` | `42` | `353` | `4.11%` (`22` cảnh báo) | `0` / `0` | Khớp 100% |
| **`khanh`** | `CV04_VPO_03` (`199` tr Khánh + `9` pilot) | `208` | `856` | `76` | `453` | `10.40%` (`89` cảnh báo) | `0` / `0` | Khớp 100% |
| **`khanh`** | **Tổng nhánh `khanh`** | **`425`** | **`1.796`** | **`125`** | **`1.137`** | **`7.41%` (`133/1.796`)** | **`0` / `0`** | **100%** |
| **`kin`** | `CV04_VPO_01` (`92` tr Kin + `8` pilot) | `100` | `359` | `6` | `280` | `0.28%` (`1` cảnh báo) | `0` / `0` | Khớp 100% |
| **`kin`** | `CV04_VPO_02` (`103` tr Kin + `7` pilot) | `110` | `499` | `36` | `297` | `3.41%` (`17` cảnh báo) | `0` / `0` | Khớp 100% |
| **`kin`** | `CV04_VPO_03` (`198` tr Kin + `9` pilot) | `207` | `1.137` | `81` | `438` | `8.71%` (`99` cảnh báo) | `0` / `0` | Khớp 100% |
| **`kin`** | **Tổng nhánh `kin`** | **`417`** | **`1.995`** | **`123`** | **`1.015`** | **`5.86%` (`117/1.995`)** | **`0` / `0`** | **100%** |

---

## 3. Cấu Trúc Thư Mục Hiện Tại Của Mã Nguồn & Dữ Liệu

```text
Project0_Zh-Vi-Corpus-Building/
├── .gitignore                        # Bỏ qua raw_data/, staging/, .venv/, và ảnh PNG bulk trong 01_nguon/
├── main.py                           # CLI trung tâm (extract, stage, ocr, align, run, validate, web)
├── requirements.txt                  # PyMuPDF, openpyxl, Pillow, streamlit (+ ghi chú gói GPU/neural)
├── README.md
├── config/
│   ├── book_manifest.json            # Ánh xạ VPO_01/02/03, công thức lệch trang, phạm vi hợp lệ & loại trừ
│   └── member_splits.json            # Bảng chia 1.583 trang cho 4 thành viên (khoa, hieu, khanh, kin)
├── raw_data/                         # (git-ignored) 3 file PDF gốc, Thông tin dữ liệu.png, Thiền Tông Chỉ Nam Tự.txt
├── CV04_VPO_01/                      # Hồ sơ cuốn 1: Hán Văn Tinh Túy
│   ├── 01_nguon/                     # Ảnh PNG 300 DPI theo số trang PDF (0007.png, 0008.png...)
│   ├── 02_ocr_tho/                   # han/*.json, viet/*.json, ocr_results.jsonl, ocr_run_summary.json
│   ├── 03_text_sach/                 # han.txt, viet.txt (UTF-8 NFC)
│   ├── 04_dong_hang/                 # VPO_01_parallel.tsv, VPO_01_parallel.xlsx, qa_report.json, word_coverage_report.json
│   └── README.md
├── CV04_VPO_02/                      # Hồ sơ cuốn 2: Thể loại từ VN thời trung đại (Phần Ba)
│   └── ...                           # (tương tự: 01_nguon/, 02_ocr_tho/, 03_text_sach/, 04_dong_hang/, README.md)
├── CV04_VPO_03/                      # Hồ sơ cuốn 3: Thơ văn Lý – Trần (Tập II – Quyển Thượng)
│   ├── 01_nguon/                     # Ảnh PNG 300 DPI + bai_03_thien_tong_chi_nam_tu_dich_nghia.txt (bù trang 25)
│   └── ...                           # (02_ocr_tho/, 03_text_sach/, 04_dong_hang/, README.md)
├── src/
│   ├── __init__.py
│   ├── pdf_extractor.py              # Trích xuất PDF -> PNG 300 DPI bằng PyMuPDF & đóng gói Kaggle (stage)
│   ├── ocr_engine.py                 # Pipeline OCR 2 luồng (PaddleOCR chinese_cht + VietOCR vgg_transformer) & phân tích bố cục
│   ├── ocr_disambiguator.py          # Khử nhầm nét chữ Hán (105 cụm tương tự, 24 chữ đa âm) + M.E.D. Levenshtein (S1 ∩ S2)
│   ├── text_cleaner.py               # Làm sạch UTF-8 NFC, lọc header/footer/chú thích, bảo toàn [MASK] & □
│   ├── phonetic_verifier.py          # Từ điển CORE_HAN_VIET_DICT (764 chữ Hán / 630 âm đọc) & phóng chiếu dấu câu
│   ├── work_segmenter.py             # Máy trạng thái phân đoạn tác phẩm & tiểu phẩm (WorkRecord, SubPoem) cho VPO_02/03
│   ├── aligner.py                    # DP Gale-Church + neo từ vựng/số đếm, dóng hàng Dịch thơ đối diện & 4 cột
│   ├── poetic_aligner.py             # Tiện ích nhận diện thể thơ & gom cặp Lục bát 6-8 (module mở rộng độc lập)
│   ├── semantic_scorer.py            # Điểm tương đồng ngữ nghĩa (hỗ trợ sentence-transformers hoặc offline anchors)
│   ├── word_aligner.py               # Đánh giá độ bao phủ Hán tự và điểm tin cậy dóng hàng ở mức từ
│   ├── exporter_and_qa.py            # Kiểm định QA 6 loại lỗi, xuất .tsv & .xlsx 2 sheet (thuần stdlib) + đối chiếu 100%
│   ├── workbench_editor.py           # Hàm edit/split/merge/delete/insert dòng & tái xuất bản đồng bộ TSV/XLSX/QA
│   ├── corpus_pipeline.py            # Điều phối dóng hàng 4 cột từ JSON OCR thật (lệnh `python main.py align`)
│   └── pipeline_runner.py            # Bộ chạy dữ liệu mẫu Pilot 32/8/15 dòng (lệnh `python main.py run`)
├── web_app/
│   └── app.py                        # Giao diện Streamlit CAT Workbench & Live Monitor tiến độ 4 thành viên
├── docs/
│   ├── 1_KIEM_KE_NGUON.md            # Báo cáo kiểm kê nguồn Bước 1 & Bước 2
│   ├── 2_THONG_KE_BO_SUNG.md         # Thống kê 4 bài khuyết gốc, 3 bài tàn khuyết & Phụ lục 3 (VPO_02)
│   ├── 3_PHAN_CONG_4_NGUOI.md        # Bảng phân chia 1.583 trang cho 4 thành viên & quy chuẩn 22/11
│   ├── Hướng dẫn dóng hàng Hán-Việt.pdf
│   ├── Hướng dẫn dóng hàng dịch âm.docx
│   └── reference/                    # Bộ mẫu tham khảo CV03_VPR_14 (01_nguon..04_dong_hang + README.md)
└── tests/
    └── test_suite.py                 # 8 unit & integration tests (unittest)
```

---

## 4. Tuân Thủ Quy Định Đề Bài & Phản Hồi Của Chị Lưu Như

Đối chiếu với [`docs/Hướng dẫn dóng hàng Hán-Việt.pdf`](docs/H%C6%B0%E1%BB%9Bng%20d%E1%BA%ABn%20d%C3%B3ng%20h%C3%A0ng%20H%C3%A1n-Vi%E1%BB%87t.pdf), [`docs/Hướng dẫn dóng hàng dịch âm.docx`](docs/H%C6%B0%E1%BB%9Bng%20d%E1%BA%ABn%20d%C3%B3ng%20h%C3%A0ng%20d%E1%BB%8Bch%20%C3%A2m.docx) và góp ý demo của chị **Lưu Như**:

1. **Định dạng 4 cột thống nhất & dòng tiêu đề riêng**:
   - Toàn bộ 3 bộ sách xuất cấu trúc **4 cột**: `Hán` – `Dịch âm` – `Dịch nghĩa` – `Dịch thơ`.
   - Trước nội dung chính mỗi bài thơ/văn/tiểu phẩm đều tách **1 dòng tiêu đề riêng** với các thành phần Hán, Dịch âm, Dịch nghĩa đặt đúng cột; tác phẩm nào khuyết cột (ví dụ *Thu dạ hoài ngâm* thiếu `Dịch nghĩa`, văn xuôi thiếu `Dịch thơ`) thì ô đó để chuỗi rỗng `""`.
   - File `.tsv` ghi UTF-8 phân tách bằng đúng 1 ký tự `\t`, **không có dòng tiêu đề cột**; file `.xlsx` có sheet `DONG_HANG` (hàng 1 là tiêu đề `Hán | Dịch âm | Dịch nghĩa | Dịch thơ`, từ hàng 2 khớp 100% với từng dòng `.tsv`, không gộp ô/công thức/cột STT) và sheet thống kê `THONG_KE`.
2. **Tổ chức `01_nguon/` & `03_text_sach/`**:
   - **Về `01_nguon/`**: Do cả 3 tài liệu đầu vào đều là sách song ngữ in chung Hán – Việt trong cùng file PDF (hoặc 2 trang đối diện ở `VPO_01`), ảnh trang scan 300 DPI được đánh số theo trang PDF (`0007.png`...) trực tiếp trong `01_nguon/`, sau đó tách hai bản Hán/Việt tại `02_ocr_tho/{han,viet}/`.
   - **Về `03_text_sach/{han,viet}.txt`**: Toàn bộ tác phẩm của mỗi cuốn được gộp chung vào một cặp file `han.txt` và `viet.txt` (UTF-8 NFC).
     - Khi chạy pipeline OCR thật (`python main.py align` qua `src/corpus_pipeline.py`), `han.txt` và `viet.txt` được xuất **đồng bộ 1-1 theo từng dòng** với `04_dong_hang/*_parallel.tsv` (mỗi bài mở đầu bằng dòng tiêu đề riêng, không chèn ký tự `=== ... ===`; `viet.txt` ưu tiên `Dịch nghĩa`, fallback sang `Dịch thơ` rồi `Dịch âm`).
     - Khi chạy bộ mẫu Pilot (`python main.py run` qua `src/pipeline_runner.py`), các bài được ngăn cách tường minh bằng dòng `=== Tiêu đề bài ===`.
3. **Bảo toàn chữ mờ/khuyết (`[MASK]` / `□`)**:
   - Các module `text_cleaner.py`, `phonetic_verifier.py`, `aligner.py` và `exporter_and_qa.py` đều hỗ trợ giữ nguyên token `[MASK]` và ký hiệu ô vuông khuyết chữ `□`/`■`.
   - Lưu ý: trong JSON OCR thô hiện tại từ PaddleOCR, chữ khắc khuyết thường được nhận dạng thành `□` hoặc `口` (ví dụ trong `VPO_03`), cần rà soát đổi sang `[MASK]` trong bước hậu kiểm cuối trước khi nộp bài.
4. **Hành động còn lại trước hạn nộp `30/11` (Hợp nhất toàn nhóm CV04)**:
   - **Gộp 4 thành viên (`>= 8.000` cặp)**: Thu thập `02_ocr_tho/{han,viet}/*.json` từ đủ 4 nhánh (`khoa`, `hieu`, `khanh`, `kin`) vào chung bộ `CV04_VPO_01..03/` và chạy `python main.py align --book ALL` để nối liền các bài ở ranh giới chia shard và đạt tổng $\ge 8.000$ cặp hợp lệ toàn nhóm *(hiện từng nhánh riêng lẻ như `khanh` đạt `1.796` cặp và `kin` đạt `1.995` cặp do mật độ câu không đều giữa các phần sách, trong khi `khoa` đạt `2.488` cặp)*.
   - **Hậu kiểm & Báo cáo cuối (Mục 8 & Mục 9)**: Rà soát các dòng cảnh báo QA (`OMISSION`, `ADDITION`, `NUMBER_MISMATCH`), chuẩn hóa `[MASK]`, cập nhật lại số liệu tổng hợp toàn nhóm vào `CV04_VPO_01..03/README.md`, lập báo cáo hậu kiểm tổng kết nhóm (hiện chưa tạo file báo cáo tổng kết cuối trong `docs/`), và dọn sạch file tạm trước khi đóng gói.

---

## 5. Giải Trình 5 Tiêu Chí Phương Pháp Đề Xuất (Mục 9 Hướng Dẫn)

1. **Lý do lựa chọn**: Kết hợp `PyMuPDF` (trích xuất 300 DPI đa nền tảng trên Windows), `PaddleOCR chinese_cht` + `VietOCR vgg_transformer` (tối ưu riêng cho chữ Hán phồn thể và tiếng Việt có dấu), thuật toán khử nhầm nét Hán dựa trên `Phiên âm` (`M.E.D. Levenshtein` $S_1 \cap S_2$ + 105 cụm tương tự) và Quy hoạch động Gale-Church + neo từ vựng/số đếm để đạt độ chính xác cao khi dóng hàng 4 cột mà không phụ thuộc API trả phí.
2. **Dữ liệu đầu vào & đầu ra**: Đầu vào là 3 bộ PDF scan gốc (`raw_data/*.pdf`) + bản dịch bổ sung trang 25 `VPO_03`; đầu ra là 3 thư mục chuẩn `CV04_VPO_01`, `CV04_VPO_02`, `CV04_VPO_03` gồm `01_nguon/*.png`, `02_ocr_tho/{han,viet}/*.json`, `03_text_sach/{han,viet}.txt`, `04_dong_hang/VPO_0*_parallel.{tsv,xlsx}` và `qa_report.json`.
3. **Cách kiểm chứng**: Đối soát tự động qua `validate_pairs` (6 nhóm cờ lỗi, tỷ lệ lỗi QA toàn nhánh hiện ở mức `5.86%–7.41%`, sâu dưới ngưỡng `<= 30%`), kiểm tra khớp 100% giữa `.tsv` và sheet `DONG_HANG` trong `.xlsx`, đánh giá độ phủ từ vựng (`word_aligner.py`), hậu kiểm trực quan qua Streamlit CAT Workbench và chạy bộ test `tests/test_suite.py` (`8/8` pass).
4. **Rủi ro & phương án dự phòng**: Rủi ro OCR nhầm nét Hán cổ, lẫn chú thích chân trang hoặc mất chữ ở trang scan mờ/trắng $\rightarrow$ khắc phục bằng cắt header 7%, lọc đường kẻ chân trang (`TLTVN`), khử nhầm nét theo `Phiên âm`, đánh dấu `[MASK]`, bổ sung văn bản trang 25 (`VPO_03`), và hỗ trợ sửa/ghép/xóa dòng thủ công trên `web_app/app.py`. Khi không có GPU cục bộ, có sẵn chế độ `--mock` và bộ đóng gói chạy Kaggle GPU (`stage`).
5. **Khả năng tái lập bởi người khác**: Toàn bộ cấu hình chia trang/sách nằm trong `config/`, pipeline chạy lại hoàn toàn bằng CLI `python main.py` (không yêu cầu thư viện `pandas`/`openpyxl` để xuất `.xlsx` nhờ bộ ghi OpenXML thuần chuẩn Python), có sẵn kiểm thử tự động trong `tests/test_suite.py`.

---

## 6. Hướng Dẫn Sử Dụng CLI & Kiểm Thử

```powershell
# 1. Trích xuất ảnh PNG 300 DPI từ PDF theo phân công thành viên (khoa, hieu, khanh, kin) hoặc dải trang
python main.py extract --member khanh --dpi 300
python main.py extract --book VPO_02 --pages 134-145 --dpi 300

# 2. Đóng gói ảnh + src/ + config/ vào staging/kaggle_<member> để chạy OCR GPU trên Kaggle
python main.py stage --member khanh --kaggle-user <kaggle_username>

# 3. Chạy OCR cục bộ (cần paddleocr/vietocr hoặc thêm --mock để chạy giả lập kiểm tra luồng)
python main.py ocr --book ALL --mock --max-pages 5

# 4. Dóng hàng 4 cột từ toàn bộ JSON OCR thật trong 02_ocr_tho/ (tạo 03_text_sach/ và 04_dong_hang/)
python main.py align --book ALL

# 5. Kiểm định chất lượng QA & đối chiếu TSV == XLSX trên CV04_VPO_01..03
python main.py validate

# 6. Chạy bộ kiểm thử tự động (8 unit & integration tests, chạy trong thư mục tạm cô lập)
python -m unittest discover -s tests -v

# 7. Mở giao diện Streamlit CAT Workbench (xem tiến độ, sửa/ghép/xóa dòng, đối soát ảnh gốc)
python main.py web
```

> **Cảnh báo về `python main.py run`**: Lệnh `python main.py run` chạy bộ dữ liệu mẫu Pilot cố định (`VPO_01/02/03_PILOT_BLOCKS`, `32/8/15` cặp) và sẽ **ghi đè** lên `03_text_sach/`, `04_dong_hang/` và `README.md` của cả 3 thư mục `CV04_VPO_01..03` nếu chạy trực tiếp trên thư mục gốc. Chỉ dùng `python main.py align --book ALL` khi làm việc với dữ liệu OCR thật.
