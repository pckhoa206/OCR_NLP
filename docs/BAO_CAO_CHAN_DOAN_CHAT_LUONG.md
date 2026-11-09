# BÁO CÁO CHẨN ĐOÁN CHẤT LƯỢNG NGỮ LIỆU & ĐỘ PHỦ TỪ VỰNG
## Hệ thống Dóng hàng Tự động Ngữ liệu Song ngữ Hán – Việt

- **Thời điểm kiểm định**: `2026-11-08 02:18:03 UTC`
- **Phạm vi đối soát**: 3 bộ sách gốc (*Hán Văn Tinh Túy*, *Thơ văn Lý – Trần 2*, *Thể loại từ VN*).
- **Công cụ chẩn đoán**: `src/word_aligner.py` & `src/exporter_and_qa.py`.

---

### 1. Bảng Tổng Hợp Chỉ Số Toàn Cục

| Mã sách | Tên tác phẩm | Tổng cặp | Lỗi QA (%) | Phủ Hán (%) | Phủ Việt (%) | Điểm Tin cậy TB | Số câu Cần Lưu ý |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `HVTT` | Hán Văn Tinh Túy (Lãng Nhân) | 26 | 0.00% | 98.1% | 45.2% | **0.82 / 1.0** | 1 |
| `TVLT2` | Thơ văn Lý – Trần Tập II (Nguyễn Huệ Chi chủ biên) | 12 | 0.00% | 54.1% | 36.2% | **0.60 / 1.0** | 10 |
| `TLTVN` | Thể loại từ Việt Nam thời trung đại (Nguyễn Xuân Diện) | 4 | 0.00% | 76.1% | 53.9% | **0.75 / 1.0** | 2 |

---

### 2. Phân Tích Chi Tiết Từng Bộ Sách

#### 📖 Hán Văn Tinh Túy (Lãng Nhân) (`HVTT`)
- **Tổng số cặp câu**: `26`
- **Phân bố độ tin cậy**: Cao (>= 0.85): `7` | Trung bình: `18` | Cần lưu ý: `1`
- **Chữ Hán hay vắng mặt trong bản dịch (Omission candidates)**: `入` (1 lần), `蕭` (1 lần), `條` (1 lần), `占` (1 lần), `閒` (1 lần), `棋` (1 lần), `陣` (1 lần)

**Các câu được đánh dấu cần chuyên gia thẩm định (Review Flags):**

| STT | Chữ Hán | Bản dịch tiếng Việt | Điểm Tin cậy | Phủ Hán (%) | Chữ chưa khớp |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 26 | `仙家別占清閒，打殘棋陣，飲殘菊杯！` | Thanh-nhàn riêng một cảnh tiên, Mảng vui cờ thánh rượu hiền tiêu-dao! | `0.67` | 71.4% | `占 閒 棋 陣` |

#### 📖 Thơ văn Lý – Trần Tập II (Nguyễn Huệ Chi chủ biên) (`TVLT2`)
- **Tổng số cặp câu**: `12`
- **Phân bố độ tin cậy**: Cao (>= 0.85): `1` | Trung bình: `1` | Cần lưu ý: `10`
- **Chữ Hán hay vắng mặt trong bản dịch (Omission candidates)**: `為` (5 lần), `先` (5 lần), `求` (3 lần), `是` (3 lần), `則` (3 lần), `於` (3 lần), `己` (3 lần), `此` (2 lần), `未` (2 lần), `蓋` (2 lần)

**Các câu được đánh dấu cần chuyên gia thẩm định (Review Flags):**

| STT | Chữ Hán | Bản dịch tiếng Việt | Điểm Tin cậy | Phủ Hán (%) | Chữ chưa khớp |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 3 | `顧無瓊報自懷慚，極目江皋意不堪。` | Nghĩ không có ngọc quỳnh đáp lại, lòng tự thẹn. Trên bờ sông nhìn xa mãi xiết bao bùi ngùi. | `0.47` | 35.7% | `顧 報 懷 慚 極 目 皋 意 堪` |
| 4 | `馬首秋風吹劍鋏，屋梁落月照書庵。` | Gió thu trước đầu ngựa thổi vào thanh gươm, Ánh trăng lọt qua rường nhà dọi vào phòng sách. | `0.54` | 42.9% | `吹 鋏 屋 梁 落 照 書 庵` |
| 5 | `幕空難駐燕歸北，地暖愁聞雁別南。` | Màn trống khó ngăn chim én về phương Bắc, Đất ấm buồn nghe chim nhạn biệt phương Nam. | `0.66` | 64.3% | `幕 空 難 駐 暖` |
| 6 | `此去未知傾蓋日，詩篇聊為當清談。` | Lần đi này chưa biết ngày nào mới có dịp nghiêng lọng, Xin vì cuộc chuyện trò tao nhã mà có một bài thơ. | `0.43` | 28.6% | `此 未 傾 蓋 篇 聊 為 當 清 談` |
| 7 | `朕竊謂佛無南北均可修求，性有智愚同資覺悟。` | Trẫm thầm nghĩ: Phật không có nam bắc, mọi người đều có thể tu cầu. Tánh có trí ngu, đồng sẵn giác ngộ. | `0.62` | 52.6% | `竊 謂 均 可 修 求 愚 同 資` |
| 8 | `是以誘群迷之方便，明生死之捷徑者，我佛之大教也；任垂世之權衡，作將來之軌範者，先聖之重責也。` | Vì vậy, phương tiện dẫn dụ đám người mê, để sáng tỏ đường tắt sanh tử, là kinh điển của đức Phật chúng ta. Đặt mực thước cho đời, làm mô phạm người sau, là trọng trách các bậc Thánh trước (Tổ). | `0.55` | 47.5% | `是 以 誘 群 便 捷 徑 大 教 任 垂 世 權 衡 作 將 來 軌 範 先 責` |
| 9 | `故六祖有言云：先大聖人與大師無別，則知我佛之教，又假先聖人以傳於世也。今朕焉可不以先聖之任為己之任，我佛之教為己之教哉！` | Cho nên Lục Tổ nói: Những bậc Thánh trước (Tổ) cùng Đại sư (Phật) không khác. Nên biết giáo pháp của Phật nhờ các bậc Thánh trước truyền bá ở đời. Nay Trẫm đâu thể không lấy trách nhiệm các bậc Thánh trước làm trách nhiệm của mình, giáo pháp của Phật làm giáo pháp của mình. | `0.60` | 59.3% | `有 先 人 別 則 又 假 先 人 傳 於 世 也 今 焉 可 先 為 己 為 己 哉` |
| 10 | `且朕於孩童有識之年，稍聞禪師之訓，則澄思息慮，慨然清淨，有心乎內教，參究於禪宗，虛己求師，精誠慕道。雖回向之意已萌，而感觸之機未達。` | Vả lại, thuở Trẫm còn niên thiếu có chút ít hiểu biết, vừa nghe lời dạy của Thiền sư thì tâm tư lóng lặng, bỗng dưng thanh tịnh; nên để tâm nơi nội giáo, tham cứu Thiền tông, dốc lòng tìm thầy, chí thành mộ đạo. Tuy ý hồi hướng đã nảy mầm, mà cơ cảm xúc chưa thấu suốt. | `0.53` | 42.9% | `且 於 孩 童 稍 訓 則 澄 息 慮 慨 然 淨 乎 參 究 於 虛 己 求 精 誠 慕 回 已 萌 而 感 觸 機 未 達` |
| 11 | `師曰：山本無佛，惟存乎心。心寂而知，是名真佛。今陛下若悟此心，則立地成佛，無苦外求也。` | Sư bảo: Trong núi vốn không có Phật, Phật chỉ ở trong tâm. Tâm lặng mà biết gọi là Chân Phật. Nay Bệ hạ nếu ngộ tâm này thì tức khắc thành Phật, không nhọc tìm cầu bên ngoài. | `0.59` | 51.4% | `本 惟 存 乎 寂 而 是 名 今 陛 此 則 立 地 苦 求 也` |
| 12 | `朕聞是言，乃命工楷寫，敕令開印，非特以為後世指迷，蓋欲繼先代聖人之功廣，因自為序云。` | Trẫm nghe lời này, sai thợ viết chữ chân phương, ra lệnh khắc bản in. Chẳng những để chỉ đường mê cho hậu thế, mà còn muốn tiếp nối công lớn các bậc Thánh nhân đời trước. Vì thế tự làm lời tựa này. | `0.51` | 38.9% | `是 乃 命 楷 敕 令 開 印 非 特 為 指 蓋 欲 繼 先 代 功 廣 為 序 云` |

#### 📖 Thể loại từ Việt Nam thời trung đại (Nguyễn Xuân Diện) (`TLTVN`)
- **Tổng số cặp câu**: `4`
- **Phân bố độ tin cậy**: Cao (>= 0.85): `1` | Trung bình: `1` | Cần lưu ý: `2`
- **Chữ Hán hay vắng mặt trong bản dịch (Omission candidates)**: `祥` (1 lần), `長` (1 lần), `觴` (1 lần), `攀` (1 lần), `戀` (1 lần), `星` (1 lần), `郎` (1 lần), `願` (1 lần), `將` (1 lần), `為` (1 lần)

**Các câu được đánh dấu cần chuyên gia thẩm định (Review Flags):**

| STT | Chữ Hán | Bản dịch tiếng Việt | Điểm Tin cậy | Phủ Hán (%) | Chữ chưa khớp |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 3 | `情慘切，對離觴，攀戀使星郎。` | Tình thảm thiết, Đối diện với chén rượu biệt li, Yêu mến vin lấy chàng sứ giả. | `0.61` | 54.5% | `觴 攀 戀 星 郎` |
| 4 | `願將深意為南疆，分明報我皇。` | Xin hãy đem cái ý sâu xa vì biên cương phía Nam, Báo rõ cho nhà vua của chúng ta. | `0.68` | 66.7% | `願 將 為 分` |

---

### 3. Đánh Giá Hán Học & Khuyến Nghị Hiệu Đính

1. **Tính bảo toàn của Trợ từ Hán văn (Classical Particles)**:
   - Các chữ như `有` (hữu), `之` (chi), `者` (giả), `也` (dã) là các hư từ/ngữ khí từ mang chức năng ngữ pháp thay vì nghĩa từ vựng, việc người dịch không dịch thành một từ độc lập là hoàn toàn tự nhiên và đúng phong cách dịch thuật cổ điển.
2. **Thơ và Từ khúc dịch thoát ý (Poetic Paraphrase)**:
   - Trong *Thể loại từ VN* và *Thơ văn Lý – Trần 2*, dịch giả dùng từ ngữ gợi hình (ví dụ: `vượt qua những làn sóng xanh`, `xiết bao bùi ngùi`) thay cho dịch từng chữ một, dẫn đến tỷ lệ phủ từ vựng thấp hơn nhưng chất lượng văn phong văn học cao hơn.
3. **Tận dụng CAT Workbench trong Web App**:
   - Sử dụng giao diện `web_app/app.py` để lọc các câu có điểm tin cậy $< 0.70$ và kiểm tra đối soát với ảnh quét trang gốc `01_nguon`.
