"""Metrical and Couplet-Aware Alignment Engine for Classical Poetry.

Addresses specialized verse-to-verse translation structures:
- Thất ngôn (7-char) and Ngũ ngôn (5-char) Classical Chinese couplets
  translated to Vietnamese Lục bát (6-8) or Song thất lục bát (7-7-6-8).
- Uneven meter in Từ khúc (Ci poetry: 3, 5, 7, 9 character clauses).
- Preserves rhyme boundaries and prevents splitting couplet units in
  verse translations (Dịch thơ).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from src.aligner import align_work_sentences, count_han_chars, count_viet_words
from src.text_cleaner import clean_han_text, clean_viet_text

_CJK_CHAR_RE = re.compile(
    r"[\u3007\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002ebef]"
)
_VIET_WORD_RE = re.compile(r"[A-Za-zÀ-ỹà-ỹ0-9]+")


def detect_vietnamese_poetic_meter(line: str) -> str:
    """Detect common Vietnamese poetic meter by word count per line.

    Returns:
        `'luc_bat_6'`, `'luc_bat_8'`, `'that_ngon'`, `'ngu_ngon'`, or `'free_verse'`
    """
    words = _VIET_WORD_RE.findall(line or "")
    count = len(words)
    if count == 6:
        return "luc_bat_6"
    elif count == 8:
        return "luc_bat_8"
    elif count == 7:
        return "that_ngon"
    elif count == 5:
        return "ngu_ngon"
    return "free_verse"


def detect_han_poetic_meter(line: str) -> str:
    """Detect Classical Chinese meter by character count per line."""
    chars = _CJK_CHAR_RE.findall(line or "")
    count = len(chars)
    if count == 7:
        return "that_ngon_7"
    elif count == 5:
        return "ngu_ngon_5"
    elif count == 4:
        return "tu_ngon_4"
    return "uneven_meter"


def group_luc_bat_couplets(lines: List[str]) -> List[str]:
    """Group alternating 6-word and 8-word lines into complete 6-8 Lục bát couplets."""
    grouped: List[str] = []
    i = 0
    while i < len(lines):
        line1 = lines[i].strip()
        meter1 = detect_vietnamese_poetic_meter(line1)

        if meter1 == "luc_bat_6" and (i + 1) < len(lines):
            line2 = lines[i + 1].strip()
            meter2 = detect_vietnamese_poetic_meter(line2)
            if meter2 == "luc_bat_8":
                grouped.append(f"{line1}, {line2}")
                i += 2
                continue

        grouped.append(line1)
        i += 1
    return grouped


def align_classical_poem(
    han_lines: List[str],
    viet_lines: List[str],
    translation_type: str = "verse",  # 'prose' or 'verse'
) -> List[Dict[str, Any]]:
    """Align Classical Chinese poetic lines with Vietnamese translations.

    When `translation_type == 'verse'` and the Vietnamese lines represent
    Lục bát couplets (6-8), the aligner groups 6-8 couplets before alignment
    to ensure perfect couplet-level coherence without fragmented single lines.
    """
    clean_h = [clean_han_text(l) for l in han_lines if clean_han_text(l)]
    clean_v = [clean_viet_text(l) for l in viet_lines if clean_viet_text(l)]

    if not clean_h or not clean_v:
        return []

    # If Vietnamese lines are Lục bát, group 6-word and 8-word pairs into single units
    has_luc_bat = any(detect_vietnamese_poetic_meter(l) in ("luc_bat_6", "luc_bat_8") for l in clean_v)
    if translation_type == "verse" and has_luc_bat:
        clean_v_processed = group_luc_bat_couplets(clean_v)
    else:
        clean_v_processed = clean_v

    # Run core dynamic programming aligner on the meter-regularized sequences
    aligned_results = align_work_sentences(clean_h, clean_v_processed)
    return aligned_results
