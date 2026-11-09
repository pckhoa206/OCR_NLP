"""Word-Level Vocabulary Alignment & Coverage Scoring Engine for Hán–Việt Corpora.

Provides fine-grained, word/token-level grounding between Classical Chinese
and Vietnamese sentences:
- Maps Han characters to both their Sino-Vietnamese phonetic readings
  (using `CORE_HAN_VIET_DICT`) and their native Vietnamese semantic translation equivalents.
- Computes character-level Han coverage (% of Han characters with an etymological or
  semantic footprint in the Vietnamese translation).
- Computes word-level Vietnamese grounding (% of Vietnamese words supported by the Han source).
- Identifies potential omission (unmatched Han characters) and potential hallucination/paraphrase.
- Calculates an overall composite Alignment Confidence Score in [0.0, 1.0].
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple

from src.phonetic_verifier import CORE_HAN_VIET_DICT
from src.text_cleaner import clean_han_text, clean_viet_text

_CJK_CHAR_RE = re.compile(
    r"[\u3007\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002ebef\u25a0-\u25a3]"
)
_VIET_WORD_RE = re.compile(r"[A-Za-zÀ-ỹà-ỹ0-9]+")

# Common Han characters and their native Vietnamese translation equivalents
_HAN_SEMANTIC_GLOSSES: Dict[str, Tuple[str, ...]] = {
    # Nature & Cosmogony
    "天": ("trời", "thiên"),
    "地": ("đất", "địa"),
    "日": ("ngày", "trời", "mặt trời", "nhật"),
    "月": ("trăng", "tháng", "nguyệt"),
    "星": ("sao", "tinh"),
    "風": ("gió", "phong"),
    "雨": ("mưa", "vũ"),
    "雲": ("mây", "vân"),
    "雪": ("tuyết", "băng"),
    "霜": ("sương", "sương giá"),
    "山": ("núi", "sơn"),
    "水": ("nước", "sông", "thủy"),
    "江": ("sông", "giang"),
    "海": ("biển", "hải"),
    "波": ("sóng", "ba"),
    "浪": ("sóng", "lãng"),
    "春": ("xuân", "mùa xuân"),
    "夏": ("hè", "hạ", "mùa hè"),
    "秋": ("thu", "mùa thu"),
    "冬": ("đông", "mùa đông"),
    "夜": ("đêm", "tối", "dạ"),
    "朝": ("sáng", "buổi sáng", "triều", "triêu"),
    "夕": ("chiều", "tịch", "tối"),
    "明": ("sáng", "rõ", "minh"),
    "暗": ("tối", "ám"),
    "花": ("hoa", "bông"),
    "草": ("cỏ", "thảo"),
    "木": ("cây", "gỗ", "mộc"),
    "松": ("thông", "tùng"),
    "竹": ("tre", "trúc"),
    "菊": ("cúc", "hoa cúc"),
    "鳥": ("chim", "điểu"),
    "燕": ("én", "chim én", "yến"),
    "雁": ("nhạn", "chim nhạn"),
    "魚": ("cá", "ngư"),
    "馬": ("ngựa", "mã"),
    # Human & Body
    "人": ("người", "nhân", "kẻ", "ai"),
    "我": ("ta", "tôi", "mình", "ngã"),
    "吾": ("ta", "tôi", "ngô"),
    "朕": ("trẫm"),
    "子": ("con", "thầy", "chàng", "tử"),
    "君": ("vua", "chàng", "quân", "người"),
    "臣": ("thần", "bầy tôi"),
    "民": ("dân", "dân chúng"),
    "僧": ("sư", "nhà sư", "tăng"),
    "師": ("thầy", "sư"),
    "佛": ("phật", "đức phật"),
    "心": ("lòng", "tâm", "tim", "dạ"),
    "目": ("mắt", "mục"),
    "手": ("tay", "thủ"),
    "首": ("đầu", "thủ"),
    "身": ("mình", "thân", "xác"),
    "神": ("thần"),
    "仙": ("tiên"),
    "帝": ("hoàng đế", "vua", "đế"),
    "皇": ("vua", "hoàng đế", "nhà vua"),
    "聖": ("thánh", "bậc thánh"),
    "祖": ("tổ", "tổ sư"),
    "識": ("biết", "hiểu", "thức", "hay"),
    "滋": ("thêm", "nhiều", "vị", "thú"),
    "淒": ("lạnh", "buồn", "thê", "lặng", "lặng lẽ"),
    # Nature & Cosmogony additions
    "光": ("ánh sáng", "sáng", "quang"),
    "好": ("thuận", "tốt", "hảo"),
    "張": ("căng", "mở", "giương"),
    "帆": ("buồm", "cánh buồm", "phàm"),
    "錦": ("gấm", "cẩm"),
    "鄉": ("quê", "quê hương", "hương"),
    "里": ("dặm", "lí"),
    "涉": ("vượt", "qua", "lội", "thiệp"),
    "滄": ("xanh", "thương"),
    "浪": ("sóng", "làn sóng", "lãng"),
    "九": ("chín", "cửu"),
    "千": ("nghìn", "ngàn", "thiên"),
    "萬": ("muôn", "vạn"),
    "重": ("trùng", "nặng", "trọng"),
    "路": ("đường", "lộ"),
    "復": ("trở về", "lại", "phục"),
    # Space & Cardinal directions
    "東": ("đông", "phương đông"),
    "西": ("tây", "phương tây"),
    "南": ("nam", "phương nam"),
    "北": ("bắc", "phương bắc"),
    "中": ("trong", "giữa", "trung"),
    "內": ("trong", "nội"),
    "外": ("ngoài", "ngoại"),
    "上": ("trên", "thượng"),
    "下": ("dưới", "hạ"),
    "前": ("trước", "tiền"),
    "後": ("sau", "hậu"),
    # Life & State
    "生": ("sống", "sinh", "sanh"),
    "死": ("chết", "tử", "mất"),
    "有": ("có", "hữu"),
    "無": ("không", "vô", "mất", "chẳng"),
    "莫": ("chớ", "đừng", "không", "mạc"),
    "不": ("không", "chẳng", "chưa", "bất"),
    "大": ("lớn", "to", "đại"),
    "小": ("nhỏ", "bé", "tiểu"),
    "長": ("dài", "lâu", "trường", "xa"),
    "短": ("ngắn", "đoản"),
    "高": ("cao"),
    "深": ("sâu", "thâm"),
    "清": ("trong", "sạch", "thanh", "lặng"),
    "冷": ("lạnh", "lãnh"),
    "寒": ("lạnh", "hàn", "rét"),
    "熱": ("nóng", "nhiệt"),
    "火": ("lửa", "hỏa"),
    # Actions & Function words
    "言": ("nói", "ngôn", "lời"),
    "語": ("nói", "lời", "ngữ"),
    "曰": ("rằng", "nói", "bảo", "viết"),
    "云": ("rằng", "nói", "vân"),
    "道": ("rằng", "nói", "đạo"),
    "以": ("lấy", "bằng", "dùng", "dĩ", "mà"),
    "之": ("nó", "ấy", "đó", "chi", "của", "mà"),
    "者": ("kẻ", "người", "ấy", "giả", "điều"),
    "也": ("vậy", "dã"),
    "其": ("thì", "kỳ", "ấy", "đó", "của", "kẻ"),
    "次": ("thứ", "sau", "kế"),
    "如": ("bằng", "như", "giống"),
    "故": ("nên", "cho nên", "cố", "vì thế"),
    "焉": ("yên", "đó", "vậy", "sao"),
    "夫": ("như", "phàm", "ôi", "phu", "phù"),
    "死": ("chết", "tử", "mất"),
    "何": ("sao", "gì", "nào", "hà"),
    "安": ("sao", "đâu", "an", "yên"),
    "豈": ("há", "sao", "khởi"),
    "若": ("nếu", "như", "bằng"),
    "自": ("tự", "từ", "mình"),
    "能": ("có thể", "năng", "được"),
    "必": ("sẽ", "tất", "hẳn", "ắt"),
    "爲": ("làm", "giữ", "vi", "cho"),
    "为": ("làm", "giữ", "vi", "cho"),
    "聞": ("nghe", "văn"),
    "視": ("nhìn", "thị"),
    "見": ("thấy", "gặp", "kiến"),
    "望": ("trông", "ngóng", "vọng"),
    "來": ("đến", "về", "lại"),
    "去": ("đi", "khứ"),
    "歸": ("về", "quy"),
    "行": ("đi", "làm", "hành", "hàng"),
    "住": ("ở", "trụ"),
    "坐": ("ngồi", "tọa"),
    "立": ("đứng", "lập"),
    "飲": ("uống", "ẩm"),
    "食": ("ăn", "thực"),
    "笑": ("cười", "tiếu"),
    "哭": ("khóc", "khốc"),
    "愛": ("yêu", "ái"),
    "恨": ("hận", "giận"),
    "愁": ("buồn", "sầu"),
    "樂": ("vui", "lạc", "nhạc"),
    "思": ("nghĩ", "nhớ", "tư"),
    "知": ("biết", "tri"),
    "識": ("biết", "hiểu", "thức"),
    "問": ("hỏi", "vấn"),
    "答": ("đáp", "trả lời"),
    "讀": ("đọc", "độc"),
    "寫": ("viết", "tả"),
    "詩": ("thơ", "thi"),
    "歌": ("hát", "ca"),
    "酒": ("rượu", "tửu"),
    "杯": ("chén", "chén rượu", "bôi", "ly"),
    "劍": ("kiếm", "gươm"),
    "舟": ("thuyền", "chu"),
    "車": ("xe", "xa"),
    "門": ("cửa", "cổng", "môn"),
    "庭": ("sân", "đình"),
    "打": ("đánh", "đập", "gõ", "đả"),
    "關": ("quan", "cửa", "cổng", "then"),
    "開": ("mở", "khai"),
    "照": ("soi", "chiếu", "rọi", "sáng"),
    "期": ("hẹn", "mong", "kỳ"),
    "共": ("cùng", "chung", "cộng"),
    "淒": ("lạnh", "buồn", "thê"),
    "箇": ("cá", "cái", "trong", "đó"),
    "味": ("vị", "mùi", "thú"),
    "付": ("giao", "cho", "mặc", "phó"),
    "與": ("cho", "với", "dữ"),
    "到": ("đến", "tới", "đáo"),
    "明": ("sáng", "rõ", "minh"),
    "疾": ("bệnh", "tật", "đau", "nặng"),
    "謂": ("bảo", "nói", "rằng", "vị"),
    "政": ("chính", "chính quyền", "việc nước"),
    "服": ("phục", "theo", "vâng"),
    "猛": ("mạnh", "nghiêm", "thẳng tay", "mãnh"),
    "寬": ("khoan", "khoan dung", "khoan hòa", "rộng rãi"),
    "烈": ("cháy", "dữ", "liệt", "mạnh"),
    "畏": ("sợ", "úy", "kinh"),
    "鮮": ("ít", "hiếm", "tiển"),
}

# Stopwords in Vietnamese that don't need direct Han anchors
_VIET_FUNCTION_WORDS = {
    "là", "của", "và", "với", "cho", "để", "ở", "tại", "mà", "nhưng",
    "đã", "đang", "sẽ", "được", "bị", "bởi", "thì", "cũng", "rất",
    "quá", "lắm", "những", "các", "mọi", "mỗi", "từng", "một", "cái",
    "con", "chiếc", "thay", "ơi", "ạ", "ư", "hỡi", "vậy", " ru", "thế",
}


def _normalize_syllable(s: str) -> str:
    """Normalize Vietnamese syllable for lookup."""
    return unicodedata.normalize("NFC", s.strip().lower())


def get_candidate_readings_and_glosses(han_char: str) -> Set[str]:
    """Retrieve all valid Sino-Vietnamese readings and Vietnamese translation glosses."""
    candidates: Set[str] = set()

    # 1. Sino-Vietnamese phonetic readings from core dictionary
    readings = CORE_HAN_VIET_DICT.get(han_char, [])
    for r in readings:
        for token in _VIET_WORD_RE.findall(r):
            candidates.add(_normalize_syllable(token))

    # 2. Semantic translation equivalents
    glosses = _HAN_SEMANTIC_GLOSSES.get(han_char, ())
    for g in glosses:
        for token in _VIET_WORD_RE.findall(g):
            candidates.add(_normalize_syllable(token))

    return candidates


def align_words_in_pair(han_text: str, viet_text: str) -> Dict[str, Any]:
    """Perform fine-grained word/character alignment and coverage analysis.

    Returns:
        dict containing:
            - `han_char_count`: int
            - `viet_word_count`: int
            - `han_coverage_pct`: float (0.0 to 100.0)
            - `viet_coverage_pct`: float (0.0 to 100.0)
            - `aligned_matches`: list of matched tuples (han_char, viet_word, match_type)
            - `unmatched_han`: list of Han characters without footprint
            - `confidence_score`: composite alignment confidence in [0.0, 1.0]
    """
    clean_h = clean_han_text(han_text)
    clean_v = clean_viet_text(viet_text)

    han_chars = _CJK_CHAR_RE.findall(clean_h)
    viet_tokens = _VIET_WORD_RE.findall(clean_v)
    viet_tokens_norm = [_normalize_syllable(t) for t in viet_tokens]

    if not han_chars or not viet_tokens:
        return {
            "han_char_count": len(han_chars),
            "viet_word_count": len(viet_tokens),
            "han_coverage_pct": 0.0,
            "viet_coverage_pct": 0.0,
            "aligned_matches": [],
            "unmatched_han": han_chars,
            "confidence_score": 0.0,
        }

    # Track matched status
    han_matched_flags = [False] * len(han_chars)
    viet_matched_flags = [False] * len(viet_tokens)
    aligned_matches: List[Dict[str, Any]] = []

    # Map each Han character to candidates
    for h_idx, ch in enumerate(han_chars):
        if ch in ("□", "■"):
            # Lacuna is naturally preserved and marked neutral
            han_matched_flags[h_idx] = True
            continue

        candidates = get_candidate_readings_and_glosses(ch)
        if not candidates:
            continue

        # Look for matching token in Vietnamese text
        matched_any = False
        for v_idx, v_token in enumerate(viet_tokens_norm):
            if v_token in candidates:
                han_matched_flags[h_idx] = True
                viet_matched_flags[v_idx] = True
                matched_any = True
                aligned_matches.append({
                    "han_index": h_idx,
                    "han_char": ch,
                    "viet_index": v_idx,
                    "viet_word": viet_tokens[v_idx],
                    "match_type": "phonetic_or_gloss",
                })
                break  # greedy match one instance per character

    # Calculate coverage ratios
    han_matched_count = sum(1 for m in han_matched_flags if m)
    han_coverage = (han_matched_count / len(han_chars)) * 100.0

    # For Vietnamese words, exclude function words from penalty
    content_viet_indices = [
        i for i, t in enumerate(viet_tokens_norm)
        if t not in _VIET_FUNCTION_WORDS and len(t) > 1
    ]
    if content_viet_indices:
        content_matched_count = sum(1 for i in content_viet_indices if viet_matched_flags[i])
        viet_coverage = (content_matched_count / len(content_viet_indices)) * 100.0
    else:
        viet_coverage = 100.0

    unmatched_han = [han_chars[i] for i, m in enumerate(han_matched_flags) if not m]

    # Length ratio score (ideal ~ 1.8 words per Han char, plateau [0.8, 2.4])
    ratio = len(viet_tokens) / max(1, len(han_chars))
    if 0.80 <= ratio <= 2.40:
        length_score = 1.0
    elif ratio < 0.80:
        length_score = max(0.1, 1.0 - (0.80 - ratio) * 1.5)
    else:
        length_score = max(0.1, 1.0 - (ratio - 2.40) * 0.4)

    # Composite Alignment Confidence Score
    confidence_score = (
        0.45 * (han_coverage / 100.0) +
        0.30 * (viet_coverage / 100.0) +
        0.25 * length_score
    )
    confidence_score = max(0.0, min(1.0, confidence_score))

    return {
        "han_char_count": len(han_chars),
        "viet_word_count": len(viet_tokens),
        "han_coverage_pct": round(han_coverage, 2),
        "viet_coverage_pct": round(viet_coverage, 2),
        "aligned_matches": aligned_matches,
        "unmatched_han": unmatched_han,
        "confidence_score": round(confidence_score, 4),
    }


def batch_evaluate_word_coverage(pairs: List[Tuple[str, ...]]) -> Dict[str, Any]:
    """Evaluate word-level alignment and coverage across a whole corpus."""
    total_pairs = len(pairs)
    if total_pairs == 0:
        return {"total_pairs": 0, "avg_confidence": 0.0, "avg_han_coverage": 0.0}

    confidences: List[float] = []
    han_coverages: List[float] = []
    viet_coverages: List[float] = []
    low_confidence_count = 0

    for pair in pairs:
        han_str = pair[0]
        # In 4-column format: Hán (0), Dịch âm (1), Dịch nghĩa (2), Dịch thơ (3)
        if len(pair) >= 4:
            # Combine phonetic transcription and translation for comprehensive grounding
            all_viet_parts = [p for p in pair[1:] if p.strip()]
            viet_str = " ".join(all_viet_parts)
        else:
            viet_str = pair[1]

        res = align_words_in_pair(han_str, viet_str)
        conf = res["confidence_score"]
        confidences.append(conf)
        han_coverages.append(res["han_coverage_pct"])
        viet_coverages.append(res["viet_coverage_pct"])
        if conf < 0.70:
            low_confidence_count += 1

    return {
        "total_pairs": total_pairs,
        "avg_confidence": round(sum(confidences) / total_pairs, 4),
        "avg_han_coverage_pct": round(sum(han_coverages) / total_pairs, 2),
        "avg_viet_coverage_pct": round(sum(viet_coverages) / total_pairs, 2),
        "high_confidence_pairs": sum(1 for c in confidences if c >= 0.85),
        "medium_confidence_pairs": sum(1 for c in confidences if 0.70 <= c < 0.85),
        "low_confidence_pairs": low_confidence_count,
    }
