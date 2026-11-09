"""Sino-Vietnamese (Hán–Việt) phonetic verification and punctuation projection.

Provides deterministic character-to-syllable verification between Classical Chinese
(`Chữ Hán`) strings and Vietnamese Sino-Vietnamese (`Phiên âm Hán–Việt`) transcriptions,
as well as automatic punctuation projection from `Phiên âm` onto unpunctuated `Chữ Hán`
(such as in *Hán Văn Tinh Túy*).

Uses only the Python 3 standard library so it can run in any local or cloud environment.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union


# CJK Unified Ideographs Unicode code-point intervals (including Extensions A–I & Compatibility)
CJK_RANGES: Tuple[Tuple[int, int], ...] = (
    (0x3400, 0x4DBF),    # CJK Unified Ideographs Extension A
    (0x4E00, 0x9FFF),    # CJK Unified Ideographs (Core)
    (0xF900, 0xFAFF),    # CJK Compatibility Ideographs
    (0x20000, 0x2A6DF),  # CJK Unified Ideographs Extension B
    (0x2A700, 0x2B73F),  # CJK Unified Ideographs Extension C
    (0x2B740, 0x2B81F),  # CJK Unified Ideographs Extension D
    (0x2B820, 0x2CEAF),  # CJK Unified Ideographs Extension E
    (0x2CEB0, 0x2EBEF),  # CJK Unified Ideographs Extension F
    (0x2EBF0, 0x2EE5F),  # CJK Unified Ideographs Extension I
    (0x2F800, 0x2FA1F),  # CJK Compatibility Ideographs Supplement
    (0x30000, 0x3134F),  # CJK Unified Ideographs Extension G
    (0x31350, 0x323AF),  # CJK Unified Ideographs Extension H
)

# Mapping from Latin punctuation in Phiên âm to fullwidth CJK punctuation in Chữ Hán
PUNCTUATION_PROJECTION_MAP: Dict[str, str] = {
    ",": "，",
    ".": "。",
    "?": "？",
    "!": "！",
    ";": "；",
    ":": "：",
}

# Set of punctuation characters that indicate a Han string is already punctuated
EXISTING_HAN_PUNCTUATION: Set[str] = set("，。？！；：、,.?!;:")

# Built-in core lookup dictionary mapping Classical Chinese characters (Traditional,
# Simplified, and Japanese/Variant forms found in Vietnamese editions) to their accepted
# Sino-Vietnamese (Hán–Việt) readings in lowercase NFC form.
CORE_HAN_VIET_DICT: Dict[str, List[str]] = {
    # Classical particles & function words
    "之": ["chi"],
    "乎": ["hồ"],
    "者": ["giả"],
    "也": ["dã"],
    "矣": ["hĩ"],
    "焉": ["yên", "ức"],
    "哉": ["tai"],
    "不": ["bất", "bưu", "phầu"],
    "無": ["vô", "mô"],
    "无": ["vô", "mô"],
    "有": ["hữu", "hựu"],
    "則": ["tắc"],
    "则": ["tắc"],
    "而": ["nhi", "năng"],
    "以": ["dĩ"],
    "於": ["ư", "ô"],
    "于": ["vu", "ư"],
    "為": ["vi", "vị"],
    "爲": ["vi", "vị"],
    "为": ["vi", "vị"],
    "曰": ["viết"],
    "云": ["vân"],
    "與": ["dữ", "dự", "dư"],
    "与": ["dữ", "dự", "dư"],
    "及": ["cập"],
    "若": ["nhược", "nhã"],
    "如": ["như"],
    "何": ["hà", "hạ"],
    "安": ["an", "yên"],
    "豈": ["khởi", "khải"],
    "岂": ["khởi", "khải"],
    "蓋": ["cái", "hạp"],
    "盖": ["cái", "hạp"],
    "夫": ["phu", "phù"],
    "惟": ["duy"],
    "唯": ["duy", "dụ"],
    "雖": ["tuy"],
    "虽": ["tuy"],
    "然": ["nhiên"],
    "故": ["cố"],
    "是以": ["thị dĩ"],
    "是": ["thị"],
    "非": ["phi"],
    "莫": ["mạc", "mộ"],
    "勿": ["vật"],
    "毋": ["vô", "mưu"],
    "未": ["vị", "mùi"],
    "既": ["ký", "kí"],
    "旣": ["ký", "kí"],
    "皆": ["giai"],
    "俱": ["câu", "cụ"],
    "各": ["các"],
    "凡": ["phàm"],
    "或": ["hoặc"],
    "乃": ["nãi"],
    "即": ["tức"],
    "卽": ["tức"],
    "將": ["tương", "tướng"],
    "将": ["tương", "tướng"],
    "且": ["thả", "thư"],
    "亦": ["diệc", "dịch"],
    "又": ["hựu"],
    "復": ["phục", "phù"],
    "复": ["phục", "phù"],
    "遂": ["toại"],
    "因": ["nhân"],
    "由": ["do"],
    "自": ["tự"],
    "從": ["tùng", "tòng", "thung"],
    "从": ["tùng", "tòng", "thung"],
    "向": ["hướng"],
    "在": ["tại"],
    "當": ["đương", "đáng"],
    "当": ["đương", "đáng"],
    "所": ["sở"],
    "所以": ["sở dĩ"],
    "其": ["kỳ", "kì", "cơ"],
    "此": ["thử"],
    "彼": ["bỉ"],
    "斯": ["tư"],
    "茲": ["tư", "từ"],
    "兹": ["tư", "từ"],
    "爾": ["nhĩ"],
    "尔": ["nhĩ"],
    "汝": ["nhữ"],
    "吾": ["ngô"],
    "我": ["ngã"],
    "予": ["dư", "dữ"],
    "余": ["dư"],
    "朕": ["trẫm"],
    "誰": ["thùy", "thuỳ"],
    "孰": ["thục"],
    # Governance, society, humanity, philosophy (incl. Hán Văn Tinh Túy / Tử Sản)
    "人": ["nhân"],
    "民": ["dân"],
    "政": ["chính", "chánh", "chinh"],
    "寬": ["khoan"],
    "宽": ["khoan"],
    "猛": ["mãnh"],
    "國": ["quốc"],
    "国": ["quốc"],
    "天": ["thiên"],
    "地": ["địa"],
    "王": ["vương", "vượng"],
    "皇": ["hoàng"],
    "帝": ["đế"],
    "君": ["quân"],
    "臣": ["thần"],
    "父": ["phụ", "phủ"],
    "母": ["mẫu"],
    "子": ["tử", "tý", "tí"],
    "女": ["nữ", "nhữ"],
    "男": ["nam"],
    "兄": ["huynh"],
    "弟": ["đệ", "đễ"],
    "友": ["hữu"],
    "師": ["sư"],
    "师": ["sư"],
    "士": ["sĩ", "sỹ"],
    "農": ["nông"],
    "工": ["công"],
    "商": ["thương"],
    "兵": ["binh"],
    "將": ["tướng", "tương"],
    "相": ["tương", "tướng"],
    "官": ["quan"],
    "吏": ["lại"],
    "賢": ["hiền"],
    "贤": ["hiền"],
    "聖": ["thánh"],
    "圣": ["thánh"],
    "仁": ["nhân"],
    "義": ["nghĩa"],
    "义": ["nghĩa"],
    "禮": ["lễ"],
    "礼": ["lễ"],
    "智": ["trí"],
    "信": ["tín"],
    "忠": ["trung"],
    "孝": ["hiếu"],
    "節": ["tiết"],
    "节": ["tiết"],
    "廉": ["liêm"],
    "恥": ["sỉ"],
    "德": ["đức"],
    "徳": ["đức"],
    "善": ["thiện"],
    "惡": ["ác", "ố", "ô"],
    "恶": ["ác", "ố", "ô"],
    "正": ["chính", "chánh", "chinh"],
    "邪": ["tà", "gia"],
    "治": ["trị", "trì"],
    "亂": ["loạn"],
    "乱": ["loạn"],
    "興": ["hưng", "hứng"],
    "兴": ["hưng", "hứng"],
    "亡": ["vong", "vô"],
    "盛": ["thịnh", "thành"],
    "衰": ["suy", "thôi"],
    "成": ["thành"],
    "敗": ["bại"],
    "败": ["bại"],
    "勝": ["thắng", "thăng"],
    "胜": ["thắng", "thăng"],
    "負": ["phụ"],
    "负": ["phụ"],
    "生": ["sinh", "sanh"],
    "死": ["tử"],
    "老": ["lão"],
    "病": ["bệnh", "bịnh"],
    "疾": ["tật"],
    "鄭": ["trịnh"],
    "郑": ["trịnh"],
    "產": ["sản"],
    "産": ["sản"],
    "产": ["sản"],
    "謂": ["vị"],
    "谓": ["vị"],
    "太": ["thái"],
    "大": ["đại", "thái"],
    "小": ["tiểu"],
    "叔": ["thúc"],
    "必": ["tất"],
    "能": ["năng"],
    "服": ["phục"],
    "次": ["thứ"],
    "火": ["hỏa", "hoả"],
    "烈": ["liệt"],
    "望": ["vọng"],
    "畏": ["úy", "uý"],
    "鮮": ["tiên", "tiển"],
    "鲜": ["tiên", "tiển"],
    "懦": ["noãn", "nhu", "nhuyễn"],
    "弱": ["nhược"],
    "狎": ["hiệp", "hạp", "áp"],
    "翫": ["ngoạn"],
    "玩": ["ngoạn"],
    "多": ["đa"],
    "少": ["thiểu", "thiếu"],
    "難": ["nan", "nạn"],
    "难": ["nan", "nạn"],
    "易": ["dị", "dịch"],
    "數": ["sổ", "số", "sác", "xúc"],
    "数": ["sổ", "số", "sác", "xúc"],
    "卒": ["tốt", "thốt", "tụy"],
    "忍": ["nhẫn"],
    "盜": ["đạo"],
    "盗": ["đạo"],
    "萑": ["hoàn"],
    "苻": ["bồ", "phù"],
    "澤": ["trạch"],
    "泽": ["trạch"],
    "悔": ["hối"],
    "徒": ["đồ"],
    "攻": ["công"],
    "盡": ["tận"],
    "尽": ["tận"],
    "殺": ["sát", "sái"],
    "杀": ["sát", "sái"],
    "止": ["chỉ"],
    "仲": ["trọng"],
    "尼": ["ni"],
    "慢": ["mạn"],
    "糾": ["củ"],
    "纠": ["củ"],
    "殘": ["tàn"],
    "残": ["tàn"],
    "施": ["thi", "thí", "di"],
    "濟": ["tế", "tể"],
    "济": ["tế", "tể"],
    "和": ["hòa", "hoà", "họa", "hoạ"],
    "勞": ["lao", "lạo"],
    "劳": ["lao", "lạo"],
    "汔": ["ngật", "hất"],
    "可": ["khả", "khắc"],
    "康": ["khang"],
    "惠": ["huệ"],
    "綏": ["tuy", "thuy"],
    "绥": ["tuy", "thuy"],
    "方": ["phương"],
    # Buddhism, Zen, Daoism, Mind (Thơ văn Lý - Trần)
    "心": ["tâm"],
    "性": ["tính", "tánh"],
    "命": ["mệnh", "mạng"],
    "身": ["thân"],
    "體": ["thể"],
    "体": ["thể"],
    "神": ["thần"],
    "魂": ["hồn"],
    "魄": ["phách"],
    "氣": ["khí"],
    "气": ["khí"],
    "意": ["ý"],
    "念": ["niệm"],
    "思": ["tư", "tứ"],
    "想": ["tưởng"],
    "覺": ["giác", "giáo"],
    "觉": ["giác", "giáo"],
    "悟": ["ngộ"],
    "迷": ["mê"],
    "佛": ["phật", "bật", "phất"],
    "法": ["pháp"],
    "僧": ["tăng"],
    "道": ["đạo", "đáo"],
    "禪": ["thiền", "thiện"],
    "禅": ["thiền", "thiện"],
    "宗": ["tông", "tôn"],
    "教": ["giáo", "giao"],
    "經": ["kinh"],
    "经": ["kinh"],
    "論": ["luận", "luân"],
    "论": ["luận", "luân"],
    "戒": ["giới"],
    "定": ["định"],
    "慧": ["tuệ", "huệ"],
    "空": ["không", "khổng", "khống"],
    "色": ["sắc"],
    "相": ["tướng", "tương"],
    "真": ["chân", "chơn"],
    "眞": ["chân", "chơn"],
    "妄": ["vọng"],
    "幻": ["ảo", "huyễn"],
    "如來": ["như lai"],
    "來": ["lai", "lại"],
    "来": ["lai", "lại"],
    "去": ["khứ", "khử"],
    "往": ["vãng"],
    "還": ["hoàn", "hàn"],
    "还": ["hoàn", "hàn"],
    "塵": ["trần"],
    "尘": ["trần"],
    "世": ["thế"],
    "界": ["giới"],
    "俗": ["tục"],
    "凡": ["phàm"],
    "居": ["cư", "cơ"],
    "樂": ["lạc", "nhạc", "nhạo"],
    "乐": ["lạc", "nhạc", "nhạo"],
    "賦": ["phú"],
    "赋": ["phú"],
    "得": ["đắc"],
    "失": ["thất"],
    "趣": ["thú", "xúc"],
    "林": ["lâm"],
    "泉": ["tuyền"],
    "歌": ["ca"],
    "曲": ["khúc"],
    "詞": ["từ"],
    "词": ["từ"],
    "詩": ["thi"],
    "诗": ["thi"],
    "文": ["văn", "vấn"],
    "書": ["thư"],
    "书": ["thư"],
    "字": ["tự"],
    "言": ["ngôn"],
    "語": ["ngữ", "ngự"],
    "语": ["ngữ", "ngự"],
    "說": ["thuyết", "duyệt", "thoát"],
    "说": ["thuyết", "duyệt", "thoát"],
    "話": ["thoại"],
    "话": ["thoại"],
    "問": ["vấn"],
    "问": ["vấn"],
    "答": ["đáp"],
    "知": ["tri", "trí"],
    "識": ["thức", "chí"],
    "识": ["thức", "chí"],
    # Nature, landscape, seasons, poetry &詞 (Thể loại từ VN & Thơ văn Lý Trần)
    "春": ["xuân"],
    "夏": ["hạ"],
    "秋": ["thu"],
    "冬": ["đông"],
    "時": ["thời", "thì"],
    "时": ["thời", "thì"],
    "年": ["niên"],
    "歲": ["tuế"],
    "岁": ["tuế"],
    "日": ["nhật", "nhựt"],
    "月": ["nguyệt"],
    "星": ["tinh"],
    "辰": ["thần", "thìn"],
    "晨": ["thần"],
    "朝": ["triều", "trêu", "châu"],
    "暮": ["mộ"],
    "夕": ["tịch"],
    "夜": ["dạ"],
    "宵": ["tiêu"],
    "曉": ["hiểu"],
    "晓": ["hiểu"],
    "明": ["minh"],
    "暗": ["ám"],
    "光": ["quang"],
    "影": ["ảnh"],
    "陰": ["âm"],
    "阴": ["âm"],
    "陽": ["dương"],
    "阳": ["dương"],
    "乾": ["càn", "kiền", "can"],
    "坤": ["khôn"],
    "元": ["nguyên"],
    "亨": ["hanh"],
    "利": ["lợi"],
    "貞": ["trinh"],
    "贞": ["trinh"],
    "花": ["hoa"],
    "華": ["hoa", "hoà"],
    "华": ["hoa", "hoà"],
    "草": ["thảo"],
    "木": ["mộc"],
    "樹": ["thụ", "thọ"],
    "树": ["thụ", "thọ"],
    "枝": ["chi"],
    "葉": ["diệp", "nhiếp"],
    "叶": ["diệp", "hiệp"],
    "根": ["căn"],
    "果": ["quả"],
    "實": ["thực", "thật"],
    "实": ["thực", "thật"],
    "松": ["tùng"],
    "竹": ["trúc"],
    "梅": ["mai"],
    "蘭": ["lan"],
    "兰": ["lan"],
    "菊": ["cúc"],
    "蓮": ["liên"],
    "莲": ["liên"],
    "荷": ["hà", "hạ"],
    "桃": ["đào"],
    "李": ["lý", "lí"],
    "柳": ["liễu"],
    "榮": ["vinh"],
    "荣": ["vinh"],
    "枯": ["khô"],
    "落": ["lạc"],
    "開": ["khai"],
    "开": ["khai"],
    "閉": ["bế"],
    "闭": ["bế"],
    "香": ["hương"],
    "芳": ["phương"],
    "風": ["phong", "phúng"],
    "风": ["phong", "phúng"],
    "雲": ["vân"],
    "雨": ["vũ", "vụ"],
    "雪": ["tuyết"],
    "霜": ["sương"],
    "露": ["lộ"],
    "霧": ["vụ"],
    "雾": ["vụ"],
    "煙": ["yên", "nhân"],
    "烟": ["yên", "nhân"],
    "霞": ["hà"],
    "電": ["điện"],
    "电": ["điện"],
    "雷": ["lôi"],
    "水": ["thủy", "thuỷ"],
    "山": ["sơn", "san"],
    "江": ["giang"],
    "河": ["hà"],
    "海": ["hải"],
    "湖": ["hồ"],
    "溪": ["khê"],
    "谿": ["khê"],
    "川": ["xuyên"],
    "波": ["ba"],
    "浪": ["lãng", "lang", "lương"],
    "濤": ["đào"],
    "涛": ["đào"],
    "流": ["lưu"],
    "源": ["nguyên"],
    "深": ["thâm"],
    "淺": ["thiển"],
    "浅": ["thiển"],
    "清": ["thanh", "thinh"],
    "濁": ["trọc"],
    "浊": ["trọc"],
    "寒": ["hàn"],
    "冷": ["lãnh"],
    "溫": ["ôn"],
    "温": ["ôn"],
    "暖": ["noãn"],
    "熱": ["nhiệt"],
    "热": ["nhiệt"],
    "涼": ["lương"],
    "凉": ["lương"],
    "石": ["thạch", "đam"],
    "玉": ["ngọc"],
    "金": ["kim"],
    "銀": ["ngân"],
    "银": ["ngân"],
    "鐵": ["thiết"],
    "铁": ["thiết"],
    "土": ["thổ"],
    "沙": ["sa"],
    # Emotions, travel, parting,詞 imagery (incl. prompt required characters)
    "夢": ["mộng", "mông"],
    "梦": ["mộng", "mông"],
    "情": ["tình"],
    "恨": ["hận"],
    "愁": ["sầu"],
    "憂": ["ưu"],
    "忧": ["ưu"],
    "悲": ["bi"],
    "哀": ["ai"],
    "喜": ["hỷ", "hỉ"],
    "怒": ["nộ"],
    "歡": ["hoan"],
    "欢": ["hoan"],
    "愛": ["ái"],
    "爱": ["ái"],
    "惜": ["tích"],
    "憐": ["liên"],
    "怜": ["liên"],
    "懷": ["hoài"],
    "怀": ["hoài"],
    "憶": ["ức"],
    "忆": ["ức"],
    "忘": ["vong", "vọng"],
    "歸": ["quy", "qui"],
    "归": ["quy", "qui"],
    "郎": ["lang"],
    "仙": ["tiên"],
    "郷": ["hương", "hướng", "khanh"],
    "鄉": ["hương", "hướng", "khanh"],
    "乡": ["hương", "hướng", "khanh"],
    "家": ["gia", "cô"],
    "室": ["thất"],
    "堂": ["đường"],
    "庭": ["đình"],
    "門": ["môn"],
    "门": ["môn"],
    "戶": ["hộ"],
    "户": ["hộ"],
    "窗": ["song"],
    "樓": ["lâu"],
    "楼": ["lâu"],
    "臺": ["đài"],
    "台": ["đài", "thai", "di"],
    "閣": ["các"],
    "阁": ["các"],
    "亭": ["đình"],
    "城": ["thành"],
    "池": ["trì", "đà"],
    "橋": ["kiều"],
    "桥": ["kiều"],
    "路": ["lộ"],
    "途": ["đồ"],
    "行": ["hành", "hàng", "hạng", "hạnh"],
    "走": ["tẩu"],
    "步": ["bộ"],
    "遊": ["du"],
    "游": ["du"],
    "客": ["khách"],
    "旅": ["lữ"],
    "舟": ["chu", "châu"],
    "船": ["thuyền"],
    "車": ["xa", "cư"],
    "车": ["xa", "cư"],
    "馬": ["mã"],
    "马": ["mã"],
    "鳥": ["điểu"],
    "鸟": ["điểu"],
    "魚": ["ngư"],
    "鱼": ["ngư"],
    "龍": ["long", "lung"],
    "龙": ["long", "lung"],
    "虎": ["hổ"],
    "鶴": ["hạc"],
    "鹤": ["hạc"],
    "鷗": ["âu"],
    "鴎": ["âu"],
    "鸥": ["âu"],
    "燕": ["yến", "yên"],
    "鶯": ["oanh"],
    "莺": ["oanh"],
    "蝶": ["điệp"],
    "萬": ["vạn", "mặc"],
    "万": ["vạn", "mặc"],
    "里": ["lý", "lí"],
    "裏": ["lý", "lí"],
    "裡": ["lý", "lí"],
    "千": ["thiên"],
    "百": ["bách", "bá"],
    "十": ["thập"],
    "一": ["nhất", "nhứt"],
    "二": ["nhị"],
    "三": ["tam", "tạm"],
    "四": ["tứ"],
    "五": ["ngũ"],
    "六": ["lục"],
    "七": ["thất"],
    "八": ["bát"],
    "九": ["cửu", "cưu"],
    "零": ["linh"],
    "半": ["bán"],
    "雙": ["song"],
    "双": ["song"],
    "獨": ["độc"],
    "独": ["độc"],
    "孤": ["cô"],
    "單": ["đơn", "đan", "thiện"],
    "单": ["đơn", "đan", "thiện"],
    "重": ["trùng", "trọng"],
    "輕": ["khinh"],
    "轻": ["khinh"],
    "滄": ["thương"],
    "沧": ["thương"],
    "蒼": ["thương"],
    "苍": ["thương"],
    "長": ["trường", "trưởng", "trượng"],
    "长": ["trường", "trưởng", "trượng"],
    "短": ["đoản"],
    "高": ["cao"],
    "低": ["đê"],
    "遠": ["viễn", "viện"],
    "远": ["viễn", "viện"],
    "近": ["cận", "cặn"],
    "廣": ["quảng"],
    "广": ["quảng", "nghiễm"],
    "闊": ["khoát"],
    "阔": ["khoát"],
    "久": ["cửu"],
    "暫": ["tạm"],
    "暂": ["tạm"],
    "早": ["tảo"],
    "晚": ["vãn"],
    "遲": ["trì", "trị"],
    "迟": ["trì", "trị"],
    "速": ["tốc"],
    "慘": ["thảm"],
    "惨": ["thảm"],
    "切": ["thiết", "thế"],
    "對": ["đối"],
    "对": ["đối"],
    "離": ["ly", "li", "lệ"],
    "离": ["ly", "li", "lệ"],
    "別": ["biệt"],
    "别": ["biệt"],
    "分": ["phân", "phận"],
    "合": ["hợp", "hạp", "cáp"],
    "會": ["hội", "cối"],
    "会": ["hội", "cối"],
    "逢": ["phùng", "bồng"],
    "遇": ["ngộ"],
    "見": ["kiến", "hiện"],
    "见": ["kiến", "hiện"],
    "看": ["khán", "khan"],
    "視": ["thị"],
    "视": ["thị"],
    "觀": ["quan", "quán"],
    "观": ["quan", "quán"],
    "聽": ["thính", "thinh"],
    "听": ["thính", "thinh"],
    "聞": ["văn", "vấn"],
    "闻": ["văn", "vấn"],
    "聲": ["thanh", "thinh"],
    "声": ["thanh", "thinh"],
    "音": ["âm"],
    "響": ["hưởng"],
    "响": ["hưởng"],
    "觴": ["thương"],
    "觞": ["thương"],
    "酒": ["tửu"],
    "杯": ["bôi"],
    "盃": ["bôi"],
    "盞": ["trản"],
    "盏": ["trản"],
    "醉": ["túy", "tuý"],
    "醒": ["tỉnh", "tinh"],
    "飲": ["ẩm", "ấm"],
    "饮": ["ẩm", "ấm"],
    "食": ["thực", "tự", "dị"],
    "衣": ["y", "ý"],
    "裳": ["thường"],
    "冠": ["quan", "quán"],
    "帶": ["đái", "đới"],
    "带": ["đái", "đới"],
    "履": ["lý", "lí"],
    "劍": ["kiếm"],
    "剑": ["kiếm"],
    "刀": ["đao"],
    "弓": ["cung"],
    "矢": ["thỉ", "thỷ"],
    "戈": ["qua"],
    "甲": ["giáp"],
    # Vietnamese classical historical & geographic characters (Lý - Trần, Nguyễn Trãi, etc.)
    "南": ["nam", "na"],
    "北": ["bắc", "bối"],
    "東": ["đông"],
    "东": ["đông"],
    "西": ["tây"],
    "中": ["trung", "trúng"],
    "外": ["ngoại"],
    "內": ["nội", "nạp"],
    "内": ["nội", "nạp"],
    "上": ["thượng", "thưởng"],
    "下": ["hạ", "hà"],
    "前": ["tiền"],
    "後": ["hậu"],
    "后": ["hậu"],
    "左": ["tả", "tá"],
    "右": ["hữu", "hựu"],
    "間": ["gian", "gián"],
    "间": ["gian", "gián"],
    "邊": ["biên"],
    "边": ["biên"],
    "界": ["giới"],
    "越": ["việt"],
    "漢": ["hán"],
    "汉": ["hán"],
    "唐": ["đường"],
    "宋": ["tống"],
    "元": ["nguyên"],
    "明": ["minh"],
    "清": ["thanh"],
    "李": ["lý", "lí"],
    "陳": ["trần", "trận"],
    "陈": ["trần", "trận"],
    "黎": ["lê"],
    "阮": ["nguyễn", "ngoan"],
    "廌": ["trãi", "trĩ"],
    "仁": ["nhân"],
    "聖": ["thánh"],
    "太": ["thái"],
    "祖": ["tổ"],
    "宗": ["tông", "tôn"],
    "截": ["tiệt"],
    "逆": ["nghịch"],
    "虜": ["lỗ"],
    "虏": ["lỗ"],
    "侵": ["xâm"],
    "犯": ["phạm"],
    "等": ["đẳng"],
    "取": ["thủ"],
    "虛": ["hư", "khư"],
    "虚": ["hư", "khư"],
    "任": ["nhiệm", "nhậm", "nhâm"],
    "運": ["vận"],
    "运": ["vận"],
    "怖": ["bố"],
    "頭": ["đầu"],
    "头": ["đầu"],
    "鋪": ["phô", "phố"],
    "铺": ["phô", "phố"],
    "巫": ["vu"],
    "段": ["đoạn"],
    "起": ["khởi", "khỉ"],
    "眠": ["miên"],
    "掬": ["cúc"],
    "手": ["thủ"],
    "弄": ["lộng", "lũng"],
    "滿": ["mãn"],
    "满": ["mãn"],
    # Additional characters from TLTVN (Nguyễn lang quy) & TVLT2 (Ký Thanh Phong am / Tống Bắc sứ)
    "祥": ["tường"],
    "好": ["hảo", "hiếu"],
    "錦": ["cẩm"],
    "锦": ["cẩm"],
    "帆": ["phàm"],
    "張": ["trương", "trướng"],
    "张": ["trương", "trướng"],
    "涉": ["thiệp"],
    "攀": ["phan"],
    "戀": ["luyến"],
    "恋": ["luyến"],
    "使": ["sứ", "sử"],
    "願": ["nguyện"],
    "愿": ["nguyện"],
    "疆": ["cương"],
    "分": ["phân", "phận"],
    "報": ["báo"],
    "报": ["báo"],
    "寄": ["ký", "kí"],
    "庵": ["am"],
    "打": ["đả"],
    "關": ["quan"],
    "关": ["quan"],
    "照": ["chiếu"],
    "期": ["kỳ", "kì", "cơ"],
    "景": ["cảnh", "ảnh"],
    "共": ["cộng", "cung"],
    "淒": ["thê"],
    "凄": ["thê"],
    "箇": ["cá"],
    "个": ["cá"],
    "滋": ["tư"],
    "味": ["vị"],
    "付": ["phó", "phụ"],
    "到": ["đáo"],
    "送": ["tống"],
    "顯": ["hiển"],
    "显": ["hiển"],
    "卿": ["khanh"],
    "顧": ["cố"],
    "顾": ["cố"],
    "瓊": ["quỳnh"],
    "琼": ["quỳnh"],
    "慚": ["tàm"],
    "惭": ["tàm"],
    "極": ["cực"],
    "极": ["cực"],
    "目": ["mục"],
    "皋": ["cao"],
    "皐": ["cao"],
    "堪": ["kham"],
    "首": ["thủ", "thú"],
    "吹": ["xuy", "xúy"],
    "鋏": ["giáp", "kiệp"],
    "铗": ["giáp", "kiệp"],
    "屋": ["ốc"],
    "梁": ["lương"],
    "幕": ["mạc", "mộ"],
    "駐": ["trụ", "trú"],
    "驻": ["trụ", "trú"],
    "雁": ["nhạn"],
    "鴈": ["nhạn"],
    "傾": ["khuynh"],
    "倾": ["khuynh"],
    "篇": ["thiên"],
    "聊": ["liêu"],
    "談": ["đàm"],
    "谈": ["đàm"],
}


# Vietnamese old/new tone placement & y/i orthographic equivalence tables
_TONE_NORMALIZATION_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("oà", "òa"), ("oá", "óa"), ("oả", "ỏa"), ("oã", "õa"), ("oạ", "ọa"),
    ("oè", "òe"), ("oé", "óe"), ("oẻ", "ỏe"), ("oẽ", "õe"), ("oẹ", "ọe"),
    ("uỳ", "ùy"), ("uý", "úy"), ("uỷ", "ủy"), ("uỹ", "ũy"), ("uỵ", "ụy"),
)

_Y_TO_I_VOWELS: Dict[str, str] = {
    "y": "i",
    "ỳ": "ì",
    "ý": "í",
    "ỷ": "ỉ",
    "ỹ": "ĩ",
    "ỵ": "ị",
}

# Regex for footnote markers in Phiên âm text:
# Matches `1*`, `12*`, `[1]`, `(1)`, superscript digits `¹²³`, asterisks `*`, and standalone digits
_FOOTNOTE_MARKER_RE = re.compile(
    r"\[\s*\d+\s*\]"          # [1], [12]
    r"|\(\s*\d+\s*\)"         # (1), (12)
    r"|\d+\s*\*+"             # 1*, 2**
    r"|\*+"                   # standalone *
    r"|[⁰¹²³⁴⁵⁶⁷⁸⁹]+"         # superscript numbers
    r"|\d+"                   # any remaining digits
)

# Regex for stripping an optional leading "Phiên âm:" header if present
_LEADING_PHIEN_AM_HEADER_RE = re.compile(
    r"^\s*(?:phiên\s*âm|phien\s*am)\s*[:：]\s*",
    flags=re.IGNORECASE,
)

# Regex for Vietnamese alphabetic syllables (including hyphen-joined syllables)
_VIET_SYLLABLE_RE = re.compile(r"[^\W\d_]+", flags=re.UNICODE)

# Regex for extracting a Vietnamese syllable together with any immediately trailing punctuation
_SYLLABLE_WITH_PUNCT_RE = re.compile(
    r"([^\W\d_]+)\s*([,.;:?!]*)",
    flags=re.UNICODE,
)


def is_han_char(ch: str) -> bool:
    """Return True if `ch` is a single CJK Unified/Compatibility Ideograph (Extensions A–I)."""
    if len(ch) != 1:
        return False
    cp = ord(ch)
    for start, end in CJK_RANGES:
        if start <= cp <= end:
            return True
    return False


def count_han_chars(text: str) -> List[str]:
    """Extract all CJK Unified Ideographs (including Extensions A–G) from `text` in order.

    Args:
        text: Input string containing Classical Chinese (`Chữ Hán`) characters.

    Returns:
        List of extracted CJK Unified Ideograph characters (`len(result)` gives the count).
    """
    if not text:
        return []
    return [ch for ch in text if is_han_char(ch)]


def normalize_viet_syllable(syllable: str) -> str:
    """Normalize a Vietnamese syllable to canonical NFC lowercase form.

    Standardizes Unicode composition (NFC), lowercase, tone mark placement
    (`thuỷ` <-> `thủy`, `hoà` <-> `hòa`), and orthographic `y`/`i` equivalence
    (`lý` <-> `lí`, `quy` <-> `qui`, `kỳ` <-> `kì`, `mỹ` <-> `mĩ`).
    """
    s = unicodedata.normalize("NFC", syllable.strip()).lower()
    for src, dst in _TONE_NORMALIZATION_PAIRS:
        if src in s:
            s = s.replace(src, dst)
    # Canonicalize qu + y -> qu + i (e.g. quy -> qui, quý -> quí, quỳ -> quì)
    if s.startswith("qu") and len(s) == 3 and s[2] in _Y_TO_I_VOWELS:
        s = "qu" + _Y_TO_I_VOWELS[s[2]]
    # Canonicalize open-syllable consonant + y -> consonant + i (e.g. lý -> lí, kỳ -> kì, mỹ -> mĩ)
    elif len(s) >= 2 and s[-1] in _Y_TO_I_VOWELS and s[-2] not in "aeoơăâuư":
        s = s[:-1] + _Y_TO_I_VOWELS[s[-1]]
    return s


def strip_footnote_markers(text: str) -> str:
    """Remove footnote markers (`1*`, `[1]`, `(1)`, superscripts `¹²³`, digits) from `text`."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFC", text)
    normalized = _LEADING_PHIEN_AM_HEADER_RE.sub("", normalized)
    return _FOOTNOTE_MARKER_RE.sub(" ", normalized)


def tokenize_phien_am(text: str, preserve_case: bool = False) -> List[str]:
    """Strip footnote markers (`1*`, `[1]`, `(1)`, superscripts) and extract Vietnamese syllables.

    Args:
        text: Input `Phiên âm Hán–Việt` string.
        preserve_case: If True, keep original capitalization; defaults to False (lowercase).

    Returns:
        Ordered list of Vietnamese syllable tokens.
    """
    if not text:
        return []
    cleaned = strip_footnote_markers(text)
    tokens = _VIET_SYLLABLE_RE.findall(cleaned)
    if preserve_case:
        return tokens
    return [tok.lower() for tok in tokens]


def project_punctuation_from_phien_am(han_text: str, phien_am_text: str) -> str:
    """Project punctuation from `phien_am_text` onto an unpunctuated `han_text`.

    When `han_text` lacks punctuation (as in *Hán Văn Tinh Túy*) and has the exact
    same number of Han characters as Vietnamese syllables in `phien_am_text`,
    projects `,` -> `，`, `.` -> `。`, `?` -> `？`, `!` -> `！`, `;` -> `；`, `:` -> `：`
    onto the corresponding character boundary in `han_text`.

    Args:
        han_text: Classical Chinese string (potentially unpunctuated).
        phien_am_text: Corresponding Sino-Vietnamese transcription with punctuation.

    Returns:
        Punctuated `han_text` if conditions are met; otherwise the original `han_text`.
    """
    if not han_text or not phien_am_text:
        return han_text

    # Do not overwrite if han_text already contains punctuation
    if any(ch in EXISTING_HAN_PUNCTUATION for ch in han_text):
        return han_text

    han_chars = count_han_chars(han_text)
    if not han_chars:
        return han_text

    cleaned_phien_am = strip_footnote_markers(phien_am_text)
    syllable_punct_pairs = _SYLLABLE_WITH_PUNCT_RE.findall(cleaned_phien_am)

    if len(han_chars) != len(syllable_punct_pairs):
        return han_text

    # Reconstruct han_text preserving newlines if present, inserting mapped CJK punctuation
    # immediately after each Han character.
    projected_puncts: List[str] = []
    for _syllable, raw_punct in syllable_punct_pairs:
        if raw_punct:
            # Collapse multiple dots (e.g. "...") to a single fullwidth period "。" or map char-by-char
            if set(raw_punct) == {"."} and len(raw_punct) > 1:
                mapped = "。"
            else:
                mapped = "".join(PUNCTUATION_PROJECTION_MAP.get(p, "") for p in raw_punct)
            projected_puncts.append(mapped)
        else:
            projected_puncts.append("")

    if "\n" not in han_text:
        return "".join(ch + punct for ch, punct in zip(han_chars, projected_puncts))

    # Preserve newlines if multi-line poetry/interlinear text was passed
    out_parts: List[str] = []
    han_idx = 0
    for ch in han_text:
        if is_han_char(ch):
            out_parts.append(ch + projected_puncts[han_idx])
            han_idx += 1
        elif ch == "\n":
            out_parts.append("\n")
    return "".join(out_parts)


def load_han_viet_dict(
    dict_path: Optional[Union[str, Path]] = None,
) -> Dict[str, List[str]]:
    """Load the core Sino-Vietnamese dictionary and merge an extended JSON/TSV file if present.

    Args:
        dict_path: Optional path to an extended `.json` or `.tsv` dictionary file.
            If omitted, checks `config/han_viet_dict.json` and `config/han_viet_dict.tsv`
            relative to the project root if they exist.

    Returns:
        Dictionary mapping each Han character to a list of lowercase Sino-Vietnamese readings.
    """
    merged: Dict[str, List[str]] = {
        char: list(readings) for char, readings in CORE_HAN_VIET_DICT.items()
    }

    candidate_paths: List[Path] = []
    if dict_path is not None:
        candidate_paths.append(Path(dict_path))
    else:
        repo_root = Path(__file__).resolve().parent.parent
        candidate_paths.extend([
            repo_root / "config" / "han_viet_dict.json",
            repo_root / "config" / "han_viet_dict.tsv",
        ])

    for path in candidate_paths:
        if not path.is_file():
            continue
        try:
            if path.suffix.lower() == ".json":
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    for k, v in data.items():
                        if not isinstance(k, str) or len(k) != 1:
                            continue
                        readings = [v] if isinstance(v, str) else list(v)
                        existing = merged.setdefault(k, [])
                        for r in readings:
                            r_clean = unicodedata.normalize("NFC", str(r).strip()).lower()
                            if r_clean and r_clean not in existing:
                                existing.append(r_clean)
            elif path.suffix.lower() in (".tsv", ".txt"):
                with path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        parts = line.split("\t")
                        if len(parts) >= 2 and len(parts[0].strip()) == 1:
                            char = parts[0].strip()
                            readings = re.split(r"[,;/\s]+", parts[1].strip())
                            existing = merged.setdefault(char, [])
                            for r in readings:
                                r_clean = unicodedata.normalize("NFC", r.strip()).lower()
                                if r_clean and r_clean not in existing:
                                    existing.append(r_clean)
        except Exception:
            # Fail gracefully and retain CORE_HAN_VIET_DICT if an external file is malformed
            continue

    return merged


def verify_han_phien_am_pair(
    han_text: str,
    phien_am_text: str,
    custom_dict: Optional[Dict[str, Sequence[str]]] = None,
    dict_path: Optional[Union[str, Path]] = None,
) -> Dict[str, object]:
    """Verify length and Sino-Vietnamese phonetic alignment between `han_text` and `phien_am_text`.

    Args:
        han_text: Classical Chinese string (`Chữ Hán`).
        phien_am_text: Corresponding Sino-Vietnamese transcription (`Phiên âm Hán–Việt`).
        custom_dict: Optional custom character-to-readings dictionary override.
        dict_path: Optional path to an extended JSON/TSV dictionary file.

    Returns:
        Dictionary with keys:
        - `char_count` (int): Number of CJK ideographs in `han_text`.
        - `syllable_count` (int): Number of Vietnamese syllables in `phien_am_text`.
        - `length_match` (bool): True iff `char_count == syllable_count` and `char_count > 0`
          (or both are 0).
        - `phonetic_mismatches` (list[tuple[int, str, str, list[str]]]): List of
          `(index, han_char, syllable, expected_readings)` for known characters whose
          aligned syllable does not match any expected Sino-Vietnamese reading.
        - `confidence_score` (float): Overall alignment and phonetic confidence in `[0.0, 1.0]`.
    """
    han_chars = count_han_chars(han_text)
    syllables = tokenize_phien_am(phien_am_text, preserve_case=False)

    char_count = len(han_chars)
    syllable_count = len(syllables)
    length_match = char_count == syllable_count

    if char_count == 0 and syllable_count == 0:
        return {
            "char_count": 0,
            "syllable_count": 0,
            "length_match": True,
            "phonetic_mismatches": [],
            "confidence_score": 0.0,
        }

    if char_count == 0 or syllable_count == 0:
        return {
            "char_count": char_count,
            "syllable_count": syllable_count,
            "length_match": False,
            "phonetic_mismatches": [],
            "confidence_score": 0.0,
        }

    lookup: Dict[str, Sequence[str]] = (
        custom_dict if custom_dict is not None else load_han_viet_dict(dict_path)
    )

    phonetic_mismatches: List[Tuple[int, str, str, List[str]]] = []
    aligned_len = min(char_count, syllable_count)
    known_char_count = 0

    for idx in range(aligned_len):
        han_ch = han_chars[idx]
        syllable = syllables[idx]
        expected = lookup.get(han_ch)
        if not expected:
            continue
        known_char_count += 1
        norm_syllable = normalize_viet_syllable(syllable)
        norm_expected = {normalize_viet_syllable(r) for r in expected}
        if norm_syllable not in norm_expected:
            phonetic_mismatches.append((idx, han_ch, syllable, list(expected)))

    # Compute deterministic confidence score in [0.0, 1.0]
    max_len = max(char_count, syllable_count)
    length_ratio = aligned_len / max_len

    if known_char_count > 0:
        phonetic_accuracy = (known_char_count - len(phonetic_mismatches)) / known_char_count
    else:
        phonetic_accuracy = 1.0

    overall_pair_accuracy = (aligned_len - len(phonetic_mismatches)) / aligned_len
    blended_phonetic = 0.7 * phonetic_accuracy + 0.3 * overall_pair_accuracy

    if length_match:
        confidence_score = round(blended_phonetic, 4)
    else:
        # Penalize length mismatch because character-by-character alignment can drift
        confidence_score = round(0.75 * length_ratio * blended_phonetic, 4)

    confidence_score = max(0.0, min(1.0, confidence_score))

    return {
        "char_count": char_count,
        "syllable_count": syllable_count,
        "length_match": length_match,
        "phonetic_mismatches": phonetic_mismatches,
        "confidence_score": confidence_score,
    }


__all__ = [
    "CJK_RANGES",
    "CORE_HAN_VIET_DICT",
    "PUNCTUATION_PROJECTION_MAP",
    "count_han_chars",
    "is_han_char",
    "load_han_viet_dict",
    "normalize_viet_syllable",
    "project_punctuation_from_phien_am",
    "strip_footnote_markers",
    "tokenize_phien_am",
    "verify_han_phien_am_pair",
]
