#!/usr/bin/env python3
"""End-to-End Pilot Runner for the Hán–Việt Parallel Corpus Alignment Pipeline.

Executes Steps 3–8 of Guideline.pdf on real pilot pages across all 3 books:
1. `HVTT_HanVanTinhTuy` (Hán Văn Tinh Túy — Lãng Nhân)
2. `TVLT2_ThoVanLyTran2` (Thơ văn Lý – Trần Tập II — Nguyễn Huệ Chi chủ biên)
3. `TLTVN_TheLoaiTuVN` (Thể loại từ Việt Nam thời trung đại — Nguyễn Xuân Diện, Nguyễn Quảng Tuân)

Generates:
- `deliverables/<BOOK>/02_ocr_tho/{han,viet}/*.json` (via `kaggle_ocr/ocr_pipeline_kaggle.py --dry-run`)
- `deliverables/<BOOK>/03_text_sach/{han.txt,viet.txt}`
- `deliverables/<BOOK>/04_dong_hang/<BOOK>_parallel.tsv`
- `deliverables/<BOOK>/04_dong_hang/<BOOK>_parallel.xlsx` (`DONG_HANG` + `THONG_KE` sheets)
- `deliverables/<BOOK>/04_dong_hang/qa_report.json`
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from kaggle_ocr import ocr_pipeline_kaggle
from src.aligner import (
    align_interlinear_4col_blocks,
    align_interlinear_blocks,
    align_work_sentences,
)
from src.exporter_and_qa import (
    export_tsv,
    export_xlsx_zero_dep,
    read_tsv,
    read_xlsx_zero_dep,
    validate_pairs,
)
from src.ocr_disambiguator import correct_han_line_with_phien_am
from src.phonetic_verifier import (
    project_punctuation_from_phien_am,
    verify_han_phien_am_pair,
)
from src.text_cleaner import (
    clean_han_text,
    clean_viet_text,
    split_han_sentences,
    split_viet_sentences,
)


# ---------------------------------------------------------------------------
# Authentic Pilot Data Extracted from the Rendered Pilot Pages (01_nguon/)
# ---------------------------------------------------------------------------

# 1. HVTT (Hán Văn Tinh Túy - PDF pages 0008, 0010, 0012 / Book pages 2, 4, 6: Tử Sản luận chính)
HVTT_PILOT_BLOCKS: List[Dict[str, str]] = [
    {
        "page": "0008",
        "han": "鄭 子 產 有 疾 謂 子 太 叔 曰",
        "phien_am": "Trịnh Tử-Sản hữu tật, vị tử Thái-Thúc viết :",
        "dich_nghia": "Trịnh Tử-Sản bệnh nặng, bảo con là Thái-Thúc rằng :",
    },
    {
        "page": "0008",
        "han": "我 死 子 必 爲 政",
        "phien_am": "Ngã tử, tử tất vi chính.",
        "dich_nghia": "Ta chết, con sẽ giữ chính-quyền.",
    },
    {
        "page": "0008",
        "han": "惟 有 德 者 能 以 寬 服 民",
        "phien_am": "Duy hữu đức giả, năng dĩ khoan phục dân,",
        "dich_nghia": "Chỉ kẻ có đức mới có thể lấy khoan hòa cho dân phục,",
    },
    {
        "page": "0008",
        "han": "其 次 莫 如 猛",
        "phien_am": "Kỳ thứ mạc như mãnh.",
        "dich_nghia": "còn thì không gì bằng chính-sách mạnh.",
    },
    {
        "page": "0008",
        "han": "夫 火 烈 民 望 而 畏 之 故 鮮 死 焉",
        "phien_am": "Phù hỏa liệt, dân vọng nhi úy chi, cố tiển tử yên.",
        "dich_nghia": "Như lửa cháy, dân trông là sợ, nên ít kẻ chết vì lửa.",
    },
    {
        "page": "0008",
        "han": "水 懦 弱 民 狎 而 翫 之 則 多 死 焉",
        "phien_am": "Thủy nhu nhược, dân hạp nhi ngoạn chi, tắc đa tử yên.",
        "dich_nghia": "Nước mềm yếu, dân ưa đùa-rỡn, nên chết nhiều.",
    },
    {
        "page": "0008",
        "han": "故 寬 難",
        "phien_am": "Cố khoan nan.",
        "dich_nghia": "Vì thế khoan hồng là khó.",
    },
    {
        "page": "0008",
        "han": "疾 數 月 而 卒 太 叔 爲 政",
        "phien_am": "Tật sổ nguyệt nhi tốt, Thái-Thúc vi chính.",
        "dich_nghia": "Đau mấy tháng rồi chết, Thái-Thúc lên cầm quyền.",
    },
    {
        "page": "0010",
        "han": "不 忍 猛 而 寬",
        "phien_am": "Bất nhẫn mãnh nhi khoan.",
        "dich_nghia": "Không nỡ mạnh nên khoan hòa.",
    },
    {
        "page": "0010",
        "han": "鄭 國 多 盜",
        "phien_am": "Trịnh-quốc đa đạo.",
        "dich_nghia": "Nước Trịnh nhiều trộm cướp.",
    },
    {
        "page": "0010",
        "han": "取 人 於 萑 苻 之 澤",
        "phien_am": "Thủ nhân ư hoàn bồ chi trạch.",
        "dich_nghia": "Bắt người lương thiện ở nơi bãi chằm um tùm.",
    },
    {
        "page": "0010",
        "han": "太 叔 悔 之 曰",
        "phien_am": "Thái-Thúc hối chi, viết :",
        "dich_nghia": "Thái-Thúc ăn-năn, nói :",
    },
    {
        "page": "0010",
        "han": "吾 早 從 夫 子 不 及 此",
        "phien_am": "Ngô tảo tòng phu-tử, bất cập thử.",
        "dich_nghia": "Ta sớm biết theo lời cha đâu đến nỗi này.",
    },
    {
        "page": "0010",
        "han": "興 徒 兵 以 攻 萑 苻 之 盜",
        "phien_am": "Hưng đồ binh dĩ công hoàn bồ chi đạo.",
        "dich_nghia": "Đem binh đi tiễu trừ trộm cướp.",
    },
    {
        "page": "0010",
        "han": "盡 殺 之 盜 少 止",
        "phien_am": "Tận sát chi. Đạo thiểu chỉ.",
        "dich_nghia": "Giết hết. Cướp trộm yên.",
    },
    {
        "page": "0010",
        "han": "仲 尼 曰 善 哉",
        "phien_am": "Trọng-Ni viết : Thiện tai !",
        "dich_nghia": "Khổng-tử nói : Giỏi thay !",
    },
    {
        "page": "0012",
        "han": "政 寬 則 民 慢",
        "phien_am": "Chính khoan tắc dân mạn,",
        "dich_nghia": "Chính sách khoan hòa dân nhờn,",
    },
    {
        "page": "0012",
        "han": "慢 則 糾 之 以 猛",
        "phien_am": "mạn tắc củ chi dĩ mãnh.",
        "dich_nghia": "nhờn thì lấy « mạnh » (thẳng tay) mà đàn áp.",
    },
    {
        "page": "0012",
        "han": "猛 則 民 殘 殘 則 施 之 以 寬",
        "phien_am": "Mãnh tắc dân tàn, tàn tắc thi chi dĩ khoan.",
        "dich_nghia": "Mạnh tất dân hại, hại thì lại lấy khoan mà thi-hành.",
    },
    {
        "page": "0012",
        "han": "寬 以 濟 猛 猛 以 濟 寬",
        "phien_am": "Khoan dĩ tế mãnh, mãnh dĩ tế khoan.",
        "dich_nghia": "Khoan để đỡ mạnh, mạnh để đỡ khoan.",
    },
    {
        "page": "0012",
        "han": "政 是 以 和",
        "phien_am": "Chính thị dĩ hòa.",
        "dich_nghia": "Chính sự sẽ hòa.",
    },
    {
        "page": "0012",
        "han": "詩 曰 民 亦 勞 止 汔 可 小 康",
        "phien_am": "Thi viết : dân diệc lao chỉ, ngật khả tiểu-khang.",
        "dich_nghia": "Kinh thi nói : dân đỡ vất-vả, để tạm yên vui.",
        "dich_tho": "Dân vất-vả, ngõ hầu yên-ổn,",
    },
    {
        "page": "0012",
        "han": "惠 此 中 國 以 綏 四 方",
        "phien_am": "Huệ thử trung-quốc, dĩ tuy tứ phương.",
        "dich_nghia": "Ra ơn trong nước, để yên bốn phương.",
        "dich_tho": "Ơn ban ra vỗ-về bốn phương.",
    },
    {
        "page": "0012",
        "han": "施 之 以 寬 也",
        "phien_am": "Thi chi dĩ khoan dã.",
        "dich_nghia": "Ấy là lấy « khoan » mà thi-hành vậy.",
        "dich_tho": "",
    },
    # Bài cuối (PDF 367-381: Thu dạ hoài ngâm - Kỳ Đồng): chỉ có Hán - Dịch âm - Dịch thơ, cột Dịch nghĩa để trống
    {
        "page": "0368",
        "han": "天 氣 入 中 秋 之 夜 蕭 條 經 四 坐 霜 寒",
        "phien_am": "Thiên khí nhập trung-thu chi dạ, Tiêu-điều kinh tứ tọa sương hàn.",
        "dich_nghia": "",
        "dich_tho": "Đêm trung-thu trời mây trong trẻo, Sương đầm đầm lạnh lẽo bốn bên.",
    },
    {
        "page": "0368",
        "han": "仙 家 別 占 清 閒 打 殘 棋 陣 飲 殘 菊 杯",
        "phien_am": "Tiên gia biệt chiếm thanh-nhàn, Đả tàn kỳ trận, ẩm tàn cúc bôi !",
        "dich_nghia": "",
        "dich_tho": "Thanh-nhàn riêng một cảnh tiên, Mảng vui cờ thánh rượu hiền tiêu-dao !",
    },
]

# 2. TLTVN (Thể loại từ VN thời trung đại - PDF pages 0134..0137 / Book pages 127..130: Nguyễn lang quy)
TLTVN_PILOT_WORKS: List[Dict[str, Any]] = [
    {
        "work_id": "TLTVN_001_NguyenLangQuy",
        "title": "Nguyễn lang quy (Ngô Chân Lưu)",
        "clauses": [
            {
                "han": "祥光風好錦帆張, 神仙復帝鄉.",
                "phien_am": "Tường quang phong hảo cẩm phàm trương, Thần tiên phục đế hương².",
                "dich_nghia": "Ánh sáng tốt lành, gió thuận, căng cánh buồm gấm, Thần tiên trở về quê hương của hoàng đế⁵.",
            },
            {
                "han": "千重萬里涉滄浪, 九天歸路長.",
                "phien_am": "Thiên trùng vạn lí¹ thiệp thương lương, Cửu thiên quy lộ trường.",
                "dich_nghia": "Nghìn trùng muôn dặm vượt qua những làn sóng xanh, Đường qua về chín tầng trời¹.",
            },
            {
                "han": "情慘切, 對離觴, 攀戀使星郎.",
                "phien_am": "Tình thảm thiết², Đối li thương, Phan luyến sứ tinh lang³.",
                "dich_nghia": "Tình thảm thiết, Đối diện với chén rượu biệt li, Yêu mến vin lấy chàng sứ giả.",
            },
            {
                "han": "願將深意為南疆, 分明報我皇.",
                "phien_am": "Nguyện tương thâm ý vị Nam cương, Phân minh báo⁴ ngã hoàng.",
                "dich_nghia": "Xin hãy đem cái ý sâu xa vì biên cương phía Nam, Báo rõ cho nhà vua của chúng ta.",
            },
        ],
    }
]

# 3. TVLT2 (Thơ văn Lý Trần 2 - PDF pages 0019..0020 / Book pages 21..22: Trần Thái Tông)
TVLT2_PILOT_WORKS: List[Dict[str, Any]] = [
    {
        "work_id": "TVLT2_001_KyThanhPhongAmTangDucSon",
        "title": "Ký Thanh Phong am tăng Đức Sơn (Trần Thái Tông)",
        "clauses": [
            {
                "han": "風打松關月照庭，心期風景共淒清。",
                "phien_am": "Phong đả tùng quan 1* nguyệt chiếu đình, Tâm kỳ phong cảnh cộng thê thanh.",
                "dich_nghia": "DỊCH NGHĨA : Gió đập cổng thông, trăng sáng trước sân, Lòng hẹn với phong cảnh cùng trong sạch lặng lẽ.",
            },
            {
                "han": "箇中滋味無人識，付與山僧樂到明。",
                "phien_am": "Cá trung tư vị vô nhân thức, Phó dữ sơn tăng lạc đáo minh.",
                "dich_nghia": "Bao nhiêu thú vị trong đó không ai hay, Mặc cho nhà sư trong núi vui đến sáng.",
            },
        ],
    },
    {
        "work_id": "TVLT2_002_TongBacSuTruongHienKhanh",
        "title": "Tống Bắc sứ Trương Hiển Khanh (Trần Thái Tông)",
        "clauses": [
            {
                "han": "顧無瓊報自懷慚，極目江皋意不堪。",
                "phien_am": "Cố 1* vô quỳnh báo tự hoài tàm, Cực mục giang cao ý bất kham.",
                "dich_nghia": "Nghĩ không có ngọc quỳnh (2) đáp lại, lòng tự thẹn. Trên bờ sông nhìn xa mãi xiết bao bùi ngùi.",
            },
            {
                "han": "馬首秋風吹劍鋏，屋梁落月照書庵。",
                "phien_am": "Mã thủ thu phong xuy kiếm giáp, Ốc lương lạc nguyệt 2* chiếu thư am.",
                "dich_nghia": "Gió thu trước đầu ngựa thổi vào thanh gươm, Ánh trăng lọt qua rường nhà (3) dọi vào phòng sách.",
            },
            {
                "han": "幕空難駐燕歸北，地暖愁聞雁別南。",
                "phien_am": "Mạc 3* không nan trụ 4* yến quy Bắc, Địa noãn 5* sầu văn nhạn biệt Nam.",
                "dich_nghia": "Màn trống khó ngăn chim én về phương Bắc, Đất ấm buồn nghe chim nhạn biệt phương Nam.",
            },
            {
                "han": "此去未知傾蓋日，詩篇聊為當清談。",
                "phien_am": "Thử khứ vị tri khuynh cái nhật, Thi thiên 6* liêu vị 7* đáng thanh 8* đàm.",
                "dich_nghia": "Lần đi này chưa biết ngày nào mới có dịp nghiêng lọng (4), Xin vì cuộc chuyện trò tao nhã mà có một bài thơ.",
            },
        ],
    },
    {
        "work_id": "TVLT2_003_ThienTongChiNamTu",
        "title": "Thiền tông chỉ nam tự (Trần Thái Tông - bổ sung bản dịch nghĩa từ Giảng viên cho trang PDF 25 bị trắng)",
        "supplement_file": "deliverables/TVLT2_ThoVanLyTran2/01_nguon/bai_03_thien_tong_chi_nam_tu_dich_nghia.txt",
        "clauses": [
            {
                "han": "朕竊謂佛無南北均可修求，性有智愚同資覺悟。",
                "phien_am": "Trẫm thiết vị : Phật vô Nam Bắc, quân khả tu cầu ; tính hữu trí ngu, đồng tư giác ngộ.",
                "dich_nghia": "Trẫm thầm nghĩ: Phật không có nam bắc, mọi người đều có thể tu cầu. Tánh có trí ngu, đồng sẵn giác ngộ.",
            },
            {
                "han": "是以誘群迷之方便，明生死之捷徑者，我佛之大教也；任垂世之權衡，作將來之軌範者，先聖之重責也。",
                "phien_am": "Thị dĩ dụ quần mê chi phương-tiện, minh sinh tử chi tiệp kính giả, ngã Phật chi đại giáo dã ; nhậm thùy thế chi quyền hành, tác tương lai chi quỹ phạm giả, tiên thánh chi trọng trách 1* dã.",
                "dich_nghia": "Vì vậy, phương tiện dẫn dụ đám người mê, để sáng tỏ đường tắt sanh tử, là kinh điển của đức Phật chúng ta. Đặt mực thước cho đời, làm mô phạm người sau, là trọng trách các bậc Thánh trước (Tổ).",
            },
            {
                "han": "故六祖有言云：先大聖人與大師無別，則知我佛之教，又假先聖人以傳於世也。今朕焉可不以先聖之任為己之任，我佛之教為己之教哉！",
                "phien_am": "Cố Lục Tổ hữu ngôn vân : Tiên đại thánh nhân dữ đại sư vô biệt, tắc tri ngã Phật chi giáo hựu giả tiên thánh nhân dĩ truyền ư thế dã. Kim trẫm yên khả bất dĩ tiên thánh chi nhậm vi kỷ chi nhậm, ngã Phật chi giáo vi kỷ chi giáo tai !",
                "dich_nghia": "Cho nên Lục Tổ nói: Những bậc Thánh trước (Tổ) cùng Đại sư (Phật) không khác. Nên biết giáo pháp của Phật nhờ các bậc Thánh trước truyền bá ở đời. Nay Trẫm đâu thể không lấy trách nhiệm các bậc Thánh trước làm trách nhiệm của mình, giáo pháp của Phật làm giáo pháp của mình.",
            },
            {
                "han": "且朕於孩童有識之年，稍聞禪師之訓，則澄思息慮，慨然清淨，有心乎內教，參究於禪宗，虛己求師，精誠慕道。雖回向之意已萌，而感觸之機未達。",
                "phien_am": "Thả trẫm ư hài đồng hữu thức chi niên, sảo văn Thiền sư chi huấn, tắc trừng tư tức lự, khái nhiên thanh tịnh, hữu tâm hồ nội giáo, tham cứu ư Thiền tông, hư kỷ cầu sư, tinh thành mộ đạo. Tuy hồi hướng chi ý dĩ manh, nhi cảm xúc chi cơ vị đạt.",
                "dich_nghia": "Vả lại, thuở Trẫm còn niên thiếu có chút ít hiểu biết, vừa nghe lời dạy của Thiền sư thì tâm tư lóng lặng, bỗng dưng thanh tịnh; nên để tâm nơi nội giáo, tham cứu Thiền tông, dốc lòng tìm thầy, chí thành mộ đạo. Tuy ý hồi hướng đã nảy mầm, mà cơ cảm xúc chưa thấu suốt.",
            },
            {
                "han": "師曰：山本無佛，惟存乎心。心寂而知，是名真佛。今陛下若悟此心，則立地成佛，無苦外求也。",
                "phien_am": "Sư viết : Sơn bản vô Phật, duy tồn hồ tâm. Tâm tịch nhi tri, thị danh Chân Phật. Kim Bệ hạ nhược ngộ thử tâm, tắc lập địa thành Phật, vô khổ ngoại cầu dã.",
                "dich_nghia": "Sư bảo: Trong núi vốn không có Phật, Phật chỉ ở trong tâm. Tâm lặng mà biết gọi là Chân Phật. Nay Bệ hạ nếu ngộ tâm này thì tức khắc thành Phật, không nhọc tìm cầu bên ngoài.",
            },
            {
                "han": "朕聞是言，乃命工楷寫，敕令開印，非特以為後世指迷，蓋欲繼先代聖人之功廣，因自為序云。",
                "phien_am": "Trẫm văn thị ngôn, nãi mệnh công khải tả, sắc lệnh khai ấn, phi đặc dĩ vi hậu thế chỉ mê, cái dục kế tiên đại thánh nhân chi công quảng, nhân tự vi tự vân.",
                "dich_nghia": "Trẫm nghe lời này, sai thợ viết chữ chân phương, ra lệnh khắc bản in. Chẳng những để chỉ đường mê cho hậu thế, mà còn muốn tiếp nối công lớn các bậc Thánh nhân đời trước. Vì thế tự làm lời tựa này.",
            },
        ],
    },
]


def _write_clean_text_files(clean_dir: Path, pairs: List[Tuple[str, ...]]) -> Tuple[Path, Path]:
    """Write `03_text_sach/han.txt` and `03_text_sach/viet.txt`."""
    clean_dir.mkdir(parents=True, exist_ok=True)
    han_txt = clean_dir / "han.txt"
    viet_txt = clean_dir / "viet.txt"
    han_lines: List[str] = []
    viet_lines: List[str] = []
    for row in pairs:
        han_lines.append(row[0])
        if len(row) >= 4:
            viet_lines.append(row[2] if row[2].strip() else row[3])
        else:
            viet_lines.append(row[1])
    han_txt.write_text("\n".join(han_lines) + "\n", encoding="utf-8")
    viet_txt.write_text("\n".join(viet_lines) + "\n", encoding="utf-8")
    return han_txt, viet_txt


def run_pilot_pipeline(workspace_root: Path = ROOT_DIR) -> Dict[str, Any]:
    """Execute the full pilot pipeline across all 3 books and return QA summary."""
    manifest_path = workspace_root / "config" / "book_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    books_cfg = manifest["books"]

    summary: Dict[str, Any] = {"books": {}}

    # 1. Run kaggle_ocr/ocr_pipeline_kaggle.py in --dry-run mode on each book's 01_nguon/
    for book_key, cfg in books_cfg.items():
        book_root = workspace_root / cfg["deliverable_dir"]
        source_dir = workspace_root / cfg["source_dir"]
        rc = ocr_pipeline_kaggle.main([
            "--input-dir", str(source_dir),
            "--output-dir", str(book_root),
            "--book-type", book_key,
            "--max-pages", "10",
            "--dry-run",
        ])
        if rc != 0:
            raise RuntimeError(f"ocr_pipeline_kaggle failed for {book_key} with exit code {rc}")

    # 2. Process HVTT (Hán Văn Tinh Túy): 4-column structure (Hán - Dịch âm - Dịch nghĩa - Dịch thơ)
    hvtt_cfg = books_cfg["HVTT"]
    hvtt_projected_blocks: List[Dict[str, str]] = []
    hvtt_phonetic_checks: List[Dict[str, Any]] = []
    for blk in HVTT_PILOT_BLOCKS:
        # Step A: Disambiguate Han characters using Phien Am phonetic reading
        corrected_han, _ = correct_han_line_with_phien_am(blk["han"], blk["phien_am"])
        ver = verify_han_phien_am_pair(corrected_han, blk["phien_am"])
        hvtt_phonetic_checks.append(ver)
        punct_han = project_punctuation_from_phien_am(corrected_han, blk["phien_am"])
        hvtt_projected_blocks.append({
            "han": punct_han,
            "dich_am": blk["phien_am"],
            "dich_nghia": blk.get("dich_nghia", ""),
            "dich_tho": blk.get("dich_tho", ""),
        })

    hvtt_pairs = align_interlinear_4col_blocks(hvtt_projected_blocks)

    # 3. Process TLTVN (Thể loại từ VN thời trung đại): Phonetic verification + Work-bounded alignment
    tltvn_cfg = books_cfg["TLTVN"]
    tltvn_pairs: List[Tuple[str, str]] = []
    tltvn_phonetic_checks: List[Dict[str, Any]] = []
    for work in TLTVN_PILOT_WORKS:
        han_sents: List[str] = []
        viet_sents: List[str] = []
        for clause in work["clauses"]:
            corrected_han, _ = correct_han_line_with_phien_am(clause["han"], clause["phien_am"])
            ver = verify_han_phien_am_pair(corrected_han, clause["phien_am"])
            tltvn_phonetic_checks.append(ver)
            han_sents.append(clean_han_text(corrected_han))
            viet_sents.append(clean_viet_text(clause["dich_nghia"]))
        aligned = align_work_sentences(han_sents, viet_sents)
        for item in aligned:
            tltvn_pairs.append((item["han"], item["viet"]))

    # 4. Process TVLT2 (Thơ văn Lý Trần 2): Phonetic verification + Work-bounded alignment
    tvlt2_cfg = books_cfg["TVLT2"]
    tvlt2_pairs: List[Tuple[str, str]] = []
    tvlt2_phonetic_checks: List[Dict[str, Any]] = []
    for work in TVLT2_PILOT_WORKS:
        han_sents = []
        viet_sents = []
        for clause in work["clauses"]:
            corrected_han, _ = correct_han_line_with_phien_am(clause["han"], clause["phien_am"])
            ver = verify_han_phien_am_pair(corrected_han, clause["phien_am"])
            tvlt2_phonetic_checks.append(ver)
            han_sents.append(clean_han_text(corrected_han))
            viet_sents.append(clean_viet_text(clause["dich_nghia"]))
        aligned = align_work_sentences(han_sents, viet_sents)
        for item in aligned:
            tvlt2_pairs.append((item["han"], item["viet"]))

    book_datasets = {
        "HVTT": (hvtt_cfg, hvtt_pairs, hvtt_phonetic_checks),
        "TLTVN": (tltvn_cfg, tltvn_pairs, tltvn_phonetic_checks),
        "TVLT2": (tvlt2_cfg, tvlt2_pairs, tvlt2_phonetic_checks),
    }

    for book_key, (cfg, pairs, phon_checks) in book_datasets.items():
        code = cfg["code"]
        clean_dir = workspace_root / cfg["clean_text_dir"]
        align_dir = workspace_root / cfg["alignment_dir"]
        align_dir.mkdir(parents=True, exist_ok=True)

        han_txt_path, viet_txt_path = _write_clean_text_files(clean_dir, pairs)
        qa_report = validate_pairs(pairs)

        tsv_path = align_dir / f"{code}_parallel.tsv"
        xlsx_path = align_dir / f"{code}_parallel.xlsx"
        qa_json_path = align_dir / "qa_report.json"

        export_tsv(pairs, str(tsv_path))
        export_xlsx_zero_dep(
            pairs,
            str(xlsx_path),
            stats={
                "Mã tài liệu": code,
                "Tổng số cặp câu": qa_report["total_pairs"],
                "Số cặp hợp lệ": qa_report["valid_pairs"],
                "Số cặp lỗi": qa_report["error_pairs"],
                "Tỷ lệ lỗi": qa_report["error_rate"],
                "Đạt ngưỡng <= 20%": qa_report["passes_target_20pct"],
                "Đạt ngưỡng nghiệm thu <= 30%": qa_report["passes_threshold_30pct"],
            },
        )
        qa_json_path.write_text(
            json.dumps(qa_report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Verify 100% round-trip content identity between .tsv and .xlsx (DONG_HANG sheet)
        tsv_roundtrip = read_tsv(str(tsv_path))
        xlsx_roundtrip = read_xlsx_zero_dep(str(xlsx_path), sheet_name="DONG_HANG")
        if tsv_roundtrip != xlsx_roundtrip:
            raise AssertionError(
                f"Mismatch between TSV and XLSX DONG_HANG for {code}: "
                f"{len(tsv_roundtrip)} vs {len(xlsx_roundtrip)}"
            )

        summary["books"][book_key] = {
            "code": code,
            "pair_count": len(pairs),
            "phonetic_all_matched": all(
                c["length_match"] and len(c["phonetic_mismatches"]) == 0
                for c in phon_checks
            ),
            "error_rate": qa_report["error_rate"],
            "is_valid": qa_report["is_valid"],
            "tsv_xlsx_identical": tsv_roundtrip == xlsx_roundtrip,
            "han_txt": str(han_txt_path),
            "viet_txt": str(viet_txt_path),
            "tsv_path": str(tsv_path),
            "xlsx_path": str(xlsx_path),
        }

    return summary


if __name__ == "__main__":
    result = run_pilot_pipeline()
    print(json.dumps(result, ensure_ascii=False, indent=2))
