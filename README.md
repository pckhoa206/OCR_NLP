# Dóng Hàng Hán - Việt

Building a Chinese-Vietnamese Parallel Corpus on Vietnamese Literature (Poetry & Prose)

- **Mã đề tài**: `CV04`
- **Thành viên nhóm**:
  1. Trần Trung Hiếu *(Nhóm trưởng)*
  2. Lê Gia Khánh
  3. Phạm Chấn Khoa
  4. Cái Hoàng Bảo Kin
- **Giảng viên / Học viên cao học hướng dẫn**: Chị **Lưu Như**

---

## 1. Cấu trúc thư mục chuẩn chỉnh

```text
Lab2_DongHangHan-Viet/
├── config/
│   └── book_manifest.json          # Cấu hình ánh xạ VPO_01, VPO_02, VPO_03 & công thức lệch trang
├── raw_data/                       # Tư liệu PDF gốc & thông tin phân công của nhóm CV04
│   ├── Hán văn tinh tuý - Lãng Nhân.pdf
│   ├── Thể loại từ VN thời trung đại - Phạm Văn Ánh.pdf
│   ├── Thơ văn Lý-Trần tập 2 - Nguyễn Huệ Chi.pdf
│   └── thong_tin_du_lieu.png
├── CV04_VPO_01/                    # Deliverables cuốn 1: Hán Văn Tinh Túy (Lãng Nhân)
│   ├── 01_nguon/                   # Ảnh PNG 300 DPI trích xuất từ PDF
│   ├── 02_ocr_tho/{han,viet}/      # Kết quả OCR thô theo từng trang JSON + ocr_results.jsonl
│   ├── 03_text_sach/{han,viet}.txt # Văn bản sạch ngăn cách bằng === Tiêu đề bài ===
│   └── 04_dong_hang/               # VPO_01_parallel.tsv, VPO_01_parallel.xlsx, qa_report.json
├── CV04_VPO_02/                    # Deliverables cuốn 2: Thể loại từ VN thời trung đại (Phần Ba)
│   ├── 01_nguon/
│   ├── 02_ocr_tho/{han,viet}/
│   ├── 03_text_sach/{han,viet}.txt
│   └── 04_dong_hang/               # VPO_02_parallel.tsv, VPO_02_parallel.xlsx, qa_report.json
├── CV04_VPO_03/                    # Deliverables cuốn 3: Thơ văn Lý - Trần Tập II
│   ├── 01_nguon/                   # Kèm bai_03_thien_tong_chi_nam_tu_dich_nghia.txt (bù trang 25 trắng)
│   ├── 02_ocr_tho/{han,viet}/
│   ├── 03_text_sach/{han,viet}.txt
│   └── 04_dong_hang/               # VPO_03_parallel.tsv, VPO_03_parallel.xlsx, qa_report.json
├── src/                            # Mã nguồn lõi của Pipeline
│   ├── pdf_extractor.py            # Trích xuất ảnh trang PDF 300 DPI đa nền tảng bằng PyMuPDF
│   ├── ocr_engine.py               # Pipeline OCR 2 luồng & phân vùng bố cục
│   ├── ocr_disambiguator.py        # Hiệu chỉnh lỗi OCR chữ Hán dựa trên phiên âm Hán-Việt
│   ├── text_cleaner.py             # Làm sạch văn bản, chuẩn hóa NFC, bảo toàn [MASK]
│   ├── phonetic_verifier.py        # Từ điển phiên âm Hán-Việt 3.175 âm tiết & giải nhập nhằng đa âm
│   ├── semantic_scorer.py          # Chấm điểm tương đồng ngữ nghĩa Hán - Việt
│   ├── aligner.py                  # Thuật toán Quy hoạch động Gale-Church + Neo âm Hán-Việt
│   ├── poetic_aligner.py           # Dóng hàng thể thơ Lục bát & song thất lục bát
│   ├── word_aligner.py             # Dóng hàng mức từ (Word-level alignment)
│   ├── exporter_and_qa.py          # Xuất TSV & XLSX 2 sheet (DONG_HANG, THONG_KE) + Kiểm định QA
│   ├── workbench_editor.py         # Tiện ích chỉnh sửa dòng, ghép câu, xóa câu & tái xuất bản
│   └── pipeline_runner.py          # Điều phối chạy toàn bộ pipeline cho VPO_01, VPO_02, VPO_03
├── web_app/
│   └── app.py                      # Giao diện Streamlit CAT Workbench kiểm tra & hiệu đính trực quan
├── docs/
│   ├── 1_KIEM_KE_NGUON.md                          # Báo cáo Kiểm kê Bước 1 & Bước 2
│   ├── 2_THONG_KE_BO_SUNG.md                       # Báo cáo thống kê bài khuyết & phụ lục gửi chị Lưu Như
│   ├── 3_PHAN_CONG_4_NGUOI.md                      # Bảng phân công 1.583 trang cho 4 thành viên
│   ├── Hướng dẫn dóng hàng Hán-Việt.pdf            # Tài liệu quy chuẩn Đồ án Dóng hàng Hán–Việt (CV04)
│   ├── Hướng dẫn dóng hàng dịch âm.docx            # Quy chuẩn bổ sung của chị Lưu Như (4 cột, [MASK], tiêu đề)
│   ├── Lab 2. Dóng hàng Hán-Việt1.pdf              # Bản tải về của đề LabOCR.pdf trên LMS (đánh giá OPRB)
│   ├── OPRB_Qwen2_5_VL_3B_Test_Evaluation.ipynb    # Notebook Colab minh họa đánh giá Qwen2.5-VL-3B trên OPRB
│   ├── example/                                    # Tệp mẫu đối chiếu định dạng (example.tsv, example.xlsx)
│   └── reference/                                  # Tài liệu tham khảo mẫu cấu trúc bàn giao
├── tests/
│   └── test_suite.py               # Bộ kiểm thử tự động toàn diện (Unit & Integration Tests)
├── main.py                         # Điểm vào CLI trung tâm
└── requirements.txt
```

---

## 2. Yêu cầu Đồ án Dóng hàng Hán – Việt (`CV04`) & Checklist hoàn thiện

> [!NOTE]
> Trong `docs/` hiện có **hai tài liệu đề bài khác nhau**:
> 1. [`docs/Hướng dẫn dóng hàng Hán-Việt.pdf`](docs/H%C6%B0%E1%BB%9Bng%20d%E1%BA%ABn%20d%C3%B3ng%20h%C3%A0ng%20H%C3%A1n-Vi%E1%BB%87t.pdf) *(kèm [`docs/Hướng dẫn dóng hàng dịch âm.docx`](docs/H%C6%B0%E1%BB%9Bng%20d%E1%BA%ABn%20d%C3%B3ng%20h%C3%A0ng%20d%E1%BB%8Bch%20%C3%A2m.docx))* — **Đồ án Dóng hàng Hán–Việt (`CV04`)** làm theo nhóm với chị **Lưu Như** (code chính trong repo này).
> 2. [`docs/Lab 2. Dóng hàng Hán-Việt1.pdf`](docs/Lab%202.%20D%C3%B3ng%20h%C3%A0ng%20H%C3%A1n-Vi%E1%BB%87t1.pdf) *(tệp `LabOCR.pdf` trên LMS, hạn nộp gia hạn đến **`10/12/2026 23:59`**)* kèm [`docs/OPRB_Qwen2_5_VL_3B_Test_Evaluation.ipynb`](docs/OPRB_Qwen2_5_VL_3B_Test_Evaluation.ipynb) — **Bài thực hành / Đồ án đánh giá VLM & OCR nhẹ trên bộ ảnh che khuất OPRB** (chi tiết xem Mục 3 bên dưới).

Với **Đồ án Dóng hàng Hán–Việt (`CV04`)**, ngoài 3 thư mục dữ liệu **`CV04_VPO_01`**, **`CV04_VPO_02`**, **`CV04_VPO_03`**, gói nộp cuối cùng của cả nhóm phải đảm bảo đủ các hạng mục sau *(cần xác nhận lại với chị Lưu Như hạn chốt thu dữ liệu nhóm có khớp hạn LMS `10/12/2026` hay giữ mốc `30/11`)*:

### A. Chỉ tiêu khối lượng & Tiến độ 4 thành viên
* **Chỉ tiêu bắt buộc (tài liệu PDF Scan cần OCR)**: Tối thiểu **2.000 cặp hợp lệ / thành viên** $\rightarrow$ **$\ge 8.000$ cặp hợp lệ cho toàn nhóm 4 người**.
* **Trạng thái hiện tại theo nhánh**:
  * Nhánh `khanh` (**Lê Gia Khánh**, 396 trang + pilot): đã chạy xong GPU OCR & dóng hàng **1.796 cặp** (`VPO_01=405`, `VPO_02=535`, `VPO_03=856`).
  * Nhánh `kin` (**Cái Hoàng Bảo Kin**, 393 trang + pilot): đã chạy xong GPU OCR & dóng hàng **1.995 cặp** (`VPO_01=359`, `VPO_02=499`, `VPO_03=1.137`).
* **Cần gộp đủ 4 phần trước khi nộp**: Sau khi **Khoa** (`mac`), **Hiếu**, **Khánh** (`khanh`) và **Kin** (`kin`) hoàn tất OCR (`02_ocr_tho/{han,viet}/*.json`), cần gộp đủ toàn bộ **1.583 trang hợp lệ** (và trang bổ sung/pilot) vào chung 1 bộ theo chuẩn tên `CV04_VPO_01..03/04_dong_hang/VPO_01..03_parallel.{tsv,xlsx}`, rồi chạy lại `python main.py align --book ALL` để nối liền các bài bị cắt ngang ở ranh giới phân công.

### B. Cấu trúc bắt buộc bên trong mỗi thư mục `CV04_VPO_01`, `CV04_VPO_02`, `CV04_VPO_03`
* `01_nguon/`: Ảnh trang scan gốc 300 DPI (`.png`, đánh số cố định `0007.png`...; kèm `bai_03_thien_tong_chi_nam_tu_dich_nghia.txt` trong `CV04_VPO_03/01_nguon/`). *(Nếu tách riêng Hán/Việt thì chia `han/` và `viet/`; với sách song ngữ in chung trang, ghi chú rõ trong `README.md` từng thư mục).*
* `02_ocr_tho/`: Lưu nguyên trạng JSON OCR thô ban đầu (`han/` và `viet/`) để truy vết tọa độ từng trang.
* `03_text_sach/`: Văn bản sạch `han.txt` và `viet.txt` chuẩn `UTF-8 NFC`, các bài ngăn cách bằng dòng tiêu đề `=== Tiêu đề bài ===`.
* `04_dong_hang/`:
  * Nộp **đồng thời `.tsv` và `.xlsx`** (`<MA_TAC_PHAM>_parallel.tsv` và `<MA_TAC_PHAM>_parallel.xlsx`), nội dung 2 file phải **khớp nhau 100%**.
  * Cấu trúc **4 cột thống nhất**: `Hán` – `Dịch âm` – `Dịch nghĩa` – `Dịch thơ`, mỗi bài có **1 dòng tiêu đề riêng** trước nội dung chính; cột nào nguyên bản không có thì để ô trống `""`.
  * File Excel có sheet `DONG_HANG` (hàng 1 là tiêu đề, không gộp ô, không chèn dòng trống hay cột số thứ tự) và sheet thống kê `THONG_KE`, kèm `qa_report.json`.
* `README.md` trong từng thư mục (`CV04_VPO_01..03/README.md`): **Bắt buộc cập nhật lại số liệu thật** của cả nhóm sau khi hợp nhất (`tổng số cặp`, `tỷ lệ lỗi QA`, `độ phủ`, `độ tin cậy`), thay thế số liệu Pilot ban đầu (`32`, `8`, `15` cặp).

### C. Bộ Báo cáo, Kiểm kê & Hậu kiểm đi kèm (Mục 2, 4, 8, 9 của `Hướng dẫn dóng hàng Hán-Việt.pdf`)
* **Bảng kiểm kê nguồn & thống kê bổ sung**: [`docs/1_KIEM_KE_NGUON.md`](docs/1_KIEM_KE_NGUON.md) và [`docs/2_THONG_KE_BO_SUNG.md`](docs/2_THONG_KE_BO_SUNG.md).
* **Báo cáo tổng kết nhóm & tự kiểm tra chất lượng (Mục 8)**: Tổng hợp số lượng cặp, số dòng Hán/Việt, tỷ lệ lỗi QA tổng toàn nhóm đảm bảo **$\le 30\%$** *(mục tiêu nội bộ $\le 20\%$)*, kèm danh sách các dòng bị gắn cờ (`OMISSION`, `ADDITION`, `NUMBER_MISMATCH`, `MISSING`) đã được hậu kiểm / sửa tay qua Web App hoặc Excel.
* **Giải trình 5 tiêu chí phương pháp đề xuất (Mục 9)**: Nêu rõ *(1) Lý do lựa chọn công cụ/phương pháp, (2) Dữ liệu đầu vào & đầu ra, (3) Cách kiểm chứng, (4) Rủi ro & phương án dự phòng, (5) Khả năng tái lập bởi người khác*.

### D. Mã nguồn tái lập & Quy tắc vệ sinh gói nộp (Bước 3 & Mục 9.5)
* Đính kèm mã nguồn tái lập (`src/`, `config/`, `main.py`, `requirements.txt`, `web_app/`, `tests/`, `README.md`) hoặc dẫn link kho GitHub chính thức.
* Tuyệt đối **không chứa** mật khẩu, cookie, token/API key (`kaggle.json`, `.env`...).
* Không đặt tên file kiểu `final`, `final2`, `final_new` (dùng tên chuẩn theo quy định hoặc mã phiên bản/commit rõ ràng).
* Dọn sạch các thư mục tạm (`.venv/`, `staging/`, `__pycache__/`) trước khi đóng gói bàn giao.

---

## 3. Yêu cầu Bài tập / Đồ án `LabOCR` trên LMS (Hạn nộp: `10/12/2026 23:59`)

Theo tệp đề gốc từ LMS (lưu tại [`docs/Lab 2. Dóng hàng Hán-Việt1.pdf`](docs/Lab%202.%20D%C3%B3ng%20h%C3%A0ng%20H%C3%A1n-Vi%E1%BB%87t1.pdf) — tên gốc `LabOCR.pdf`, mở từ `16/11/2026`, tới hạn **`10/12/2026 23:59`**) và notebook mẫu [`docs/OPRB_Qwen2_5_VL_3B_Test_Evaluation.ipynb`](docs/OPRB_Qwen2_5_VL_3B_Test_Evaluation.ipynb), nội dung cần thực hiện và nộp gồm:

### A. Nhiệm vụ & Dữ liệu đánh giá (`OPRB`)
* **Mục tiêu**: Đánh giá độ chính xác nhận dạng văn bản và độ bền (robustness) của các mô hình **Vision-Language Models (VLMs)** nhẹ và mô hình **OCR** trên ảnh tài liệu bị che khuất (vết mực, nét gạch xóa, con dấu, bụi, dấu sửa bài).
* **Tập dữ liệu**: **OPRB (*Occluded Pages Restoration Benchmark*)** (`kpurkayastha/OPRB` trên Hugging Face).
* **Quy định tập kiểm thử**: Chỉ sử dụng **tập `test`** gồm **9.000 ảnh tài liệu**:
  * **6.000 ảnh** bị che khuất vùng chữ (`test/text/img/`).
  * **3.000 ảnh** bị che khuất vùng ngoài chữ (`test/nontext/img/`).
  * Các nhãn trong `test/*/gt/` chỉ được dùng để **tính điểm đánh giá**, không đưa vào mô hình; **không tải** `img_gt/` hay `annots/` và **nghiêm cấm huấn luyện / fine-tune** trên tập test OPRB.

### B. Mô hình & Chỉ số đánh giá bắt buộc
* **Số lượng mô hình**: Chọn và đánh giá **tối thiểu 05 mô hình nhẹ pretrained (zero-shot)** thuộc 2 nhóm **VLMs** và **OCR Models**.
* **Chỉ số bắt buộc**:
  1. `CER` (*Character Error Rate* — càng thấp càng tốt).
  2. `WER` (*Word Error Rate* — càng thấp càng tốt).
  3. `Precision`, `Recall`, `F1-score` (theo tập từ bag-of-words không xét thứ tự trong `token` ground-truth).
  4. `Inference Time` (thời gian suy luận trung bình cho 1 trang ảnh).

### C. Tác dụng của Notebook mẫu `OPRB_Qwen2_5_VL_3B_Test_Evaluation.ipynb`
* Đây là **notebook Colab minh họa mẫu** của giảng viên cho **1 trong 5 mô hình cần chạy**: **`Qwen/Qwen2.5-VL-3B-Instruct`** (lượng tử hóa 4-bit NF4, compute `float16`, zero-shot).
* Quy trình notebook thực hiện sẵn: tải `test/{text,nontext}/img.tar.gz` & `gt.tar.gz` $\rightarrow$ chạy OCR zero-shot trên GPU T4 $\rightarrow$ tính `cer`, `wer`, `token_precision/recall/f1`, `latency_sec`, gắn cờ `possibly_truncated` $\rightarrow$ xuất bảng CSV tổng hợp theo vùng (`category`), loại che khuất (`occlusion_type`) và mật độ che khuất (`occlusion_density`) $\rightarrow$ vẽ 2 biểu đồ lỗi (`cer_wer_by_category.png`, `wer_by_occlusion_type.png`) $\rightarrow$ đóng gói thành `oprb_qwen_results.zip`.
* **Lưu ý khi dùng để nộp bài**:
  * Notebook mặc định đặt `MAX_SAMPLES_PER_CATEGORY = 5` (chỉ để chạy thử nhanh **5 ảnh/nhóm**). Khi chạy đánh giá chính thức phải đổi thành `MAX_SAMPLES_PER_CATEGORY = None` để chấm đủ **9.000 ảnh test**.
  * Cần bổ sung chạy và đối chiếu thêm **ít nhất 04 mô hình VLM / OCR nhẹ khác** (ngoài `Qwen2.5-VL-3B-Instruct`) để đáp ứng điều kiện tối thiểu **05 mô hình** của đề bài.

### D. Sản phẩm cần nộp cho bài `LabOCR`
* **Tệp nén kết quả thực nghiệm** (ví dụ `oprb_qwen_results.zip` và kết quả các mô hình còn lại để đối chiếu).
* **Báo cáo ngắn định dạng PDF (`< 4 trang A4`)** gồm đúng **5 phần**:
  1. `Introduction`
  2. `Dataset Statistics`
  3. `Model Descriptions`
  4. `Experimental Results` (bảng định lượng $\ge 5$ mô hình, so sánh `text` vs `nontext`, phân tích ảnh hưởng từng loại/mật độ che khuất, **$\ge 3$ ví dụ định tính** đúng & sai từ `per_image_results.csv`, phân tích đánh đổi độ chính xác – kích thước mô hình – thời gian suy luận)
  5. `Conclusion`

---

## 4. Tuân thủ 100% Quy định của Đề bài Dóng hàng Hán–Việt & Chị Lưu Như

1. **Đúng mã nhóm và mã tác phẩm**: `CV04_VPO_01`, `CV04_VPO_02`, `CV04_VPO_03` với tệp đầu ra `VPO_01_parallel.{tsv,xlsx}`, `VPO_02_parallel.{tsv,xlsx}`, `VPO_03_parallel.{tsv,xlsx}`.
2. **Cấu trúc dóng hàng 4 cột chuẩn (`Hán - Dịch âm - Dịch nghĩa - Dịch thơ`)**:
   - Riêng bài cuối của `VPO_01` (*Thu dạ hoài ngâm*, `PDF 367–381`) chỉ có `Hán - Dịch âm - Dịch thơ`, cột `Dịch nghĩa` được để trống `""`.
   - Các tác phẩm văn xuôi không có bản dịch thơ (như *Thiền tông chỉ nam tự* ở `VPO_03`), cột `Dịch thơ` được để trống `""`.
3. **Bảo toàn ký hiệu `[MASK]` cho chữ Hán bị mờ/khuyết**:
   - Mọi vị trí chữ Hán bị mờ nặng hoặc tàn khuyết trong bản in (ví dụ `霸橋[MASK]詩` ở `VPO_02`) được giữ nguyên token `[MASK]` xuyên suốt khâu làm sạch, đếm số âm tiết Hán-Việt, dóng hàng và kiểm định QA.
4. **Ngăn cách tiêu đề bài trong `03_text_sach/`**:
   - Toàn bộ các bài thơ/văn nhỏ trong cùng một cuốn sách được gộp chung vào `03_text_sach/han.txt` và `03_text_sach/viet.txt`, ngăn cách bằng dòng tiêu đề `=== Tiêu đề bài ===`.
5. **Tương thích hoàn toàn với Windows**:
   - Thay thế hoàn toàn script Swift macOS bằng [`src/pdf_extractor.py`](src/pdf_extractor.py) sử dụng `PyMuPDF` (`fitz`) tốc độ cao ở chuẩn **300 DPI**.

---

## 5. Hướng dẫn sử dụng nhanh

### Chạy toàn bộ Pipeline Pilot / Hoặc Dóng hàng 4 cột từ JSON OCR thật
```powershell
# Chạy lại bước tách bài & dóng hàng 4 cột từ toàn bộ JSON trong 02_ocr_tho/
python main.py align --book ALL

# Chạy Pipeline mẫu Pilot (--dry-run)
python main.py run
```

### Trích xuất trang PDF ra ảnh PNG 300 DPI (trên Windows)
```powershell
# Trích xuất theo phần phân công từng thành viên (khoa, hieu, khanh, kin)
python main.py extract --member khanh --dpi 300

# Trích xuất dải trang bất kỳ (ví dụ trang PDF 134 đến 145 của VPO_02)
python main.py extract --book VPO_02 --pages 134-145 --dpi 300
```

### Kiểm tra chất lượng dữ liệu (Headless QA Validation)
```powershell
python main.py validate
```

### Chạy bộ Kiểm thử Tự động (Unit & Integration Tests)
```powershell
python -m unittest discover -s tests -v
```

### Mở Giao diện Hiệu đính Trực quan (Streamlit CAT Workbench)
```powershell
python main.py web
```

