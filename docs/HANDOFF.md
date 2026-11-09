# HANDOFF — Biên bản Bàn giao Trạng thái Liên-Agent & Liên-Phiên

- **Thời điểm cập nhật (Snapshot Timestamp)**: `2026-11-08 02:19:46 UTC`
- **Ghi chú bàn giao mới nhất**: Hoàn thành Ticket T18: Xây dựng CAT Workbench Interactive Editor (edit/split/merge/insert/delete), Báo cáo Chẩn đoán Dịch thuật (BAO_CAO_CHAN_DOAN_CHAT_LUONG.md), và tích hợp chỉnh sửa trực tiếp trên Web App.
- **Bản đồ phụ thuộc nhiệm vụ**: [`docs/WAYFINDER.md`](./WAYFINDER.md)
- **Kiểm kê nguồn chi tiết**: [`docs/BANG_KIEM_KE_NGUON.md`](./BANG_KIEM_KE_NGUON.md)

---

## 1. Tiến độ Ticket theo DAG (`config/tickets.json`)

- **Đã hoàn tất (`DONE`)**: `16/16` (`T01`, `T02`, `T03`, `T04`, `T05`, `T06`, `T09`, `T10`, `T11`, `T12`, `T13`, `T14`, `T15`, `T16`, `T17`, `T18`)
- **Sẵn sàng thực thi ngay (`READY`)**: `0` (Không có)
- **Đang chờ phụ thuộc (`BLOCKED`)**: `0` (Không có)

---

## 2. Trạng thái Sản phẩm Thực tế trên Đĩa (`deliverables/`)

| Mã sách | Thư mục đích | Số ảnh 300 DPI (`01_nguon`) | Số cặp câu dóng hàng (`04_dong_hang`) | Tệp `.tsv` | Tệp `.xlsx` |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `HVTT` | `deliverables/HVTT_HanVanTinhTuy` | `374` | `25` | `OK` | `OK` |
| `TVLT2` | `deliverables/TVLT2_ThoVanLyTran2` | `795` | `11` | `OK` | `OK` |
| `TLTVN` | `deliverables/TLTVN_TheLoaiTuVN` | `414` | `3` | `OK` | `OK` |

---

## 3. Quyết định Kiến trúc & Dị biệt Nguồn Bắt buộc Ghi nhớ (Memory Bank)

1. **Hán Văn Tinh Túy (`HVTT`)**:
   - Chỉ lấy **trang sách chẵn 2–360** (`PDF 8–366`, 180 trang) có đủ 3 dòng gióng sẵn (`Chữ Hán` + `Phiên âm` + `Dịch nghĩa`).
   - Bài thơ cuối (*Mộc Lan từ*, trang sách 361–375 / `PDF 367–381`) chỉ có dịch thơ lục bát ở trang lẻ, thiếu dịch nghĩa xuôi $ightarrow$ loại trừ khỏi bộ dóng hàng câu.
   - Dòng chữ Hán in rời không dấu câu $ightarrow$ bắt buộc đi qua `src/phonetic_verifier.py::project_punctuation` để chiếu dấu câu từ dòng `Phiên âm` lên dòng `Chữ Hán`.
2. **Thơ văn Lý Trần — Tập II, Quyển Thượng (`TVLT2`)**:
   - Công thức lệch trang phần nội dung: `PDF_Page = Book_Page - 2`.
   - **Trang sách 27 (`PDF 25`) bị trắng hoàn toàn** $ightarrow$ bài số 3 (*Thiền tông chỉ nam tự*, `PDF 22–29`) bị đứt phần cuối `Phiên âm` và đầu `Dịch nghĩa`. Cần đánh dấu loại trừ hoặc chỉ dóng hàng tới dòng có bản dịch.
   - Loại trừ 4 tác phẩm **Chữ Nôm** không có mục `Dịch nghĩa` (trang sách `495–520`, `521–527`, `690–705`, `864–875`).
   - Chữ Hán viết tay có ký hiệu chú thích khảo dị `1*`, `2*` dính sát chữ $ightarrow$ đã xử lý bằng regex `(?<!\d)\d{1,3}\s*\*+` trong `src/text_cleaner.py`.
3. **Thể loại từ Việt Nam thời trung đại (`TLTVN`)**:
   - Lớp text ẩn có sẵn trong PDF bị hỏng 100% chữ Hán (`0` ký tự CJK) $ightarrow$ bắt buộc OCR lại từ ảnh PNG 300 DPI.
   - Chỉ trích xuất **Phần Ba — Tổng tập từ Việt Nam** (trang sách `127–540` / `PDF 134–547`, công thức `PDF_Page = Book_Page + 7`).
   - Dấu chấm hết câu chữ Hán trong sách in bằng dấu chấm ASCII `.` $ightarrow$ tự động chuẩn hóa thành `。` trong `src/text_cleaner.py::clean_han_text`.

---

## 4. Lệnh Tiếp tục Công việc (Exact Resume Commands)

```bash
python3 .agents/skills/wayfinder/scripts/wayfinder.py --sync
```
