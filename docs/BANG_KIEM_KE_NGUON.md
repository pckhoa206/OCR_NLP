# BẢNG KIỂM KÊ NGUỒN DỮ LIỆU SONG NGỮ HÁN – VIỆT (NHÓM CV04 — BƯỚC 1 & BƯỚC 2)

Tài liệu này thực hiện **Bước 1 (Nhận đề tài và xác nhận phạm vi)** và **Bước 2 (Kiểm kê nguồn & Ánh xạ phần/trang)** theo đúng quy định tại `Lab 2. Dóng hàng Hán-Việt.pdf` và hướng dẫn của chị **Lưu Như** cho nhóm **`CV04`** (Trần Trung Hiếu, Lê Gia Khánh, Phạm Chấn Khoa, Cái Hoàng Bảo Kin).

---

## 1. Xác nhận đề tài và phạm vi tổng thể (Bước 1)

Nhóm `CV04` phụ trách xử lý **03 nguồn tư liệu PDF Scan** chứa văn bản song ngữ Hán – Việt theo bảng phân công `CV04_Trần Trung Hiếu.xlsx` (`raw_data/thong_tin_du_lieu.png`):

1. **`VPO_01` (`CV04_VPO_01`)** — *Hán Văn Tinh Túy* (Lãng Nhân Phùng Tất Đắc biên dịch).
2. **`VPO_02` (`CV04_VPO_02`)** — *Thể loại từ VN thời trung đại* (Phạm Văn Ánh / Nguyễn Xuân Diện – Nguyễn Quảng Tuân biên khảo và tuyển dịch).
3. **`VPO_03` (`CV04_VPO_03`)** — *Thơ văn Lý – Trần 2* (Nguyễn Huệ Chi chủ biên, Viện Văn học).

### Quy chuẩn kỹ thuật theo hướng dẫn của Giảng viên & Chị Lưu Như
- **Chỉ tiêu số lượng**: Tối thiểu **8.000 cặp câu** cho toàn nhóm 4 thành viên (tương đương tối thiểu **2.000 cặp câu/thành viên**).
- **Cấu trúc dóng hàng 4 cột**: Đối với các tác phẩm có bản chữ Hán, dịch âm, dịch nghĩa và dịch thơ, xuất đủ 4 cột theo cấu trúc: **`Hán` – `Dịch âm` – `Dịch nghĩa` – `Dịch thơ`**.
  - Riêng bài cuối của `VPO_01` (*Thu dạ hoài ngâm*, `PDF 367–381`) chỉ có `Hán - Dịch âm - Dịch thơ`, cột **`Dịch nghĩa` để trống (`""`)**.
  - Các bài văn xuôi/tựa không có bản dịch thơ (ví dụ *Thiền tông chỉ nam tự* ở `VPO_03`), cột **`Dịch thơ` để trống (`""`)**.
- **Đánh dấu chữ Hán bị mờ/khuyết**: Với những trang/đoạn bị hư hỏng hoặc mờ nặng, không đọc được chữ Hán, đánh dấu chữ khuyết là **`[MASK]`** vào dữ liệu dóng hàng.
- **Tổ chức thư mục `03_text_sach`**: Mỗi cuốn sách có 1 mã đề tài (`VPO_01`, `VPO_02`, `VPO_03`), thư mục `03_text_sach` chứa `han.txt` và `viet.txt` đã làm sạch của từng cuốn; các bài thơ/văn nhỏ bên trong được ngăn cách rõ ràng bằng tiêu đề `=== Tiêu đề bài ===` (không tạo thư mục riêng cho từng bài nhỏ).

---

## 2. Bảng kiểm kê nguồn chi tiết (Bước 2)

| Trường | Tài liệu 1 (`VPO_01`) | Tài liệu 2 (`VPO_02`) | Tài liệu 3 (`VPO_03`) |
| :--- | :--- | :--- | :--- |
| **Mã tác phẩm / Thư mục** | `VPO_01` (`CV04_VPO_01`) | `VPO_02` (`CV04_VPO_02`) | `VPO_03` (`CV04_VPO_03`) |
| **Tên tài liệu** | *Hán Văn Tinh Túy* (Lãng Nhân Phùng Tất Đắc) | *Thể loại từ VN thời trung đại* (Phạm Văn Ánh / Nguyễn Xuân Diện – Nguyễn Quảng Tuân) | *Thơ văn Lý – Trần (Tập II – Quyển Thượng)* (Nguyễn Huệ Chi chủ biên) |
| **Tệp gốc trong `raw_data/`** | `raw_data/Hán văn tinh tuý - Lãng Nhân.pdf` | `raw_data/Thể loại từ VN thời trung đại - Phạm Văn Ánh.pdf` | `raw_data/Thơ văn Lý-Trần tập 2 - Nguyễn Huệ Chi.pdf` |
| **Tổng số trang PDF** | **386 trang** | **645 trang** | **965 trang** |
| **Phạm vi xử lý hợp lệ** | Các trang sách chẵn `2..360` (`PDF 8..366` chẵn) + bài cuối `361..375` (`PDF 367..381`, để trống cột Dịch nghĩa) | **Phần Ba: Tuyển tập từ Việt Nam thời trung đại** tại trang sách `127..540` (`PDF 134..547`, 414 trang) | Thơ văn chữ Hán tại trang sách `19..863` (`PDF 17..861`, 795 trang hợp lệ sau khi loại 4 bài Chữ Nôm); trang `PDF 25` bị trắng được bổ sung từ file Drive của chị Như |
| **Công thức lệch trang** | `pdf_page = book_page + 6` | `pdf_page = book_page + 7` | `book_page = pdf_page + 2` (`pdf_page >= 7`) |
| **Mẫu Pilot (`01_nguon/`)** | `PDF [8, 10, 12, 50, 312, 326, 368, 369]` | `PDF [134, 135, 136, 137, 200, 300]` | `PDF [19, 20, 22, 23, 24, 25, 26, 38, 40, 42]` + `bai_03_thien_tong_chi_nam_tu_dich_nghia.txt` |

---

## 3. Quy tắc tổ chức thư mục bàn giao chuẩn (`Lab 2. Dóng hàng Hán-Việt.pdf` Mục 2)

```text
CV04_VPO_01/
├── 01_nguon/                  # Ảnh trang sách PNG 300 DPI (0008.png, 0010.png, ...)
├── 02_ocr_tho/
│   ├── han/                   # JSON OCR chữ Hán theo từng trang
│   ├── viet/                  # JSON OCR tiếng Việt theo từng trang
│   └── ocr_results.jsonl      # Log OCR tổng hợp
├── 03_text_sach/
│   ├── han.txt                # Văn bản chữ Hán đã làm sạch (ngăn cách bằng === Tiêu đề ===)
│   └── viet.txt               # Văn bản tiếng Việt đã làm sạch (ngăn cách bằng === Tiêu đề ===)
└── 04_dong_hang/
    ├── VPO_01_parallel.tsv    # File TSV 4 cột (Hán - Dịch âm - Dịch nghĩa - Dịch thơ)
    ├── VPO_01_parallel.xlsx   # File Excel gồm 2 sheet: DONG_HANG và THONG_KE
    └── qa_report.json         # Báo cáo kiểm định chất lượng tự động (Error Rate <= 30%)
```

*(Tương tự cho `CV04_VPO_02/` và `CV04_VPO_03/`).*

