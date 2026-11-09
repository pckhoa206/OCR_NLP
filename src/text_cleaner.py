"""Non-destructive text cleaning and sentence segmentation for Hán-Việt corpora.

Implements Steps 5 & 6 of Guideline.pdf:
- Unicode NFC normalization and control/artifact character removal.
- Classical Chinese (Hán văn) text cleaning and punctuation normalization.
- Vietnamese translation text cleaning, header/footer/label removal, footnote
  stripping, and line-wrap hyphenation merging.
- Punctuation and clause-aware sentence segmentation for both Hán and Việt.
"""

from __future__ import annotations

import re
import unicodedata

# Zero-width, BOM, soft-hyphen, and object replacement characters
_ZERO_WIDTH_AND_ARTIFACTS_RE = re.compile(
    r"[\u00ad\u200b\u200c\u200d\u200e\u200f\u2060\ufeff\ufffc\ufffd]"
)

# C0/C1 control characters except \t (\x09), \n (\x0a), \r (\x0d)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# Horizontal whitespace (excluding \n)
_HORIZ_WHITESPACE_RE = re.compile(r"[^\S\n]+")

# Footnote markers in Hán or Việt text:
# e.g., 1*, 23*, [1], [12], (1)..(99), （1）, 〔1〕, superscripts, circled numbers
_FOOTNOTE_BRACKET_RE = re.compile(
    r"(?:\[\s*\d{1,3}\s*\]|\(\s*\d{1,2}\s*\)|（\s*\d{1,3}\s*）|〔\s*\d{1,3}\s*〕|【\s*\d{1,3}\s*】)"
)
_FOOTNOTE_STAR_RE = re.compile(r"(?:(?<!\d)\d{1,3}\s*\*+|\*+\d{0,3})")
_SUPERSCRIPTS_RE = re.compile(
    r"[¹²³⁴⁵⁶⁷⁸⁹⁰⁺⁻⁼⁽⁾\u2460-\u2473\u24ea\u3251-\u325f\u32b1-\u32bf]+"
)

# Allowed CJK characters and CJK punctuation (including lacunae □ ■)
_VALID_HAN_CHAR_RE = re.compile(
    r"[\u3007\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
    r"\U00020000-\U0002ebef"
    r"\u25a0-\u25a3"
    r"，。！？；：「」『』、（）《》〈〉【】—…·]"
)
_CJK_IDEOGRAPH_RE = re.compile(
    r"[\u3007\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002ebef\u25a0-\u25a3]"
)

# Empty brackets left over after removing non-CJK inside them
_EMPTY_CJK_BRACKETS_RE = re.compile(r"(?:（）|「」|『』|【】|《》|〈〉)+")

# Repeated CJK sentence punctuation
_REPEATED_CJK_PUNCT_RE = re.compile(r"([，。！？；：、])\1+")

# Leading stray CJK punctuation at the start of a sentence
_LEADING_CJK_PUNCT_RE = re.compile(r"^[，。！？；：、）》〉】」』]+")

# Running headers, footers, and standalone page numbers in Vietnamese OCR/PDF
_VIET_HEADER_FOOTER_LINE_RE = re.compile(
    r"^\s*(?:"
    r"(?:Trang|Page)\s*\d+\s*|"
    r"[-—–~·•*\s]*\d{1,4}[-—–~·•*\s]*|"
    r"(?:\d+\s+)?HÁN[\s\-—–]+VĂN\s+TINH[\s\-—–]+T(?:ÚY|UÝ)(?:\s*[-—–]\s*[^\n]*)?(?:\s+\d+)?|"
    r"(?:\d+\s+)?THƠ\s+VĂN\s+LÝ[\s\-—–]+TRẦN[^\n]*|"
    r"(?:\d+\s+)?THỂ\s+LOẠI\s+TỪ\s+(?:VIỆT\s+NAM|VN)\s+THỜI\s+TRUNG\s+ĐẠI[^\n]*|"
    r"CỔ\s+VĂN\s+QUAN\s+CHỈ(?:\s*[-—–]\s*[^\n]*)?|"
    r"ĐẠI\s+VIỆT\s+SỬ\s+KÝ\s+TOÀN\s+THƯ(?:\s*[-—–]\s*[^\n]*)?"
    r")\s*$",
    re.IGNORECASE,
)

# Section labels (inline or line-initial)
_VIET_SECTION_LABEL_RE = re.compile(
    r"(?i)\b(?:"
    r"PHIÊN\s*ÂM|DỊCH\s*NGHĨA|DỊCH\s*THƠ|DỊCH\s*XUÔI|DỊCH\s*THEO\s*NGUYÊN\s*ĐIỆU|"
    r"NGUYÊN\s*VĂN|NGUYÊN\s*TÁC|BÀI\s*DỊCH|CHÚ\s*THÍCH|KHẢO\s*ĐÍNH|CÁC\s*DỊ\s*BẢN|LỜI\s*BÌNH|GIẢI\s*NGHĨA"
    r")\s*[:：.\-—–]*\s*"
)

# Hyphenated word break across a line wrap
_LINE_WRAP_HYPHEN_RE = re.compile(r"([A-Za-zÀ-ỹà-ỹ])-\s*\n\s*([A-Za-zÀ-ỹà-ỹ])")

# Common Vietnamese abbreviations with dots to protect during sentence splitting
_ABBREVIATIONS_LIST = [
    # Multi-part titles & common expressions
    r"PGS\.TS\.",
    r"GS\.TS\.",
    r"TS\.BS\.",
    r"v\.v\.\.\.",
    r"v\.v\.",
    # Single-part abbreviations (case-insensitive or title-case)
    r"PGS\.",
    r"GS\.",
    r"TS\.",
    r"ThS\.",
    r"BS\.",
    r"KS\.",
    r"CN\.",
    r"NXB\.",
    r"Nxb\.",
    r"Tr\.",
    r"tr\.",
    r"Sđd\.",
    r"sđd\.",
    r"Tlđd\.",
    r"tlđd\.",
    r"Tp\.",
    r"TP\.",
    r"Q\.",
    r"q\.",
    r"T\.",
    r"Ch\.",
    r"ch\.",
    r"St\.",
    r"BT\.",
    r"TG\.",
    r"ND\.",
    r"Đd\.",
    r"Bđd\.",
]
_ABBREV_RE = re.compile(
    r"(?<!\w)(?:" + "|".join(_ABBREVIATIONS_LIST) + r")"
)

# Personal name / place name initials like "Nguyễn V. A" or "H. C. Minh"
_INITIALS_RE = re.compile(
    r"\b([A-ZĐÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ])\."
    r"(?=\s+[A-ZĐÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ])"
)

# Numbered list prefix at start of text/line like "1. " or "II. "
_LIST_PREFIX_RE = re.compile(r"(?:^|(?<=\n))\s*(\d{1,3}|[IVXLCDM]{1,6})\.(?=\s+)")

# Dots inside numbers like 3.14 or 1.000
_DECIMAL_DOT_RE = re.compile(r"(?<=\d)\.(?=\d)")

# Colons inside time or ratios like 10:30
_TIME_COLON_RE = re.compile(r"(?<=\d):(?=\d)")

_DOT_PLACEHOLDER = "\ufff0"
_COLON_PLACEHOLDER = "\ufff1"


def normalize_unicode_nfc(text: str) -> str:
    """Convert decomposed NFD strings to composed NFC and clean whitespace/artifacts.

    Non-destructively returns a new string with:
    - Unicode NFC composition (essential for Vietnamese diacritics).
    - Removal of zero-width characters, soft hyphens, and object replacement `\\ufffc`.
    - Normalized line endings (`\\r\\n` / `\\r` -> `\\n`) and collapsed horizontal spaces.
    """
    if not text:
        return ""
    out = unicodedata.normalize("NFC", str(text))
    out = _ZERO_WIDTH_AND_ARTIFACTS_RE.sub("", out)
    out = _CONTROL_CHARS_RE.sub("", out)
    out = out.replace("\r\n", "\n").replace("\r", "\n")
    out = _HORIZ_WHITESPACE_RE.sub(" ", out)
    out = re.sub(r" *\n *", "\n", out)
    return out.strip()


def clean_han_text(text: str) -> str:
    """Clean Classical Chinese (Hán văn) text non-destructively.

    Removes embedded footnote markers (`1*`, `23*`, `[1]`, `(1)`, superscripts),
    section labels, and Latin/Vietnamese OCR noise while keeping valid CJK ideographs
    and CJK punctuation (`，。！？；：「」『』、`). Guarantees no `\\t` or `\\n` inside the result.
    """
    if not text:
        return ""
    out = normalize_unicode_nfc(text)

    # Remove section labels first so punctuation after labels (like ':') doesn't turn into '：'
    out = _VIET_SECTION_LABEL_RE.sub("", out)

    # Remove footnote markers before punctuation normalization
    out = _FOOTNOTE_BRACKET_RE.sub("", out)
    out = _FOOTNOTE_STAR_RE.sub("", out)
    out = _SUPERSCRIPTS_RE.sub("", out)

    # Convert ASCII punctuation immediately following a CJK character into fullwidth CJK punctuation
    _ascii_punct_map = {
        ",": "，",
        ".": "。",
        ";": "；",
        ":": "：",
        "?": "？",
        "!": "！",
    }
    out = re.sub(
        r"(?<=[\u3007\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff])\s*([.,;:?!])",
        lambda m: _ascii_punct_map[m.group(1)],
        out,
    )

    # Retain only valid CJK ideographs and CJK punctuation
    kept_chars = _VALID_HAN_CHAR_RE.findall(out)
    out = "".join(kept_chars)

    # Remove empty brackets and repeated/leading stray punctuation
    out = _EMPTY_CJK_BRACKETS_RE.sub("", out)
    out = _REPEATED_CJK_PUNCT_RE.sub(r"\1", out)
    out = _LEADING_CJK_PUNCT_RE.sub("", out)

    # If the resulting string has no CJK ideographs at all, return empty string
    if not _CJK_IDEOGRAPH_RE.search(out):
        return ""

    return out.strip()


def clean_viet_text(text: str) -> str:
    """Clean Vietnamese translation text non-destructively.

    Removes running headers/footers, section labels (`PHIÊN ÂM :`, `DỊCH NGHĨA :`),
    footnote markers (`1*`, `[1]`, `(1)`, superscripts), merges hyphenated words
    across line wraps, and guarantees no `\\t` or `\\n` remains inside a single sentence.
    """
    if not text:
        return ""
    out = normalize_unicode_nfc(text)

    # Drop standalone header/footer/page-number lines when multi-line input is given
    lines = out.split("\n")
    cleaned_lines: list[str] = []
    for line in lines:
        if _VIET_HEADER_FOOTER_LINE_RE.match(line):
            continue
        # Deduplicate consecutive identical OCR lines (Step 5)
        if cleaned_lines and line.strip() and line.strip() == cleaned_lines[-1].strip():
            continue
        cleaned_lines.append(line)
    out = "\n".join(cleaned_lines)

    # Merge hyphenated line wraps across page/line breaks
    out = _LINE_WRAP_HYPHEN_RE.sub(r"\1\2", out)

    # Remove section labels and footnote markers
    out = _VIET_SECTION_LABEL_RE.sub("", out)
    out = _FOOTNOTE_BRACKET_RE.sub("", out)
    out = _FOOTNOTE_STAR_RE.sub("", out)
    out = _SUPERSCRIPTS_RE.sub("", out)

    # Remove any stray CJK characters that leaked into the Vietnamese side
    out = _CJK_IDEOGRAPH_RE.sub("", out)

    # Replace any remaining newlines/tabs with single space
    out = re.sub(r"[\r\n\t]+", " ", out)

    # Normalize spacing around standard punctuation
    out = re.sub(r"\s+([,.;:!?)\]])", r"\1", out)
    out = re.sub(r"([(\[])\s+", r"\1", out)
    out = re.sub(r"([,;!?])(?=[A-Za-zÀ-ỹà-ỹ])", r"\1 ", out)

    # Collapse multiple spaces
    out = re.sub(r" {2,}", " ", out)
    return out.strip()


def split_han_sentences(text: str, mode: str = "clause_or_sent") -> list[str]:
    """Split Classical Chinese text into sentences or clauses per Step 6 of Guideline.pdf.

    Args:
        text: Raw or cleaned Hán text.
        mode:
            - `"clause_or_sent"` or `"sent"`: splits on `。！？；` (attaching closing quotes)
              as well as line breaks for poetry/interlinear blocks.
            - `"clause"`: additionally splits on `，`.
            - `"line"`: splits strictly on line breaks `\\n`.

    Returns:
        List of cleaned, non-empty Hán sentences.
    """
    if not text:
        return []
    norm = normalize_unicode_nfc(text)
    raw_lines = [ln for ln in norm.split("\n") if ln.strip()]

    if mode == "line":
        results: list[str] = []
        for ln in raw_lines:
            cleaned = clean_han_text(ln)
            if cleaned:
                results.append(cleaned)
        return results

    # Punctuation pattern to split after, keeping any trailing closing brackets/quotes
    if mode == "clause":
        split_re = re.compile(r"([。！？；，]+[」』）》〉】]*)")
    else:
        split_re = re.compile(r"([。！？；]+[」』）》〉】]*)")

    sentences: list[str] = []
    for ln in raw_lines:
        cleaned_ln = clean_han_text(ln)
        if not cleaned_ln:
            continue
        parts = split_re.split(cleaned_ln)
        buf = ""
        for idx, part in enumerate(parts):
            if idx % 2 == 0:
                buf += part
            else:
                buf += part
                sent = clean_han_text(buf)
                if sent:
                    sentences.append(sent)
                buf = ""
        if buf.strip():
            tail = clean_han_text(buf)
            if tail:
                sentences.append(tail)

    return sentences


def split_viet_sentences(text: str, mode: str = "clause_or_sent") -> list[str]:
    """Split Vietnamese text into sentences/clauses while protecting abbreviations.

    Protects abbreviations and personal/place names with dots (e.g. `Tr.`, `NXB.`,
    `PGS.TS.`, `Tp.`, `v.v.`, single-letter initials `H.`) and decimal numbers
    before splitting on `.?!;:` (or `.?!` when `mode == "sent"`).

    Args:
        text: Raw or cleaned Vietnamese text.
        mode:
            - `"clause_or_sent"` (default): splits on `.?!;:`
            - `"sent"`: splits on `.?!`
            - `"line"`: splits strictly on line breaks `\\n`.

    Returns:
        List of cleaned, non-empty Vietnamese sentences.
    """
    if not text:
        return []
    norm = normalize_unicode_nfc(text)

    if mode == "line":
        results: list[str] = []
        for ln in norm.split("\n"):
            cleaned = clean_viet_text(ln)
            if cleaned:
                results.append(cleaned)
        return results

    # Pre-clean headers, footers, section labels, and line-wrap hyphens
    cleaned_full = clean_viet_text(norm)
    if not cleaned_full:
        return []

    # Protect dots in known abbreviations, initials, list numbers, and decimals
    protected = _ABBREV_RE.sub(
        lambda m: m.group(0).replace(".", _DOT_PLACEHOLDER), cleaned_full
    )
    protected = _INITIALS_RE.sub(rf"\1{_DOT_PLACEHOLDER}", protected)
    protected = _LIST_PREFIX_RE.sub(rf"\1{_DOT_PLACEHOLDER}", protected)
    protected = _DECIMAL_DOT_RE.sub(_DOT_PLACEHOLDER, protected)
    protected = _TIME_COLON_RE.sub(_COLON_PLACEHOLDER, protected)

    # Protect ellipses (...) so we don't split inside them mid-sentence unless followed by capital
    protected = re.sub(
        r"\.{3}(?=\s+[a-zà-ỹ])",
        _DOT_PLACEHOLDER * 3,
        protected,
    )

    if mode == "sent":
        delim_re = re.compile(r"([.?!]+[\"'”’)\]]*)\s*")
    else:
        delim_re = re.compile(r"([.?!;:]+[\"'”’)\]]*)\s*")

    parts = delim_re.split(protected)
    sentences: list[str] = []
    buf = ""
    for idx, part in enumerate(parts):
        if idx % 2 == 0:
            buf += part
        else:
            buf += part
            restored = (
                buf.replace(_DOT_PLACEHOLDER, ".")
                .replace(_COLON_PLACEHOLDER, ":")
                .strip()
            )
            cleaned_sent = clean_viet_text(restored)
            if cleaned_sent:
                sentences.append(cleaned_sent)
            buf = ""

    if buf.strip():
        restored = (
            buf.replace(_DOT_PLACEHOLDER, ".")
            .replace(_COLON_PLACEHOLDER, ":")
            .strip()
        )
        cleaned_sent = clean_viet_text(restored)
        if cleaned_sent:
            sentences.append(cleaned_sent)

    return sentences
