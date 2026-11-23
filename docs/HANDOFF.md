# HANDOFF — Biên bản Bàn giao Trạng thái Liên-Agent & Liên-Phiên

- **Thời điểm cập nhật (Snapshot Timestamp)**: `2026-11-22 09:48:00 UTC`
- **Ghi chú bàn giao mới nhất**: T23 completed: unified 4-col schema, work titles, Dich tho, 2,488 Khoa pairs (error_rate 2.91%-6.91%, MISSING=0), 100% test suite pass, Mục 8/9 docs updated.
- **Bản đồ phụ thuộc nhiệm vụ**: [`docs/WAYFINDER.md`](./WAYFINDER.md)
- **Kiểm kê nguồn chi tiết**: [`docs/BANG_KIEM_KE_NGUON.md`](./BANG_KIEM_KE_NGUON.md)
- **Báo cáo tổng kết nhóm (Mục 9)**: [`docs/BAO_CAO_TONG_KET_NHOM.md`](./BAO_CAO_TONG_KET_NHOM.md)
- **Báo cáo chi tiết quy trình, lỗi & kết quả (`khoa`)**: [`docs/BAO_CAO_CHI_TIET_QUY_TRINH_VA_KET_QUA_KHOA.md`](./BAO_CAO_CHI_TIET_QUY_TRINH_VA_KET_QUA_KHOA.md)
- **Danh sách hậu kiểm lỗi (Mục 8)**: [`docs/DANH_SACH_HAU_KIEM_LOI.md`](./DANH_SACH_HAU_KIEM_LOI.md)

---

## 1. Tiến độ Ticket theo DAG (`config/tickets.json`)

- **Đã hoàn tất (`DONE`)**: `21/21` (`T01`, `T02`, `T03`, `T04`, `T05`, `T06`, `T09`, `T10`, `T11`, `T12`, `T13`, `T14`, `T15`, `T16`, `T17`, `T18`, `T19`, `T20`, `T21`, `T22`, `T23`)
- **Sẵn sàng thực thi ngay (`READY`)**: `0` (Không có)
- **Đang chờ phụ thuộc (`BLOCKED`)**: `0` (Không có)

---

## 2. Trạng thái Sản phẩm Thực tế trên Đĩa

### 2.1. Bộ Pilot Chuẩn 4 Cột (`deliverables/`) & Demo Giảng viên (`demo_giang_vien/`)

| Mã sách | Thư mục đích | Số ảnh 300 DPI (`01_nguon`) | Lược đồ cột | Số cặp (`04_dong_hang`) | Tỷ lệ lỗi QA | `.tsv` / `.xlsx` (`TSV == XLSX`) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `HVTT` | `deliverables/HVTT_HanVanTinhTuy` | `375` (`0007..0381`) | 4 cột + tiêu đề | `28` | `0.00%` | `OK` (`100%`) |
| `TVLT2` | `deliverables/TVLT2_ThoVanLyTran2` | `795` (`0017..0861`) | 4 cột + tiêu đề | `15` | `0.00%` | `OK` (`100%`) |
| `TLTVN` | `deliverables/TLTVN_TheLoaiTuVN` | `414` (`0134..0547`) | 4 cột + tiêu đề | `5` | `0.00%` | `OK` (`100%`) |

- **Demo Giảng viên (`demo_giang_vien/`)**: `HVTT_demo` (`12` dòng, `0.00%`), `TVLT2_demo` (`12` dòng, `0.00%`), `TLTVN_demo` (`5` dòng, `0.00%`), kèm ảnh `01_nguon_demo/` và báo cáo [`BAO_CAO_DEMO_GIANG_VIEN.md`](../demo_giang_vien/BAO_CAO_DEMO_GIANG_VIEN.md).

### 2.2. Kết quả Chạy thật Kaggle GPU v4 — Shard Khoa (`outputs/khoa/`, 397+1 = 398 trang)

| Mã sách | Trang OCR thật | Cấu trúc 4 cột | Tổng số cặp | Dòng tiêu đề | Dòng có `Dịch thơ` | `MISSING` | Lỗi QA (Số cặp / Tỷ lệ) | `TSV == XLSX` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `HVTT` | `95` (`0007..0101`) | `Hán \| Dịch âm \| Dịch nghĩa \| Dịch thơ` | **`275`** | `10` | `256` | `0` | `8` (**`2.91%`**) | `OK` (`100%`) |
| `TVLT2` | `199` (`0017..0216`) | `Hán \| Dịch âm \| Dịch nghĩa \| Dịch thơ` | **`1,693`** | `58` | `222` | `0` | `117` (**`6.91%`**) | `OK` (`100%`) |
| `TLTVN` | `104` (`0134..0237`) | `Hán \| Dịch âm \| Dịch nghĩa \| Dịch thơ` | **`520`** | `50` | `377` | `0` | `16` (**`3.08%`**) | `OK` (`100%`) |
| **Tổng** | **`398` trang** | **Thống nhất 4 cột** | **`2,488`** | **`118`** | **`855`** | **`0`** | **`141` (`5.67%`)** | **`100%`** |

- Đầy đủ cây thư mục `01_nguon/{han,viet}`, `02_ocr_tho/{han,viet}`, `03_text_sach/{han.txt,viet.txt}`, `04_dong_hang/<book_dir>_parallel.{tsv,xlsx}` tại `outputs/khoa/deliverables/*`; không còn tệp ngắn cũ (`HVTT_parallel.*`, `TVLT2_parallel.*`, `TLTVN_parallel.*`); không có tệp `.cookie`/token/credential.

---

## 3. Quyết định Kiến trúc & Dị biệt Nguồn (Memory Bank Hiện hành)

1. **Lược đồ thống nhất 4 cột & Quy cách bảo toàn**:
   - Toàn bộ cả 3 bộ sách xuất chuẩn **4 cột** `Hán | Dịch âm | Dịch nghĩa | Dịch thơ` với tên tệp chuẩn `<MA_DE_TAI>_<MA_TAC_PHAM>_parallel.{tsv,xlsx}` (2 sheet `DONG_HANG` + `THONG_KE`), giữ nguyên chữ cổ/dị thể, chữ khuyết `□`, năm/niên hiệu/con số, chuẩn hóa `UTF-8 NFC`.
   - Mỗi tác phẩm (và tiểu phẩm liên hoàn trong `TLTVN` / `TVLT2`) có **dòng tiêu đề tách riêng** (`is_title`), không trộn vào câu mở đầu.
2. **Hán Văn Tinh Túy (`HVTT`)**:
   - Phạm vi hợp lệ mở rộng từ `PDF 7..381` (`375` trang): trang lẻ có tiêu đề (`0007`, `0017`, ..., `0367`) tách dòng tiêu đề; trang lẻ đối diện bài thơ/văn vần trích `Dịch thơ` (`odd_page_dich_tho`) và dóng theo trục $Y$ (`align_hvtt_facing_dich_tho`); trang chẵn ghép 3 tầng xen kẽ (`interlinear_triplets`) và gộp `Phiên âm` xuống dòng theo dải dọc.
   - Bài *Thạch Hào lại* (`PDF 100`) và bài cuối *Thu dạ hoài ngâm* (`PDF 367–381`) chỉ có `Hán – Dịch âm – Dịch thơ` $\rightarrow$ giữ đủ 4 cột và để trống `Dịch nghĩa = ""`.
   - Dòng chữ Hán in rời không dấu câu đi qua `src/ocr_disambiguator.py` (105+ cụm) và `src/phonetic_verifier.py::project_punctuation_from_phien_am` để chiếu dấu câu từ `Phiên âm`.
3. **Thơ văn Lý Trần — Tập II, Quyển Thượng (`TVLT2`)**:
   - Công thức lệch trang phần nội dung: `book_page = pdf_page + 2` (`PDF >= 7`).
   - **Trang PDF 25 bị trắng** $\rightarrow$ bài số 3 (*Thiền tông chỉ nam tự*, `PDF 22–29`) được tự động bổ sung bản dịch nghĩa từ tệp [`bai_03_thien_tong_chi_nam_tu_dich_nghia.txt`](../deliverables/TVLT2_ThoVanLyTran2/01_nguon/bai_03_thien_tong_chi_nam_tu_dich_nghia.txt) do Giảng viên cung cấp (`Dịch thơ = ""`).
   - Loại trừ 4 tác phẩm **Chữ Nôm** (`PDF 493..525`, `688..703`, `862..873`).
   - Máy trạng thái `src/work_segmenter.py` tách 58 tác phẩm (gồm *Niêm tụng kệ* 43 tiết và *Phổ thuyết tứ sơn* 5 bài kệ), tách `DỊCH THƠ` khỏi điểm dừng `KHẢO ĐÍNH` / `CHÚ THÍCH`, và xử lý ký hiệu chú thích khảo dị `1*`, `2*`.
4. **Thể loại từ Việt Nam thời trung đại (`TLTVN`)**:
   - Lớp text ẩn bị hỏng chữ Hán $\rightarrow$ OCR lại từ ảnh PNG 300 DPI (cắt 7% running header + phát hiện đường kẻ chân trang `detect_footnote_separator`).
   - Chỉ dóng hàng **Phần Ba** (`PDF 134–547` / Sách `127–540`, `pdf_page = book_page + 7`), đưa phần *Dịch theo nguyên điệu* vào cột `Dịch thơ`; thống kê bài khuyết gốc & Phụ lục 3 lưu tại [`docs/THONG_KE_BO_SUNG_GIANG_VIEN.md`](./THONG_KE_BO_SUNG_GIANG_VIEN.md).

---

## 4. Lệnh Kiểm tra & Hậu kiểm Tiếp theo

```bash
# 1. Kiểm thử toàn bộ hệ thống (87/87 tests PASS)
/Users/khoa/study/nam_3_ky_1/nlp/LAB/lab_gki/.venv/bin/pytest tests/ -v

# 2. Chạy cổng đánh giá Evaluator-Optimizer
python3 /Users/khoa/.gemini/config/skills/subagent-plan-reviewer/scripts/review_evaluator.py \
  --spec docs/BANG_KIEM_KE_NGUON.md \
  --proposal-file docs/HANDOFF.md \
  --workspace /Users/khoa/study/nam_3_ky_1/nlp/LAB/lab_gki

# 3. Mở CAT Workbench để hậu kiểm 141 dòng gắn cờ theo docs/DANH_SACH_HAU_KIEM_LOI.md
streamlit run web_app/app.py
```
