# DANH SÁCH HẬU KIỂM LỖI THỦ CÔNG (GUIDELINE MỤC 8)

Tài liệu này tổng hợp toàn bộ các dòng còn lại bị `src/exporter_and_qa.py::validate_pairs` gắn cờ cảnh báo trên kết quả chạy thực tế Kaggle GPU v4 của thành viên **Khoa** (`outputs/khoa/`, `397(+1) = 398` trang, tổng cộng **`2.488` cặp** ở chuẩn thống nhất **4 cột**: `Hán | Dịch âm | Dịch nghĩa | Dịch thơ`).

> **Nguyên tắc Guideline Mục 8**: Dù cả 3 bộ sách đều đã vượt xa ngưỡng nghiệm thu ($\le 30\%$) và mục tiêu nội bộ ($\le 20\%$) với **`0` lỗi `MISSING`**, **`0` lỗi `FORMAT_ERROR`** và **`0` lỗi `LEFTOVER_MARKER`**, mọi dòng cụ thể bị gắn cờ bên dưới vẫn được liệt kê kèm chỉ số dòng TSV/XLSX để rà soát và hiệu đính thủ công trong **CAT Workbench** (`streamlit run web_app/app.py`).

---

## 1. Bảng Tổng Hợp Số Lượng Dòng Cần Hậu Kiểm (`outputs/khoa/`)

| Bộ sách | Tệp đích (`.tsv` / `.xlsx`) | Tổng số cặp | `MISSING` | `OMISSION` | `ADDITION` | `NUMBER_MISMATCH` | `FORMAT_ERROR` | `LEFTOVER_MARKER` | Tổng dòng gắn cờ (duy nhất) | Tỷ lệ lỗi QA |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`HVTT`** | `outputs/khoa/deliverables/HVTT_HanVanTinhTuy/04_dong_hang/HVTT_HanVanTinhTuy_parallel.tsv` | **275** | 0 | **8** | 0 | 0 | 0 | 0 | **8** | **2.91%** (`0.029091`) |
| **`TVLT2`** | `outputs/khoa/deliverables/TVLT2_ThoVanLyTran2/04_dong_hang/TVLT2_ThoVanLyTran2_parallel.tsv` | **1.693** | 0 | **78** | **7** | **33** | 0 | 0 | **117** *(118 lượt cờ)* | **6.91%** (`0.069108`) |
| **`TLTVN`** | `outputs/khoa/deliverables/TLTVN_TheLoaiTuVN/04_dong_hang/TLTVN_TheLoaiTuVN_parallel.tsv` | **520** | 0 | **15** | 0 | **3** | 0 | 0 | **16** *(18 lượt cờ)* | **3.08%** (`0.030769`) |
| **Tổng** | **03 bộ sách (`outputs/khoa/`)** | **2.488** | **0** | **101** | **7** | **36** | **0** | **0** | **141** *(144 lượt cờ)* | **5.67%** |

*Ghi chú chỉ số dòng*:
- `row_index`: chỉ số 0-based trong `qa_report.json` (`0..N-1`).
- `Dòng TSV`: số dòng 1-based trong tệp `.tsv` (`row_index + 1`).
- `Hàng XLSX`: số hàng trong sheet `DONG_HANG` của `.xlsx` (`row_index + 2`, do hàng 1 là tiêu đề 4 cột).

---

## 2. Chi Tiết `HVTT_HanVanTinhTuy` — 8 dòng `OMISSION` (`2.91%`)

Cả 8 dòng đều là các câu dịch xuôi ngắn gọn hợp lý (tỷ lệ `số từ Việt / số chữ Hán` trong khoảng `0.43–0.67 < 0.70`) hoặc có lỗi dấu chính tả nhẹ do OCR tiếng Việt cần sửa trực tiếp:

| `row_index` | Dòng TSV | Hàng XLSX | Loại lỗi | Lý do (`validate_pairs`) | Chữ Hán | Dịch nghĩa (Mẫu kiểm tra) | Nhận xét hậu kiểm |
| :---: | :---: | :---: | :--- | :--- | :--- | :--- | :--- |
| `26` | `27` | `28` | `OMISSION` | `0.67 < 0.7 (6/9)` | `慘不畏明，糾之以猛也` | `Không xong sẽ dùng sức mạnh` | Dịch thoát ý (4 chữ `慘不畏明` dịch gọn thành `Không xong`), kiểm tra đối chiếu trang 12. |
| `55` | `56` | `57` | `OMISSION` | `0.60 < 0.7 (3/5)` | `民之有口也，` | `Dân có miệng` | Đầy đủ nghĩa (hư từ `之`, `也` không dịch rời). |
| `119` | `120` | `121` | `OMISSION` | `0.50 < 0.7 (3/6)` | `王忿然作色，曰：` | `Vua giận, nói` | Dịch gọn `忿然作色` thành `giận`. |
| `159` | `160` | `161` | `OMISSION` | `0.60 < 0.7 (6/10)` | `故有聞舍本而聞末者耶` | `Nên bỏ gọc mà hỏi ngọn` | Lỗi OCR Việt: sửa `gọc` $\rightarrow$ `gốc` (và rà câu Hán `聞`/`問`). |
| `175` | `176` | `177` | `OMISSION` | `0.43 < 0.7 (3/7)` | `而出於孝情者也` | `hiều cho dân` | Lỗi OCR Việt: sửa `hiều` $\rightarrow$ `hiếu` / đối chiếu vế trên. |
| `182` | `183` | `184` | `OMISSION` | `0.56 < 0.7 (5/9)` | `此率民而出於無用者` | `Thiệt là đồ vô dụng` | Dịch gọn; đối chiếu trang gốc để xác nhận câu trước/sau. |
| `228` | `229` | `230` | `OMISSION` | `0.64 < 0.7 (7/11)` | `吁嗟默默兮，誰知吾之廉貞` | `Buồn thay, ai biết ta liêm-trinh` | Đầy đủ ý chính (giữ nguyên thể dịch Sở từ). |
| `253` | `254` | `255` | `OMISSION` | `0.60 < 0.7 (3/5)` | `墮而折其髀` | `té gẫy đùi.` | Đầy đủ ý chính. |

---

## 3. Chi Tiết `TVLT2_ThoVanLyTran2` — 117 dòng gắn cờ (`6.91%`)

Lưu ý: dòng `row_index = 67` (Dòng TSV `68`) đồng thời bị gắn cả 2 cờ `OMISSION` và `NUMBER_MISMATCH`, nên tổng số lượt cờ là `118` trên `117` dòng duy nhất.

### 3.1. Nhóm `ADDITION` — 7 dòng (Ưu tiên kiểm tra `Split` trong Workbench)

Đây là các dòng có tỷ lệ độ dài `> 4.5` do dóng hàng `1-n` gom nhiều câu tiếng Việt vào một câu Hán ngắn hoặc câu Hán bị ngắt thiếu:

| `row_index` | Dòng TSV | Hàng XLSX | Tỷ lệ | Chữ Hán | Dịch nghĩa (Trích đoạn đầu) | Hướng xử lý Workbench |
| :---: | :---: | :---: | :---: | :--- | :--- | :--- |
| `328` | `329` | `330` | `18.20 (91/5)` | `二者得為人。` | `Nay đã là người, được sinh ở nơi trung tàm của đất nước, lại đủ sâu căn...` | Tách (`Split`) câu Việt gắn sang các câu Hán kế tiếp (`三者得生於中國`...). |
| `333` | `334` | `335` | `26.25 (105/4)` | `不被仁風。` | `Hà chẳng phải bà bực thánh nhân khinh thàn minh mà trọng đạo đó sao...` | Tách đoạn văn xuôi Khuyến phát bồ đề tâm & sửa lỗi OCR Việt (`bà bực` $\rightarrow$ `là bậc`). |
| `415` | `416` | `417` | `23.33 (140/6)` | `紙這向上一路。` | `Hoặc gặp nơi dùa cọt, hoặc gặp chón thư lòng...` | Rà chữ Hán (`紙` $\rightarrow$ `只`?) và tách đoạn dịch nghĩa bị dồn. |
| `494` | `495` | `496` | `14.00 (56/4)` | `得生佛國。` | `Bậc trung trí nếu có thể chăm chỉ tu bành như đã nói ở trên thì lập tức...` | Tách câu Việt trước và sau sang các mệnh đề Hán tương ứng. |
| `693` | `694` | `695` | `5.00 (10/2)` | `獨尊。` | `nói: trời trên, đất dưới, riêng tạ là cao cả` | Ghép (`Merge`) với câu Hán trước (`天上天下唯我`) và sửa `tạ` $\rightarrow$ `ta`. |
| `724` | `725` | `726` | `7.00 (7/1)` | `是。` | `Phật. Phép của Phật là như thế.` | Ghép (`Merge`) với dòng trước để trọn câu `如是。`. |
| `1031` | `1032` | `1033` | `16.00 (16/1)` | `舉` | `Lâm Tế ở trong bội, các vị thượng tọa hai. dây nhà đều quát. một nhà` | Rà tách tiêu đề `Cử` của công án *Niêm tụng kệ* và gộp câu Việt sang dòng `1033`. |

### 3.2. Nhóm `OMISSION` — 78 dòng

- **Danh sách đầy đủ 78 Dòng TSV (1-based)**:
  `35, 49, 57, 64, 68, 130, 196, 214, 254, 302, 361, 376, 388, 466, 475, 482, 509, 510, 520, 524, 588, 645, 663, 674, 679, 698, 797, 897, 963, 994, 1002, 1007, 1033, 1130, 1137, 1138, 1143, 1144, 1193, 1218, 1222, 1223, 1224, 1277, 1288, 1299, 1300, 1332, 1351, 1368, 1369, 1372, 1436, 1446, 1452, 1458, 1467, 1492, 1493, 1495, 1533, 1548, 1554, 1572, 1578, 1586, 1595, 1601, 1663, 1666, 1667, 1670, 1672, 1673, 1674, 1675, 1678, 1692`
- **Phân loại & mẫu đại diện cần ưu tiên kiểm tra**:
  1. **Lệch câu / Rút gọn văn xuôi OCR** (cần `Split`/`Merge` hoặc chỉnh câu):
     - Dòng TSV `49` (`row_index=48`): `師一見欣然。` $\leftrightarrow$ `Sáng hôm sau` *(lệch ranh giới với câu trên)*.
     - Dòng TSV `130` (`row_index=129`): `字恐丁而未識。` $\leftrightarrow$ `vào ani. ma-ta.` *(OCR tiếng Việt sai nặng)*.
     - Dòng TSV `1193` (`row_index=1192`): `牕前竹葉醉醒...` (47 chữ Hán) $\leftrightarrow$ `Chén Trúc diệp trước song bồ tỉnh: khúc Hoa mai trên gác vừa tan.` (14 từ, tỷ lệ `0.30`).
     - Dòng TSV `1667` (`row_index=1666`): `粟紅貫腐不濟貧寒...` (32 chữ Hán) $\leftrightarrow$ `Rột vào lại bết;` (4 từ, tỷ lệ `0.12`).
     - Dòng TSV `1692` (`row_index=1691`): `墮于地獄經億千劫...` (32 chữ Hán) $\leftrightarrow$ `Những tội trên dây:` (4 từ, tỷ lệ `0.12`).
  2. **Mục chuyển tiết `Niêm tụng kệ`** (dịch đúng nhưng 2 chữ Hán vs 1 từ Việt nên tỷ lệ `0.50`):
     - Dòng TSV `698`, `797`, `897`, `1007`: `公頌` / `公顷` / `公颂` $\leftrightarrow$ `Tụng` / `Tung:`.
  3. **Dịch thoáng / Tỉnh lược hư từ hợp lệ** (ví dụ Dòng TSV `35` `奈何。尋而思之。` $\leftrightarrow$ `Phải làm sao đây?`, Dòng TSV `1436` `是香也。` $\leftrightarrow$ `Hương này:`).

### 3.3. Nhóm `NUMBER_MISMATCH` — 33 dòng

- **Danh sách đầy đủ 33 Dòng TSV (1-based)**:
  `68, 87, 132, 137, 150, 161, 162, 164, 165, 183, 187, 201, 212, 248, 282, 337, 338, 343, 358, 415, 457, 522, 558, 662, 766, 830, 835, 948, 1011, 1048, 1153, 1481, 1645`
- **Các nhóm nguyên nhân & mẫu tiêu biểu**:
  1. **Lỗi dấu thanh OCR tiếng Việt ở chữ số Hán–Việt** (dịch đúng nhưng OCR mất/nhầm dấu nên validator không nhận diện):
     - Dòng TSV `150` (`row_index=149`): `原夫四大本无。五蕴非有。` $\leftrightarrow$ `Khoi nguồn, lứ đại...` (`lứ` thay vì `tứ`).
     - Dòng TSV `161` (`row_index=160`): `...致使六道徃來。` $\leftrightarrow$ `...qua lại sảu đường...` (`sảu` thay vì `sáu`).
     - Dòng TSV `282` (`row_index=281`): `不覺四肢真漏屋。` $\leftrightarrow$ `bắt giác tử chi...` (`tử` thay vì `tứ`).
     - Dòng TSV `165, 201, 457, 1011`: `萬` $\leftrightarrow$ `vận`/`van`/`vạn` bị mất dấu nặng.
     - Dòng TSV `1481` (`row_index=1480`): `罵詈三寶...` $\leftrightarrow$ `Chửi mắng tạm bảo...` (`tạm` thay vì `tam`).
  2. **Nhầm chữ Hán OCR gần nét liên quan đến số**:
     - Dòng TSV `835` (`row_index=834`): `元見僧八門便喝` (`八` nhầm từ `入`, `元` nhầm từ `凡`) $\leftrightarrow$ `Nói chung hễ thấy sư vào cửa là quát`.
     - Dòng TSV `1645` (`row_index=1644`): `淡蟾半八碧山頭` (`八` nhầm từ `入`).
     - Dòng TSV `948` (`row_index=947`): `九聖念未盡` (`九` nhầm từ `凡`) $\leftrightarrow$ `phàm và thành`.
  3. **Lệch ranh giới dóng hàng hoặc dịch ý/thành ngữ**:
     - Dòng TSV `68` (`row_index=67`): `至於三尺之童` $\leftrightarrow$ `Cho đến đứa bé lên bảy` *(cách dịch ước lệ: "ba thước" $\approx$ "lên bảy", đúng nghĩa)*.
     - Dòng TSV `337, 338, 343, 662`: lệch câu quanh phần *Khuyến phát bồ đề tâm* / đối đáp thiền sư $\rightarrow$ kiểm tra `Split`/`Merge` trong Workbench.

---

## 4. Chi Tiết `TLTVN_TheLoaiTuVN` — 16 dòng gắn cờ (`3.08%`)

Lưu ý: dòng `row_index = 4` (Dòng TSV `5`) và `row_index = 363` (Dòng TSV `364`) mỗi dòng có cả 2 cờ `OMISSION` và `NUMBER_MISMATCH`, nên tổng số lượt cờ là `18` trên `16` dòng duy nhất:

| `row_index` | Dòng TSV | Hàng XLSX | Loại lỗi | Lý do | Chữ Hán | Dịch nghĩa | Nhận xét hậu kiểm |
| :---: | :---: | :---: | :--- | :--- | :--- | :--- | :--- |
| `4` | `5` | `6` | `OMISSION`, `NUMBER_MISMATCH` | `0.60 < 0.7 (3/5)`; thiếu `九` | `九天歸路長。` | `Tình thảm thiết,` | **Lệch câu** ở bài *Nguyễn lang quy* (bị dịch chuyển 1 dòng trên cột `Dịch nghĩa`). Cần kéo lại đúng câu `Đường về chín tầng trời dài dặc`. |
| `12` | `13` | `14` | `OMISSION` | `0.69 < 0.7 (9/13)` | `古稱孝子有曾參，三足之鳥冠止。` | `Xưa có Tăng Sâm được khen là con hiếu,` | Thiếu vế `三足之鳥冠止` (`chim ba chân đậu trên mũ`) bị gộp/trôi xuống dòng sau. |
| `15` | `16` | `17` | `OMISSION` | `0.68 < 0.7 (15/22)` | `星高，敬祝高堂之壽。遐算欲齊龜鶴數，新詞再唱鷓鴣天。` | `cao đường thêm thọ. Tuổi thọ so tày rùa hạc, hát bài Giá cô thiên` | Hầu như đủ ý (khuyết 2 chữ đầu `星高` thuộc dòng trên). |
| `27` | `28` | `29` | `OMISSION` | `0.70 < 0.7 (16/23)` | `茲當九十日，韶華好箇暄和之候，再一番快事，聊為勝賞之` | `từ) chơi. Nay đương tiết xuân tươi ấm áp, lại một phen vui vẻ, cần phải` | Ngắt dòng câu dài (*Thập cửu phong* tiểu dẫn); rà nối vế trước/sau. |
| `28` | `29` | `30` | `OMISSION` | `0.54 < 0.7 (13/24)` | `歡會。適逢嘉興來，堪玩可人惟有酒。喜兼四美二難，行樂須及` | `thưởng thức cảnh đẹp. Gặp khi hứng đến, đáng để du ngoạn, vốn` | Tiếp nối tiểu dẫn trên; kiểm tra ranh giới với dòng `30`. |
| `51` | `52` | `53` | `OMISSION` | `0.62 < 0.7 (8/13)` | `古來樂事尚傳聞。今遭逢聖天子，` | `Những việc vui thuở xưa vẫn truyền nghe.` | Thiếu vế `今遭逢聖天子` (`nay gặp được bậc thánh thiên tử`). |
| `98` | `99` | `100` | `OMISSION` | `0.60 < 0.7 (3/5)` | `啞啞黃鸝佬。` | `Cùng bảo nhau:` | Lệch ranh giới `Oanh vàng líu lo`. |
| `100` | `101` | `102` | `OMISSION` | `0.62 < 0.7 (5/8)` | `春主今歸兮如何好。` | `Cảnh sắc như thế này,` | Kiểm tra nối với dòng `100–102`. |
| `124` | `125` | `126` | `OMISSION` | `0.57 < 0.7 (4/7)` | `起觀姑射落塵間，` | `Nằm làm sao yên` | Lệch 1 dòng trên `Dịch nghĩa` (dòng `125` là câu trên `Dịch thơ` có ghi `Dậy xem mai rụng xuống trần gian`). |
| `159` | `160` | `161` | `OMISSION` | `0.69 < 0.7 (9/13)` | `共遊追想始交時，不禁暮春相憶。` | `Chẳng ngăn được nỗi nhớ nhau lúc cuối xuân` | Thiếu vế đầu `Cùng dạo chơi nhớ lại thuở mới kết giao`. |
| `264` | `265` | `266` | `OMISSION` | `0.40 < 0.7 (2/5)` | `雲路戟枝寒。` | `Hoa xuân,` | Lệch ranh giới câu ngắn trong điệu từ. |
| `306` | `307` | `308` | `OMISSION` | `0.67 < 0.7 (8/12)` | `跨了龍門萬丈瀾。步月甲枝攀，` | `Rảo bước dưới trăng, vin cành cao nhất,` | Thiếu vế `跨了龍門萬丈瀾` (dịch thơ có đủ `Vượt khỏi Long môn lớp sóng tràn`). |
| `360` | `361` | `362` | `OMISSION` | `0.57 < 0.7 (4/7)` | `離別後卻為君攀。` | `Lúc buồn đứt ruột,` | Lệch 1 dòng với `Dịch nghĩa` (cột `Dịch thơ` đúng: `Chia biệt rồi, vì chàng mà vin`). |
| `363` | `364` | `365` | `OMISSION`, `NUMBER_MISMATCH` | `0.40 < 0.7 (2/5)`; thiếu `五` | `不睡五更闌。` | `Thời gian,` | Khả năng tiêu đề/chữ Hán dòng trên bị tách lệch với `Thời quang` $\rightarrow$ rà lại đoạn *Khuê oán*. |
| `367` | `368` | `369` | `NUMBER_MISMATCH` | thiếu `千` | `秋滿千山。` | `Đúng lúc muốn gửi áo chiến chinh,` | Lệch 1 dòng so với `正戎衣欲寄` (do cột `Dịch nghĩa` bị đẩy từ dòng trên). |
| `379` | `380` | `381` | `OMISSION` | `0.67 < 0.7 (8/12)` | `不奈朔風寒。料想黃雲征戰地，` | `Gió bắc lạnh chẳng biết phải làm sao.` | Thiếu vế sau `料想黃雲征戰地` (cột `Dịch thơ` có đủ `Nghĩ đến mây vàng nơi chiến địa`). |

---

## 5. Quy Trình Sửa Lỗi Nhanh Bằng CAT Workbench

1. Khởi chạy giao diện đối chiếu ảnh scan gốc:
   ```bash
   streamlit run web_app/app.py
   ```
2. Chọn bộ sách cần hiệu đính và nhập số dòng TSV tương ứng ở bảng trên để **Edit / Split / Merge / Insert / Delete**.
3. Lưu thay đổi qua `src/workbench_editor.py::save_and_reexport_corpus` để đồng bộ tự động `.tsv`, `.xlsx` (2 sheet `DONG_HANG`, `THONG_KE`) và `qa_report.json`.
