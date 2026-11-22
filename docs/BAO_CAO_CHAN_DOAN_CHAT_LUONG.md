# BÁO CÁO CHẨN ĐOÁN CHẤT LƯỢNG NGỮ LIỆU & ĐỘ PHỦ TỪ VỰNG
## Hệ thống Dóng hàng Tự động Ngữ liệu Song ngữ Hán – Việt

- **Thời điểm kiểm định**: `2026-11-22 09:45:59 UTC`
- **Phạm vi đối soát**: 3 bộ sách gốc (*Hán Văn Tinh Túy*, *Thơ văn Lý – Trần 2*, *Thể loại từ VN*).
- **Công cụ chẩn đoán**: `src/word_aligner.py` & `src/exporter_and_qa.py`.

---

### 1. Bảng Tổng Hợp Chỉ Số Toàn Cục

| Mã sách | Tên tác phẩm | Tổng cặp | Lỗi QA (%) | Phủ Hán (%) | Phủ Việt (%) | Điểm Tin cậy TB | Số câu Cần Lưu ý |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `HVTT` | Hán Văn Tinh Túy (Lãng Nhân) | 28 | 0.00% | 96.2% | 32.2% | **0.78 / 1.0** | 2 |
| `TVLT2` | Thơ văn Lý – Trần Tập II (Nguyễn Huệ Chi chủ biên) | 15 | 0.00% | 84.1% | 30.4% | **0.72 / 1.0** | 6 |
| `TLTVN` | Thể loại từ Việt Nam thời trung đại (Nguyễn Xuân Diện) | 5 | 0.00% | 100.0% | 31.5% | **0.79 / 1.0** | 0 |

---

### 2. Phân Tích Chi Tiết Từng Bộ Sách

#### 📖 Hán Văn Tinh Túy (Lãng Nhân) (`HVTT`)
- **Tổng số cặp câu**: `28`
- **Phân bố độ tin cậy**: Cao (>= 0.85): `1` | Trung bình: `25` | Cần lưu ý: `2`
- **Chữ Hán hay vắng mặt trong bản dịch (Omission candidates)**: `授` (1 lần), `旅` (1 lần), `吟` (1 lần), `入` (1 lần), `蕭` (1 lần), `條` (1 lần), `占` (1 lần), `閒` (1 lần), `棋` (1 lần), `陣` (1 lần)

**Các câu được đánh dấu cần chuyên gia thẩm định (Review Flags):**

| STT | Chữ Hán | Bản dịch tiếng Việt | Điểm Tin cậy | Phủ Hán (%) | Chữ chưa khớp |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 26 | `秋夜旅懷吟` | KHÚC NGÂM CẢM HOÀI ĐÊM THU | `0.61` | 60.0% | `旅 吟` |
| 28 | `仙家別占清閒，打殘棋陣，飲殘菊杯！` | Thanh-nhàn riêng một cảnh tiên, Mảng vui cờ thánh rượu hiền tiêu-dao! | `0.67` | 71.4% | `占 閒 棋 陣` |

#### 📖 Thơ văn Lý – Trần Tập II (Nguyễn Huệ Chi chủ biên) (`TVLT2`)
- **Tổng số cặp câu**: `15`
- **Phân bố độ tin cậy**: Cao (>= 0.85): `0` | Trung bình: `9` | Cần lưu ý: `6`
- **Chữ Hán hay vắng mặt trong bản dịch (Omission candidates)**: `先` (5 lần), `求` (3 lần), `己` (3 lần), `指` (2 lần), `序` (2 lần), `今` (2 lần), `顯` (1 lần), `竊` (1 lần), `均` (1 lần), `修` (1 lần)

**Các câu được đánh dấu cần chuyên gia thẩm định (Review Flags):**

| STT | Chữ Hán | Bản dịch tiếng Việt | Điểm Tin cậy | Phủ Hán (%) | Chữ chưa khớp |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 9 | `禪宗指南序` | TỰA SÁCH THIỀN TÔNG CHỈ NAM | `0.60` | 60.0% | `指 序` |
| 10 | `朕竊謂佛無南北均可修求，性有智愚同資覺悟。` | Trẫm thầm nghĩ: Phật không có nam bắc, mọi người đều có thể tu cầu. Tánh có trí ngu, đồng sẵn giác ngộ. | `0.62` | 63.2% | `竊 均 修 求 愚 同 資` |
| 11 | `是以誘群迷之方便，明生死之捷徑者，我佛之大教也；任垂世之權衡，作將來之軌範者，先聖之重責也。` | Vì vậy, phương tiện dẫn dụ đám người mê, để sáng tỏ đường tắt sanh tử, là kinh điển của đức Phật chúng ta. Đặt mực thước cho đời, làm mô phạm người sau, là trọng trách các bậc Thánh trước (Tổ). | `0.63` | 67.5% | `誘 群 便 捷 徑 垂 權 衡 作 軌 範 先 責` |
| 13 | `且朕於孩童有識之年，稍聞禪師之訓，則澄思息慮，慨然清淨，有心乎內教，參究於禪宗，虛己求師，精誠慕道。雖回向之意已萌，而感觸之機未達。` | Vả lại, thuở Trẫm còn niên thiếu có chút ít hiểu biết, vừa nghe lời dạy của Thiền sư thì tâm tư lóng lặng, bỗng dưng thanh tịnh; nên để tâm nơi nội giáo, tham cứu Thiền tông, dốc lòng tìm thầy, chí thành mộ đạo. Tuy ý hồi hướng đã nảy mầm, mà cơ cảm xúc chưa thấu suốt. | `0.58` | 58.9% | `孩 童 稍 訓 澄 息 慮 慨 淨 參 究 己 求 精 誠 慕 回 已 萌 感 觸 機 達` |
| 14 | `師曰：山本無佛，惟存乎心。心寂而知，是名真佛。今陛下若悟此心，則立地成佛，無苦外求也。` | Sư bảo: Trong núi vốn không có Phật, Phật chỉ ở trong tâm. Tâm lặng mà biết gọi là Chân Phật. Nay Bệ hạ nếu ngộ tâm này thì tức khắc thành Phật, không nhọc tìm cầu bên ngoài. | `0.69` | 77.1% | `本 存 寂 名 今 陛 苦 求` |
| 15 | `朕聞是言，乃命工楷寫，敕令開印，非特以為後世指迷，蓋欲繼先代聖人之功廣，因自為序云。` | Trẫm nghe lời này, sai thợ viết chữ chân phương, ra lệnh khắc bản in. Chẳng những để chỉ đường mê cho hậu thế, mà còn muốn tiếp nối công lớn các bậc Thánh nhân đời trước. Vì thế tự làm lời tựa này. | `0.63` | 66.7% | `楷 敕 令 印 特 指 欲 繼 先 代 功 序` |

#### 📖 Thể loại từ Việt Nam thời trung đại (Nguyễn Xuân Diện) (`TLTVN`)
- **Tổng số cặp câu**: `5`
- **Phân bố độ tin cậy**: Cao (>= 0.85): `0` | Trung bình: `5` | Cần lưu ý: `0`
- **Chữ Hán vắng mặt**: Không có.
- **Nhận xét**: 100% các cặp câu đạt độ tin cậy cao, không có câu nào bị đánh cờ cảnh báo.

---

### 3. Đánh Giá Hán Học & Khuyến Nghị Hiệu Đính

1. **Tính bảo toàn của Trợ từ Hán văn (Classical Particles)**:
   - Các chữ như `有` (hữu), `之` (chi), `者` (giả), `也` (dã) là các hư từ/ngữ khí từ mang chức năng ngữ pháp thay vì nghĩa từ vựng, việc người dịch không dịch thành một từ độc lập là hoàn toàn tự nhiên và đúng phong cách dịch thuật cổ điển.
2. **Thơ và Từ khúc dịch thoát ý (Poetic Paraphrase)**:
   - Trong *Thể loại từ VN* và *Thơ văn Lý – Trần 2*, dịch giả dùng từ ngữ gợi hình (ví dụ: `vượt qua những làn sóng xanh`, `xiết bao bùi ngùi`) thay cho dịch từng chữ một, dẫn đến tỷ lệ phủ từ vựng thấp hơn nhưng chất lượng văn phong văn học cao hơn.
3. **Tận dụng CAT Workbench trong Web App**:
   - Sử dụng giao diện `web_app/app.py` để lọc các câu có điểm tin cậy $< 0.70$ và kiểm tra đối soát với ảnh quét trang gốc `01_nguon`.
