# Xây dựng Ngữ liệu Song ngữ Hán – Việt trên Văn học Việt Nam (Nhóm `CV04`)

Đồ án giữa kỳ môn **Xử lý Ngôn ngữ Tự nhiên (NLP)**: *Building a Chinese-Vietnamese Parallel Corpus on Vietnamese Literature (Poetry & Prose)*.

- **Mã nhóm**: `CV04`
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
│   ├── ocr_engine.py               # Pipeline OCR 2 luồng (PP-OCRv5 Hán + VietOCR Quốc ngữ)
│   ├── layout_analyzer.py          # Phân vùng bố cục trang sách & lọc trang trắng/Chữ Nôm
│   ├── text_cleaner.py             # Làm sạch văn bản, chuẩn hóa NFC, bảo toàn [MASK]
│   ├── phonetic_verifier.py        # Từ điển phiên âm Hán-Việt 3.175 âm tiết & giải nhập nhằng đa âm
│   ├── semantic_scorer.py          # Chấm điểm tương đồng ngữ nghĩa Hán - Việt
│   ├── aligner.py                  # Thuật toán Quy hoạch động Gale-Church + Neo âm운 Hán-Việt
│   ├── word_aligner.py             # Dóng hàng mức từ (Word-level alignment)
│   ├── exporter_and_qa.py          # Xuất TSV & XLSX 2 sheet (DONG_HANG, THONG_KE) + Kiểm định QA
│   ├── workbench_editor.py         # Tiện ích chỉnh sửa dòng, ghép câu, xóa câu & tái xuất bản
│   └── pipeline_runner.py          # Điều phối chạy toàn bộ pipeline cho VPO_01, VPO_02, VPO_03
├── web_app/
│   └── app.py                      # Giao diện Streamlit CAT Workbench kiểm tra & hiệu đính trực quan
├── docs/
│   ├── BANG_KIEM_KE_NGUON.md       # Báo cáo Kiểm kê Bước 1 & Bước 2
│   └── THONG_KE_BO_SUNG_GIANG_VIEN.md # Báo cáo thống kê bài khuyết & phụ lục gửi chị Lưu Như
├── tests/
│   └── test_suite.py               # Bộ kiểm thử tự động toàn diện (Unit & Integration Tests)
├── main.py                         # Điểm vào CLI trung tâm
└── requirements.txt
```

---

## 2. Tuân thủ 100% Quy định của Đề bài & Chị Lưu Như

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

## 3. Hướng dẫn sử dụng nhanh

### Chạy toàn bộ Pipeline (Làm sạch + Dóng hàng 4 cột + Xuất TSV/XLSX + QA)
```powershell
python main.py run
```

### Trích xuất trang PDF ra ảnh PNG 300 DPI (trên Windows)
```powershell
# Trích xuất các trang mẫu Pilot của VPO_01
python main.py extract --book VPO_01 --pages pilot

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

