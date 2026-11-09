# BẢNG KIỂM KÊ NGUỒN DỮ LIỆU SONG NGỮ HÁN – VIỆT (BƯỚC 1 & BƯỚC 2)

Tài liệu này thực hiện **Bước 1 (Nhận đề tài và xác nhận phạm vi)** và **Bước 2 (Kiểm kê nguồn & Ánh xạ phần/trang)** theo đúng quy định tại Mục 4 của `Guideline.pdf` cho dự án xây dựng ngữ liệu song ngữ Hán – Việt.

---

## 1. Xác nhận đề tài và phạm vi tổng thể (Bước 1)

Dự án xử lý **03 nguồn tư liệu PDF Scan** chứa văn bản song ngữ Hán – Việt (nguyên tác chữ Hán đi kèm phiên âm Hán-Việt, bản dịch nghĩa xuôi và/hoặc dịch thơ trong cùng một ấn phẩm):

1. **`HVTT_HanVanTinhTuy`** — *Hán Văn Tinh Túy* (Lãng Nhân Phùng Tất Đắc biên dịch).
2. **`TVLT2_ThoVanLyTran2`** — *Thơ văn Lý – Trần, Tập II – Quyển Thượng* (Nguyễn Huệ Chi chủ biên, Viện Văn học).
3. **`TLTVN_TheLoaiTuVN`** — *Thể loại từ Việt Nam thời trung đại* (Nguyễn Xuân Diện – Nguyễn Quảng Tuân biên khảo và tuyển dịch).

### Xác nhận tính đồng bộ phạm vi Hán – Việt trước khi OCR
- Cả 3 tài liệu đều là ấn phẩm học thuật/tuyển dịch song ngữ có đối chiếu trực tiếp giữa **Nguyên văn chữ Hán** và **Dịch nghĩa tiếng Việt** trên cùng một trang hoặc các trang liên tiếp trong cùng một mục tác phẩm.
- Những phần chỉ có tiếng Việt nghiên cứu (như *Phần Một & Phần Hai* của `TLTVN`, hoặc các trang lẻ *Trích giảng* của `HVTT`), những bài thiếu phần *Dịch nghĩa xuôi* (trang sách 361–375 của `HVTT`), các trang scan lỗi/trắng (trang PDF 25 của `TVLT2`), và các tác phẩm viết bằng **Chữ Nôm** (4 bài phú/ca chữ Nôm trong `TVLT2`) đã được rà soát ở đầu, giữa và cuối tài liệu để **loại trừ chính xác** trước khi chạy OCR và dóng hàng.

---

## 2. Bảng kiểm kê nguồn chi tiết (Bước 2)

Bảng dưới đây liệt kê đầy đủ 8 trường bắt buộc theo `Guideline.pdf` (Tên tài liệu, Ngôn ngữ, Link nguồn/Nguồn gốc, Tên tệp, Số trang, Định dạng, Phạm vi, Ghi chú lỗi):

| Trường | Tài liệu 1 (`HVTT`) | Tài liệu 2 (`TVLT2`) | Tài liệu 3 (`TLTVN`) |
| :--- | :--- | :--- | :--- |
| **Mã đề tài / Thư mục** | `HVTT_HanVanTinhTuy` | `TVLT2_ThoVanLyTran2` | `TLTVN_TheLoaiTuVN` |
| **Tên tài liệu** | *Hán Văn Tinh Túy* (Biên giả: Lãng Nhân Phùng Tất Đắc) | *Thơ văn Lý – Trần (Tập II – Quyển Thượng)* (Chủ biên: Nguyễn Huệ Chi) | *Thể loại từ Việt Nam thời trung đại* (Tác giả: Nguyễn Xuân Diện – Nguyễn Quảng Tuân) |
| **Ngôn ngữ** | Song ngữ Hán – Việt (Chữ Hán phồn thể + Phiên âm Hán-Việt + Dịch nghĩa tiếng Việt + Trích giảng) | Song ngữ Hán – Việt (Chữ Hán phồn thể + Phiên âm Hán-Việt + Dịch nghĩa + Dịch thơ + Khảo đính/Chú thích; có lẫn 4 bài Chữ Nôm đã lọc bỏ) | Song ngữ Hán – Việt ở Phần Ba (Chữ Hán phồn thể + Phiên âm + Dịch nghĩa + Dịch thơ + Chú thích); Tiếng Việt ở Phần Một, Hai & Phụ lục |
| **Link nguồn / Nguồn gốc** | Bản số hóa PDF kho học liệu Đồ án NLP (`workspace:/Hán Văn Tinh Túy - Lãng Nhân.pdf`; NXB Nam Chi Tùng Thư / Bản in Sài Gòn) | Bản số hóa PDF kho học liệu Đồ án NLP (`workspace:/Nguyễn Huệ Chi (chủ biên) - Thơ văn Lý Trần 2.pdf`; NXB Khoa học Xã hội, Hà Nội, 1989) | Bản số hóa PDF kho học liệu Đồ án NLP (`workspace:/Thể loại từ VN thời trung đại.pdf`; NXB Khoa học Xã hội / Viện Nghiên cứu Hán Nôm) |
| **Tên tệp** | `Hán Văn Tinh Túy - Lãng Nhân.pdf` | `Nguyễn Huệ Chi (chủ biên) - Thơ văn Lý Trần 2.pdf` | `Thể loại từ VN thời trung đại.pdf` |
| **Số trang** | **Tổng số trang PDF:** 386 trang<br>**Trang nội dung hợp lệ:** 180 trang PDF chẵn (tương ứng các trang sách chẵn từ 2 đến 360, tức PDF trang 8..366 bước nhảy 2) | **Tổng số trang PDF:** 965 trang<br>**Trang nội dung hợp lệ:** 795 trang PDF (trong khoảng trang sách 19..863 / PDF 17..861, sau khi trừ 1 trang scan trắng và 49 trang Chữ Nôm) | **Tổng số trang PDF:** 645 trang<br>**Trang nội dung hợp lệ:** 414 trang PDF thuộc *Phần Ba* (trang sách 127..540 / PDF trang 134..547) |
| **Định dạng** | `PDF Scan` (ảnh quét trang sách in chữ Hán kèm quốc ngữ, không có lớp text chuẩn) | `PDF Scan` (ảnh quét trang sách in lito/typo cổ, có nhiễu hạt nền và vết xuyên trang nhẹ) | `PDF Scan` (ảnh quét trang sách in hiện đại, rõ nét, không có lớp text chuẩn) |
| **Phạm vi** | Các trang sách chẵn `2..360` (`PDF 8..366`, chỉ lấy trang chẵn). Loại bỏ các trang lẻ (`Trích giảng`) và các trang `361..375` (`PDF 367..381`). | Từ bài số 1 đến hết phần thơ văn chữ Hán tại trang sách `19..863` (`PDF 17..861`), ngoại trừ trang PDF `25` và 4 tác phẩm Chữ Nôm. | Toàn bộ **Phần Ba: Tuyển tập từ Việt Nam thời trung đại** tại trang sách `127..540` (`PDF 134..547`). |
| **Ghi chú lỗi & Bất thường** | - Công thức lệch trang: `pdf_page = book_page + 6`.<br>- Trang sách lẻ `3..359` (`PDF 9..365` lẻ) chỉ chứa lời bình *Trích giảng* tiếng Việt.<br>- Trang sách `361..375` (`PDF 367..381`) là các bài thơ Đường chỉ có *Chữ Hán + Phiên âm + Dịch thơ*, **thiếu phần Dịch nghĩa xuôi** nên loại trừ. | - Công thức lệch trang: `book_page = pdf_page + 2` (áp dụng cho `pdf_page >= 7` do đầu sách thiếu trang 7–8).<br>- **Trang PDF 25** (trang sách 27) bị **scan trắng hoàn toàn (blank scan)**, làm khuyết đoạn giữa bài 3 *Thiền tông chỉ nam tự*.<br>- Có **4 tác phẩm Chữ Nôm** cần loại trừ: *Cư trần lạc đạo phú* (sách `495..520` / PDF `493..518`), *Đắc thú lâm tuyền thành đạo ca* (sách `521..527` / PDF `519..525`), *Vịnh Vân-yên tự phú* (sách `690..705` / PDF `688..703`), *Giáo tử phú* (sách `864..875` / PDF `862..873`). | - Công thức lệch trang: `pdf_page = book_page + 7` (áp dụng cho trang sách `1..593`).<br>- Đầu sách **thiếu 2 trang La Mã `VI` (Mục lục phần 2) và `VII`**.<br>- *Phần Một & Phần Hai* (sách `1..126` / PDF `8..133`) là chuyên khảo tiếng Việt.<br>- *Phụ lục* (sách `541..635` / PDF `548..643`) có **2 trang scan ngược 180°** tại `PDF 589..590` (sách `582..583`) và **trang gập tách đôi** tại `PDF 601..602` (sách `594`). |

---

## 3. Bảng ánh xạ phần/trang và Công thức quy đổi (Step 2 Mapping Tables)

### 3.1. Tài liệu 1: `HVTT` (*Hán Văn Tinh Túy* – 386 trang PDF)
- **Công thức ánh xạ:** `pdf_page = book_page + 6` $\Leftrightarrow$ `book_page = pdf_page - 6`
- **Bố cục nội dung:** Hai trang đối diện theo cặp:
  - **Trang sách chẵn (`PDF chẵn 8..366`):** Bố cục xen kẽ từng câu (*interlinear*). Mỗi câu gồm dòng chữ Hán (in lớn), dòng Phiên âm Hán-Việt (in nghiêng đậm) và dòng Dịch nghĩa tiếng Việt (in thường).
  - **Trang sách lẻ (`PDF lẻ 9..365`):** Phần *Trích giảng* giải thích điển tích, tiểu sử tác giả bằng tiếng Việt.

| Phần / Mục nội dung | Trang sách (`book_page`) | Trang PDF (`pdf_page`) | Số trang PDF | Trạng thái xử lý | Ghi chú chi tiết |
| :--- | :---: | :---: | :---: | :---: | :--- |
| Bìa, Lời nói đầu, Trang tựa | Không đánh số, I–IV, 1 | `1..7` | 7 | **Loại trừ** | Phần mở đầu sách |
| Văn bản đối chiếu Hán – Việt (Trang chẵn) | `2, 4, 6, ..., 360` | `8, 10, 12, ..., 366` | **180** | **Sử dụng (Hợp lệ)** | Đủ 3 tầng: Chữ Hán + Phiên âm + Dịch nghĩa xuôi từng câu |
| Phần Trích giảng (Trang lẻ) | `3, 5, 7, ..., 359` | `9, 11, 13, ..., 365` | 179 | **Loại trừ** | Bình giảng tiếng Việt, không phải câu đối chiếu trực tiếp |
| Phần Thơ Đường cuối sách | `361..375` | `367..381` | 15 | **Loại trừ** | Chỉ có Chữ Hán + Phiên âm + Dịch thơ, **thiếu Dịch nghĩa xuôi** |
| Mục lục cuối sách | `376..380` | `382..386` | 5 | **Loại trừ** | Mục lục tra cứu |
| **Mẫu thử nghiệm (Pilot Pages)** | `2, 4, 6, 44, 306, 320` | `[8, 10, 12, 50, 312, 326]` | 6 | **Pilot OCR** | Trích xuất vào `deliverables/HVTT_HanVanTinhTuy/01_nguon/` |

---

### 3.2. Tài liệu 2: `TVLT2` (*Thơ văn Lý – Trần Tập II, Quyển Thượng* – 965 trang PDF)
- **Công thức ánh xạ:** `book_page = pdf_page + 2` $\Leftrightarrow$ `pdf_page = book_page - 2` (áp dụng cho `pdf_page >= 7`).
- **Bố cục nội dung:** Trình bày nối tiếp theo khối trong từng bài (*sequential section blocks*):
  1. Tiêu đề bài + Nguyên văn chữ Hán (cột trái) song song với Phiên âm Hán-Việt (cột phải) hoặc nối tiếp.
  2. Mục `DỊCH NGHĨA:` (văn xuôi tiếng Việt dùng để dóng hàng chính).
  3. Mục `DỊCH THƠ:` (nếu là thơ/kệ).
  4. Mục `KHẢO ĐÍNH:` và `CHÚ THÍCH:` (loại bỏ khi làm sạch theo Bước 5 `Guideline.pdf`).

| Phần / Mục nội dung | Trang sách (`book_page`) | Trang PDF (`pdf_page`) | Số trang PDF | Trạng thái xử lý | Ghi chú chi tiết |
| :--- | :---: | :---: | :---: | :---: | :--- |
| Bìa, Giới thiệu, Khái luận đầu tập | `1..6, 9..18` (thiếu 7–8) | `1..16` | 16 | **Loại trừ** | Phần dẫn nhập tiếng Việt |
| Thơ văn chữ Hán (Đoạn 1: Bài 1 – đầu Bài 3) | `19..26` | `17..24` | **8** | **Sử dụng (Hợp lệ)** | Song ngữ Hán – Việt |
| **Lỗi trang trắng (Blank Scan)** | `27` | `25` | 1 | **Loại trừ (Lỗi scan)** | Trang PDF 25 trắng tinh, mất phần giữa bài 3 *Thiền tông chỉ nam tự* |
| Thơ văn chữ Hán (Đoạn 2: Cuối Bài 3 – trước Phú Nôm) | `28..494` | `26..492` | **467** | **Sử dụng (Hợp lệ)** | Song ngữ Hán – Việt |
| *Cư trần lạc đạo phú* (Trần Nhân Tông) | `495..520` | `493..518` | 26 | **Loại trừ (Chữ Nôm)** | Tác phẩm viết bằng Chữ Nôm |
| *Đắc thú lâm tuyền thành đạo ca* (Trần Nhân Tông) | `521..527` | `519..525` | 7 | **Loại trừ (Chữ Nôm)** | Tác phẩm viết bằng Chữ Nôm |
| Thơ văn chữ Hán (Đoạn 3) | `528..689` | `526..687` | **162** | **Sử dụng (Hợp lệ)** | Song ngữ Hán – Việt |
| *Vịnh Vân-yên tự phú* (Huyền Quang) | `690..705` | `688..703` | 16 | **Loại trừ (Chữ Nôm)** | Tác phẩm viết bằng Chữ Nôm |
| Thơ văn chữ Hán (Đoạn 4) | `706..863` | `704..861` | **158** | **Sử dụng (Hợp lệ)** | Song ngữ Hán – Việt (Tổng cộng 4 đoạn hợp lệ = **795 trang PDF**) |
| *Giáo tử phú* (Mạc Đĩnh Chi) | `864..875` | `862..873` | 12 | **Loại trừ (Chữ Nôm)** | Tác phẩm viết bằng Chữ Nôm ở cuối phần tác phẩm |
| Khảo đính chung, Sách dẫn, Mục lục | `876..967` | `874..965` | 92 | **Loại trừ** | Phụ lục tra cứu và mục lục cuối sách |
| **Mẫu thử nghiệm (Pilot Pages)** | `21, 22, 40, 42, 44` | `[19, 20, 38, 40, 42]` | 5 | **Pilot OCR** | Trích xuất vào `deliverables/TVLT2_ThoVanLyTran2/01_nguon/` |

---

### 3.3. Tài liệu 3: `TLTVN` (*Thể loại từ Việt Nam thời trung đại* – 645 trang PDF)
- **Công thức ánh xạ:** `pdf_page = book_page + 7` $\Leftrightarrow$ `book_page = pdf_page - 7` (áp dụng chính xác cho trang sách `1..593`).
- **Bố cục nội dung (Phần Ba):** Mỗi tác giả có đoạn tiểu dẫn ngắn, tiếp theo từng bài *từ* trình bày theo thứ tự:
  1. Tên điệu từ + Nguyên văn chữ Hán.
  2. `Phiên âm:` (Hán-Việt).
  3. `Dịch nghĩa:` (văn xuôi tiếng Việt dùng để dóng hàng chính với nguyên văn chữ Hán).
  4. `Dịch thơ:` và `Chú thích:`.

| Phần / Mục nội dung | Trang sách (`book_page`) | Trang PDF (`pdf_page`) | Số trang PDF | Trạng thái xử lý | Ghi chú chi tiết |
| :--- | :---: | :---: | :---: | :---: | :--- |
| Bìa & Mục lục đầu sách | `I..V, VIII..IX` (thiếu `VI, VII`) | `1..7` | 7 | **Loại trừ (Khuyết trang)** | Thiếu trang `VI` (Mục lục phần 2) và trang `VII` |
| **Phần Một & Phần Hai:** Khái luận & Nghiên cứu | `1..126` | `8..133` | 126 | **Loại trừ** | Chuyên khảo nghiên cứu văn học bằng tiếng Việt |
| **Phần Ba:** Tuyển tập *Từ* Việt Nam thời trung đại | `127..540` | `134..547` | **414** | **Sử dụng (Hợp lệ)** | Tuyển dịch song ngữ Hán – Việt đầy đủ (Ngô Chân Lưu đến cuối thời Nguyễn) |
| **Phụ lục:** Từ phổ, Bảng tra, Tài liệu tham khảo | `541..635` (+2 trang cuối) | `548..645` | 98 | **Loại trừ (Có lỗi scan)** | Trang `PDF 589..590` (sách `582..583`) bị **scan ngược 180°**; trang `PDF 601..602` (sách `594`) là **trang gập tách đôi** làm lệch công thức trang từ sau trang sách 593 |
| **Mẫu thử nghiệm (Pilot Pages)** | `127, 128, 129, 130, 193, 293` | `[134, 135, 136, 137, 200, 300]` | 6 | **Pilot OCR** | Trích xuất vào `deliverables/TLTVN_TheLoaiTuVN/01_nguon/` |

---

## 4. Quy tắc tổ chức thư mục và đặt tên tệp (Bước 2 & Bước 3)

1. **Cấu trúc thư mục bàn giao chuẩn (`Guideline.pdf` Mục 2):**
   - `deliverables/HVTT_HanVanTinhTuy/{01_nguon/han,01_nguon/viet,02_ocr_tho/han,02_ocr_tho/viet,03_text_sach,04_dong_hang}`
   - `deliverables/TVLT2_ThoVanLyTran2/{01_nguon/han,01_nguon/viet,02_ocr_tho/han,02_ocr_tho/viet,03_text_sach,04_dong_hang}`
   - `deliverables/TLTVN_TheLoaiTuVN/{01_nguon/han,01_nguon/viet,02_ocr_tho/han,02_ocr_tho/viet,03_text_sach,04_dong_hang}`
2. **Quy tắc đặt tên tệp trang nguồn (`01_nguon/`):**
   - Mỗi trang PDF được trích xuất thành ảnh PNG độ phân giải cao bằng script `scripts/extract_pages.swift` với tên tệp cố định **4 chữ số** theo đúng `pdf_page`: ví dụ `0008.png`, `0010.png`, `0134.png`.
   - Khi tách phần OCR thô (`02_ocr_tho/han/` và `02_ocr_tho/viet/`), mã trang 4 chữ số này được giữ nguyên để đảm bảo khả năng truy vết 1–1 về trang PDF gốc.

---

## 5. Cập nhật theo Giải đáp Chính thức của Giảng viên

Theo hướng dẫn bổ sung từ Giảng viên đối với các bất thường ở 3 bộ sách:

1. **`HVTT_HanVanTinhTuy` (*Hán Văn Tinh Túy*)**:
   - Cấu trúc bộ sách gồm 4 phần: `Hán - Dịch âm - Dịch nghĩa - Dịch thơ`. File dóng hàng (`HVTT_HanVanTinhTuy_parallel.tsv` & `.xlsx`) xuất đủ **4 cột tương ứng** (`Hán`, `Dịch âm`, `Dịch nghĩa`, `Dịch thơ`).
   - Riêng **bài cuối (*Thu dạ hoài ngâm* — Kỳ-Đồng, `PDF 367–381` / trang sách `361–375`)** và các bài thơ cổ chỉ có `Hán - Dịch âm - Dịch thơ`, cột **`Dịch nghĩa` được để trống (`""`)**, lấy phần `Dịch thơ` từ các trang lẻ đối diện (`PDF 369, 371, 373, 375, 377, 379, 381`).
2. **`TVLT2_ThoVanLyTran2` (*Thơ văn Lý – Trần Tập II*)**:
   - Đối với **bài số 3 (*Thiền tông chỉ nam tự* — Trần Thái Tông)** bị mất đoạn đầu phần Dịch nghĩa do trang `PDF 25` (trang sách `27`) bị trắng: sử dụng văn bản dịch nghĩa đầy đủ do Giảng viên cung cấp tại Google Drive (`1kfB6t89jzT96PhK8vzngwyYdskLN8GSx`), lưu tại [`deliverables/TVLT2_ThoVanLyTran2/01_nguon/bai_03_thien_tong_chi_nam_tu_dich_nghia.txt`](../deliverables/TVLT2_ThoVanLyTran2/01_nguon/bai_03_thien_tong_chi_nam_tu_dich_nghia.txt).
3. **`TLTVN_TheLoaiTuVN` (*Thể loại từ Việt Nam thời trung đại*)**:
   - Chỉ thực hiện dóng hàng **Phần Ba: Tuyển tập từ Việt Nam thời trung đại**.
   - Phần chữ Hán trích xuất ảnh và xử lý OCR.
   - Đã lập báo cáo chi tiết các bài khuyết bản gốc chữ Hán/Nôm và các quyển chỉ có chữ Hán trong phần Phụ lục tại [`docs/THONG_KE_BO_SUNG_GIANG_VIEN.md`](THONG_KE_BO_SUNG_GIANG_VIEN.md).
