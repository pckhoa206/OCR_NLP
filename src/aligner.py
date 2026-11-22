"""Work-bounded Hán-Việt sentence and block alignment engine.

Implements Step 7 and Section 3.1 of Guideline.pdf:
- Supports alignment types `1-1`, `1-n` (`1-2`, `1-3`, ...), `n-1` (`2-1`, `3-1`, ...),
  and `n-m` (`2-2`).
- `align_interlinear_blocks`: aligns 3-line interlinear blocks `(han, phien_am, dich_nghia)`
  from Hán Văn Tinh Túy even pages.
- `align_work_sentences`: dynamic programming aligner using the Classical Chinese
  character-to-Vietnamese word length ratio prior (1 Hán char ≈ 1.8 Việt words),
  lexical/numeric/punctuation anchors, and optional semantic similarity matrix
  (from Bertalign / LaBSE / BGE-M3). Strictly bounded within a single work/poem.
"""

from __future__ import annotations

import math
import re
from typing import Any

from src.text_cleaner import clean_han_text, clean_viet_text

# Target length ratio: 1 Classical Chinese character ≈ 1.8 Vietnamese words
HAN_TO_VIET_WORD_RATIO: float = 1.8
HAN_TO_VIET_VARIANCE: float = 1.25

# Allowed DP transitions (d_han, d_viet) and their structural priors per Section 3.1
# "Ưu tiên đơn vị nhỏ nhất có ý nghĩa đầy đủ."
BEAD_PRIORS: dict[tuple[int, int], float] = {
    (1, 1): 1.00,
    (1, 2): 0.94,
    (2, 1): 0.94,
    (1, 3): 0.88,
    (3, 1): 0.88,
    (2, 2): 0.84,
    (1, 4): 0.78,
    (4, 1): 0.78,
    (2, 3): 0.80,
    (3, 2): 0.80,
}

_CJK_CHAR_RE = re.compile(
    r"[\u3007\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002ebef\u25a0-\u25a3]"
)
_VIET_WORD_RE = re.compile(r"[A-Za-zÀ-ỹà-ỹ0-9]+")

# Number and concept anchors for offline similarity scoring
_NUMERIC_ANCHORS: list[tuple[str, tuple[str, ...]]] = [
    ("一", ("một", "nhất", "đầu", "nguyên", "1")),
    ("二", ("hai", "nhị", "lưỡng", "đôi", "2")),
    ("兩", ("hai", "lưỡng", "đôi", "2")),
    ("三", ("ba", "tam", "3")),
    ("四", ("bốn", "tứ", "4")),
    ("五", ("năm", "ngũ", "5")),
    ("六", ("sáu", "lục", "6")),
    ("七", ("bảy", "thất", "7")),
    ("八", ("tám", "bát", "8")),
    ("九", ("chín", "cửu", "9")),
    ("十", ("mười", "thập", "chục", "10")),
    ("百", ("trăm", "bách", "100")),
    ("千", ("nghìn", "ngàn", "thiên", "1000", "1.000")),
    ("萬", ("vạn", "muôn", "10000", "10.000")),
    ("半", ("nửa", "rưỡi", "bán")),
]

_LEXICAL_ANCHORS: list[tuple[str, tuple[str, ...]]] = [
    ("王", ("vua", "vương", "chúa")),
    ("帝", ("đế", "vua", "hoàng")),
    ("朕", ("trẫm",)),
    ("佛", ("phật",)),
    ("師", ("sư", "thầy")),
    ("禪", ("thiền",)),
    ("道", ("đạo", "đường")),
    ("教", ("giáo", "dạy")),
    ("天", ("trời", "thiên")),
    ("地", ("đất", "địa")),
    ("山", ("núi", "sơn", "non")),
    ("水", ("nước", "thủy", "sông")),
    ("人", ("người", "nhân", "kẻ")),
    ("心", ("lòng", "tâm", "dạ")),
    ("國", ("nước", "quốc")),
    ("民", ("dân", "người")),
    ("君", ("vua", "quân", "chàng")),
    ("臣", ("tôi", "thần", "quan")),
    ("父", ("cha", "phụ", "bố")),
    ("母", ("mẹ", "mẫu")),
    ("子", ("con", "tử", "thầy")),
    ("年", ("năm", "niên", "tuổi")),
    ("月", ("tháng", "trăng", "nguyệt")),
    ("日", ("ngày", "nhật", "mặt trời")),
    ("春", ("xuân", "mùa xuân")),
    ("秋", ("thu", "mùa thu")),
    ("南", ("nam", "phương nam")),
    ("北", ("bắc", "phương bắc")),
    ("東", ("đông", "phương đông")),
    ("西", ("tây", "phương tây")),
    ("越", ("việt",)),
    ("交", ("giao",)),
    ("周", ("chu",)),
    ("漢", ("hán",)),
    ("唐", ("đường",)),
    ("宋", ("tống",)),
    ("死", ("chết", "tử", "mất")),
    ("生", ("sống", "sinh", "đời")),
]


def count_han_chars(text: str) -> int:
    """Count CJK ideographs in a Hán string."""
    return len(_CJK_CHAR_RE.findall(text))


def count_viet_words(text: str) -> int:
    """Count word/syllable tokens in a Vietnamese string."""
    return len(_VIET_WORD_RE.findall(text))


def compute_length_ratio_score(
    han_text: str,
    viet_text: str,
    target_ratio: float = HAN_TO_VIET_WORD_RATIO,
) -> float:
    """Compute length-ratio prior score in (0, 1] given Hán and Việt strings.

    Classical Chinese to Vietnamese word ratio naturally spans [0.80, 2.40]
    (with philosophical prose around 0.9–1.3 and ornate verse around 1.5–2.2).
    A plateau in [0.80, 2.40] provides score 1.0, with smooth Gaussian dropoff
    outside this range.
    """
    n_han = max(1, count_han_chars(han_text))
    n_viet = max(1, count_viet_words(viet_text))
    ratio = n_viet / n_han
    if 0.80 <= ratio <= 2.40:
        return 1.0
    elif ratio < 0.80:
        diff = 0.80 - ratio
        return math.exp(-0.5 * ((diff / 0.25) ** 2))
    else:
        diff = ratio - 2.40
        return math.exp(-0.5 * ((diff / 0.80) ** 2))


def compute_anchor_similarity(han_text: str, viet_text: str) -> float:
    """Compute offline lexical, numeric, and punctuation anchor similarity in [0, 1]."""
    if not han_text or not viet_text:
        return 0.0

    viet_lower = viet_text.lower()
    viet_tokens = set(_VIET_WORD_RE.findall(viet_lower))

    matches = 0.0
    checks = 0.0

    # 1. Punctuation / Sentence-type anchors
    han_has_q = "？" in han_text or "?" in han_text
    viet_has_q = "?" in viet_text
    if han_has_q or viet_has_q:
        checks += 1.0
        if han_has_q == viet_has_q:
            matches += 1.0

    han_has_ex = "！" in han_text or "!" in han_text
    viet_has_ex = "!" in viet_text
    if han_has_ex or viet_has_ex:
        checks += 0.8
        if han_has_ex == viet_has_ex:
            matches += 0.8

    # Dialogue markers
    han_has_quote = any(c in han_text for c in ("曰", "云", "謂", "問", "答", "「", "『"))
    viet_has_quote = any(
        w in viet_tokens for w in ("nói", "rằng", "hỏi", "đáp", "bảo", "thưa")
    ) or any(c in viet_text for c in (":", '"', "“", "”"))
    if han_has_quote:
        checks += 0.8
        if viet_has_quote:
            matches += 0.8

    # 2. Numeric anchors
    for han_num, viet_equivalents in _NUMERIC_ANCHORS:
        if han_num in han_text:
            checks += 1.2
            if any(
                (eq in viet_tokens if " " not in eq else eq in viet_lower)
                for eq in viet_equivalents
            ):
                matches += 1.2

    # 3. Lexical anchors
    for han_char, viet_equivalents in _LEXICAL_ANCHORS:
        if han_char in han_text:
            checks += 0.7
            if any(
                (eq in viet_tokens if " " not in eq else eq in viet_lower)
                for eq in viet_equivalents
            ):
                matches += 0.7

    if checks == 0.0:
        return 0.5  # Neutral baseline when no specific anchors appear
    return min(1.0, max(0.0, (matches + 0.5) / (checks + 1.0)))


def align_interlinear_blocks(blocks: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Align 3-line interlinear blocks from Hán Văn Tinh Túy even pages.

    Each block dictionary typically contains `(han, phien_am, dich_nghia)`
    (also accepts keys like `han_text`/`cjk` and `viet`/`viet_text`/`translation`,
    or 2/3-element tuples/lists).
    Handles empty-side continuation merges (`1-n` or `n-1`) if a block wraps across lines.

    Args:
        blocks: List of interlinear block dicts (or tuples).

    Returns:
        List of cleaned `(han, viet)` sentence pairs.
    """
    if not blocks:
        return []

    aligned_pairs: list[tuple[str, str]] = []
    is_title_flags: list[bool] = []
    pending_han: list[str] = []

    for blk in blocks:
        raw_han = ""
        raw_viet = ""
        raw_phien_am = ""
        blk_is_title = bool(isinstance(blk, dict) and blk.get("is_title"))

        if isinstance(blk, dict):
            raw_han = str(
                blk.get("han")
                or blk.get("han_text")
                or blk.get("raw_han")
                or blk.get("cjk")
                or blk.get("source")
                or ""
            )
            raw_viet = str(
                blk.get("dich_nghia")
                or blk.get("viet")
                or blk.get("viet_text")
                or blk.get("raw_viet")
                or blk.get("translation")
                or blk.get("target")
                or ""
            )
            raw_phien_am = str(blk.get("phien_am") or "")
        elif isinstance(blk, (tuple, list)):
            if len(blk) >= 3:
                raw_han = str(blk[0] or "")
                raw_phien_am = str(blk[1] or "")
                raw_viet = str(blk[2] or "")
            elif len(blk) == 2:
                raw_han = str(blk[0] or "")
                raw_viet = str(blk[1] or "")

        cleaned_han = clean_han_text(raw_han)
        cleaned_viet = clean_viet_text(raw_viet)

        # Fallback: only if dich_nghia is completely absent and phien_am was placed there
        if not cleaned_viet and raw_phien_am and not raw_viet:
            cleaned_viet = clean_viet_text(raw_phien_am)

        if cleaned_han and cleaned_viet:
            if pending_han:
                merged_han = "".join(pending_han) + cleaned_han
                pending_han.clear()
                aligned_pairs.append((merged_han, cleaned_viet))
                is_title_flags.append(blk_is_title)
            else:
                aligned_pairs.append((cleaned_han, cleaned_viet))
                is_title_flags.append(blk_is_title)
        elif cleaned_han and not cleaned_viet:
            # Buffer Hán to merge with the next block (n-1)
            pending_han.append(cleaned_han)
        elif cleaned_viet and not cleaned_han and aligned_pairs and not is_title_flags[-1]:
            # Continuation of Vietnamese translation from previous non-title block (1-n)
            prev_h, prev_v = aligned_pairs[-1]
            aligned_pairs[-1] = (prev_h, clean_viet_text(f"{prev_v} {cleaned_viet}"))

    # If trailing pending_han remains and we already have at least one pair, attach to last non-title pair
    if pending_han and aligned_pairs and not is_title_flags[-1]:
        prev_h, prev_v = aligned_pairs[-1]
        aligned_pairs[-1] = (prev_h + "".join(pending_han), prev_v)

    return aligned_pairs


def align_interlinear_4col_blocks(
    blocks: list[dict[str, Any]],
) -> list[tuple[str, str, str, str]]:
    """Align 4-column blocks `(Hán, Dịch âm, Dịch nghĩa, Dịch thơ)` for Hán Văn Tinh Túy.

    Per instructor specification:
    - `Hán Văn Tinh Túy` has 4 columns: `Hán - Dịch âm - Dịch nghĩa - Dịch thơ`.
    - For the final poem (*Thu dạ hoài ngâm*, PDF pages 367-381) and verse-only works
      that only have `Hán - Dịch âm - Dịch thơ`, the `Dịch nghĩa` column is left blank (`""`).
    - For prose works or clauses where `Dịch thơ` is not applicable, `Dịch thơ` may be `""`.
    - Rows marked `is_title=True` are never merged with subsequent continuation rows.
    """
    if not blocks:
        return []

    aligned_rows: list[tuple[str, str, str, str]] = []
    is_title_flags: list[bool] = []
    for blk in blocks:
        raw_han = ""
        raw_dich_am = ""
        raw_dich_nghia = ""
        raw_dich_tho = ""
        blk_is_title = bool(isinstance(blk, dict) and blk.get("is_title"))

        if isinstance(blk, dict):
            raw_han = str(
                blk.get("han")
                or blk.get("han_text")
                or blk.get("raw_han")
                or blk.get("cjk")
                or ""
            )
            raw_dich_am = str(
                blk.get("dich_am")
                or blk.get("phien_am")
                or ""
            )
            raw_dich_nghia = str(
                blk.get("dich_nghia")
                if blk.get("dich_nghia") is not None
                else (blk.get("viet") or "")
            )
            raw_dich_tho = str(blk.get("dich_tho") or "")
        elif isinstance(blk, (tuple, list)):
            if len(blk) >= 4:
                raw_han = str(blk[0] or "")
                raw_dich_am = str(blk[1] or "")
                raw_dich_nghia = str(blk[2] or "")
                raw_dich_tho = str(blk[3] or "")
            elif len(blk) == 3:
                raw_han = str(blk[0] or "")
                raw_dich_am = str(blk[1] or "")
                raw_dich_nghia = str(blk[2] or "")

        cleaned_han = clean_han_text(raw_han)
        cleaned_dich_am = clean_viet_text(raw_dich_am) if raw_dich_am.strip() else ""
        cleaned_dich_nghia = (
            clean_viet_text(raw_dich_nghia) if raw_dich_nghia.strip() else ""
        )
        cleaned_dich_tho = (
            clean_viet_text(raw_dich_tho) if raw_dich_tho.strip() else ""
        )

        if cleaned_han and (cleaned_dich_am or cleaned_dich_nghia or cleaned_dich_tho):
            aligned_rows.append(
                (
                    cleaned_han,
                    cleaned_dich_am,
                    cleaned_dich_nghia,
                    cleaned_dich_tho,
                )
            )
            is_title_flags.append(blk_is_title)
        elif (
            not cleaned_han
            and not blk_is_title
            and aligned_rows
            and not is_title_flags[-1]
            and (cleaned_dich_nghia or cleaned_dich_tho)
        ):
            prev_h, prev_am, prev_ng, prev_th = aligned_rows[-1]
            new_ng = (
                clean_viet_text(f"{prev_ng} {cleaned_dich_nghia}")
                if cleaned_dich_nghia
                else prev_ng
            )
            new_th = (
                clean_viet_text(f"{prev_th} {cleaned_dich_tho}")
                if cleaned_dich_tho
                else prev_th
            )
            aligned_rows[-1] = (prev_h, prev_am, new_ng, new_th)

    return aligned_rows


def _token_overlap_score(text_a: str, text_b: str) -> float:
    """Compute lightweight normalized Vietnamese token overlap in [0, 1]."""
    if not text_a or not text_b:
        return 0.0
    toks_a = {t for t in _VIET_WORD_RE.findall(text_a.lower()) if len(t) >= 2}
    toks_b = {t for t in _VIET_WORD_RE.findall(text_b.lower()) if len(t) >= 2}
    if not toks_a or not toks_b:
        return 0.0
    overlap = len(toks_a & toks_b)
    return overlap / max(1.0, min(len(toks_a), len(toks_b)))


def align_hvtt_facing_dich_tho(
    han_rows: list[Any],
    dich_tho_lines: list[str],
    han_y_centers: list[float] | None = None,
    dt_y_centers: list[float] | None = None,
) -> list[str]:
    """Align facing-page `Dịch thơ` lines onto `Hán` rows without dropping any verse line.

    Supports:
    - Empty `dich_tho_lines` -> `[""] * len(han_rows)`
    - Exact `len(dich_tho_lines) == len(han_rows)` -> clean 1:1 pairing
    - `1-n` (more `Dịch thơ` lines than `Hán` rows) -> spread-level DP joining
      multi-line verse segments with `" / "`
    - `n-1` (fewer `Dịch thơ` lines than `Hán` rows) -> spread-level DP placing
      each `Dịch thơ` line on its best matching `Hán` row (using normalized y-center,
      relative index, length heuristic, and lexical/anchor overlap) and leaving
      untranslated rows as `""`.
    """
    n_h = len(han_rows)
    if n_h == 0:
        return []
    if not dich_tho_lines:
        return [""] * n_h

    han_texts: list[str] = []
    ref_texts: list[str] = []
    for row in han_rows:
        if isinstance(row, dict):
            h_txt = str(
                row.get("han")
                or row.get("han_text")
                or row.get("chu_han")
                or row.get("raw_han")
                or ""
            )
            r_txt = f"{row.get('dich_am') or row.get('phien_am') or ''} {row.get('dich_nghia') or ''}".strip()
        elif isinstance(row, (tuple, list)):
            h_txt = str(row[0] or "") if len(row) >= 1 else ""
            r_txt = " ".join(str(x or "") for x in row[1:3]).strip()
        else:
            h_txt = str(row or "")
            r_txt = ""
        han_texts.append(clean_han_text(h_txt) or h_txt.strip())
        ref_texts.append(clean_viet_text(r_txt) if r_txt else "")

    use_y = (
        han_y_centers is not None
        and dt_y_centers is not None
        and len(han_y_centers) == n_h
        and len(dt_y_centers) == len(dich_tho_lines)
        and any(y is not None and y > 0 for y in han_y_centers)
        and any(y is not None and y > 0 for y in dt_y_centers)
    )

    valid_dt: list[tuple[str, float | None]] = []
    for idx, line in enumerate(dich_tho_lines):
        cleaned = clean_viet_text(line)
        if not cleaned:
            continue
        y_val = float(dt_y_centers[idx]) if (use_y and dt_y_centers is not None) else None
        valid_dt.append((cleaned, y_val))

    n_dt = len(valid_dt)
    if n_dt == 0:
        return [""] * n_h
    if n_dt == n_h:
        return [dt for dt, _ in valid_dt]

    y_scale = 1.0
    if use_y and han_y_centers is not None:
        max_hy = max(float(y) for y in han_y_centers)
        max_dy = max((float(y) for _, y in valid_dt if y is not None), default=0.0)
        y_scale = max(1600.0, max_hy, max_dy) * 1.05

    def _score_assignment(i: int, j0: int, k: int) -> float:
        if k == 0:
            # Small skip baseline used only when n_dt < n_h
            return 0.05
        slice_dt = valid_dt[j0 : j0 + k]
        joined_dt = " / ".join(dt for dt, _ in slice_dt)
        h_txt = han_texts[i]
        r_txt = ref_texts[i]

        len_s = compute_length_ratio_score(h_txt, joined_dt)
        anc_s = compute_anchor_similarity(h_txt, joined_dt)
        ref_s = _token_overlap_score(r_txt, joined_dt) if r_txt else 0.0

        if use_y and han_y_centers is not None:
            h_pos = float(han_y_centers[i]) / y_scale
            ys = [y for _, y in slice_dt if y is not None]
            dt_pos = (sum(ys) / len(ys)) / y_scale if ys else (j0 + 0.5 * k) / n_dt
            pos_s = math.exp(-10.0 * ((h_pos - dt_pos) ** 2))
        else:
            h_pos = (i + 0.5) / n_h
            dt_pos = (j0 + 0.5 * k) / n_dt
            pos_s = math.exp(-7.0 * ((h_pos - dt_pos) ** 2))

        if k == 1:
            k_prior = 1.00
        elif k == 2:
            k_prior = 0.96
        elif k == 3:
            k_prior = 0.85
        elif k == 4:
            k_prior = 0.72
        else:
            k_prior = 0.55

        if r_txt:
            quality = 0.34 * len_s + 0.18 * anc_s + 0.18 * ref_s + 0.30 * pos_s
        else:
            quality = 0.42 * len_s + 0.23 * anc_s + 0.35 * pos_s

        # Multiply by (1 + 0.5*(k-1)) when n_dt > n_h so multi-line grouping competes fairly
        weight = (1.0 + 0.55 * (k - 1)) if n_dt > n_h else 1.0
        return weight * k_prior * (0.25 + quality)

    neg_inf = -1e9
    dp: list[list[float]] = [[neg_inf] * (n_dt + 1) for _ in range(n_h + 1)]
    back: list[list[int]] = [[-1] * (n_dt + 1) for _ in range(n_h + 1)]
    dp[0][0] = 0.0

    if n_dt > n_h:
        min_k = 1
        max_k = max(4, n_dt - n_h + 1)
    else:
        min_k = 0
        max_k = 2

    for i in range(n_h):
        rem_h = n_h - 1 - i
        for j in range(n_dt + 1):
            if dp[i][j] <= neg_inf / 2:
                continue
            rem_dt = n_dt - j
            if n_dt > n_h and rem_dt < rem_h + 1:
                continue
            hi_k = min(max_k, rem_dt)
            if n_dt > n_h:
                hi_k = min(hi_k, rem_dt - rem_h)
            for k in range(min_k, hi_k + 1):
                nj = j + k
                cand = dp[i][j] + _score_assignment(i, j, k)
                if cand > dp[i + 1][nj]:
                    dp[i + 1][nj] = cand
                    back[i + 1][nj] = k

    if back[n_h][n_dt] < 0:
        # Safe uniform fallback ensuring 0 lines dropped
        out = [""] * n_h
        for j, (dt_txt, _) in enumerate(valid_dt):
            target_i = min(n_h - 1, int(j * n_h / n_dt))
            out[target_i] = f"{out[target_i]} / {dt_txt}".strip(" /") if out[target_i] else dt_txt
        return out

    counts: list[int] = []
    ci, cj = n_h, n_dt
    while ci > 0:
        k = back[ci][cj]
        if k < 0:
            k = 0
        counts.append(k)
        cj -= k
        ci -= 1
    counts.reverse()

    aligned_dt: list[str] = []
    cursor = 0
    for k in counts:
        if k <= 0:
            aligned_dt.append("")
        else:
            aligned_dt.append(" / ".join(dt for dt, _ in valid_dt[cursor : cursor + k]))
            cursor += k
    return aligned_dt


def align_phien_am_to_han_chunks(
    han_chunks: list[str],
    pa_lines: list[str],
) -> list[str]:
    """Project `Phiên âm` lines onto aligned `Hán` sentence chunks using syllable-count + phonetic DP.

    Handles:
    - Full coverage (`0.75 <= pa_syls / han_chars <= 1.25`): monotonic DP partition
      matching Hán char counts to Sino-Vietnamese syllables with punctuation and
      `CORE_HAN_VIET_DICT` boundary bonuses.
    - Truncated prefix (`pa_syls < 0.75 * han_chars`, e.g., TVLT2 Work #3 before
      blank scan page): projects across the matching prefix chunks and leaves `""`
      for uncovered chunks.
    - Missing Hán middle blocks (`pa_syls > 1.25 * han_chars`, e.g., TVLT2 Work #8):
      splits `Phiên âm` into clauses and aligns via phonetic-anchor DP so skipped
      sections do not corrupt remaining rows.
    """
    n_h = len(han_chunks)
    if n_h == 0:
        return []
    cleaned_pa_lines = [clean_viet_text(ln) for ln in (pa_lines or []) if clean_viet_text(ln)]
    if not cleaned_pa_lines:
        return [""] * n_h

    from src.phonetic_verifier import CORE_HAN_VIET_DICT, normalize_viet_syllable

    joined_pa = clean_viet_text("\n".join(cleaned_pa_lines))
    raw_tokens = [t for t in joined_pa.split() if t]
    # Merge standalone punctuation tokens onto preceding token
    pa_tokens: list[str] = []
    for tok in raw_tokens:
        if not re.search(r"[A-Za-zÀ-ỹà-ỹ0-9]", tok):
            if pa_tokens and tok in (".", ",", ";", ":", "?", "!"):
                pa_tokens[-1] = f"{pa_tokens[-1]}{tok}"
            continue
        pa_tokens.append(tok)

    if not pa_tokens:
        return [""] * n_h

    def _syl_weight(tok: str) -> int:
        parts = [p for p in re.split(r"[-–—]", tok) if re.search(r"[A-Za-zÀ-ỹà-ỹ0-9]", p)]
        return max(1, len(parts))

    def _norm_tok(tok: str) -> str:
        base = re.sub(r"[^A-Za-zÀ-ỹà-ỹ]", "", tok.split("-")[0])
        return normalize_viet_syllable(base)

    def _norm_last_tok(tok: str) -> str:
        base = re.sub(r"[^A-Za-zÀ-ỹà-ỹ]", "", tok.split("-")[-1])
        return normalize_viet_syllable(base)

    def _char_matches_syl(ch: str, norm_syl: str) -> bool:
        if not ch or not norm_syl:
            return False
        readings = CORE_HAN_VIET_DICT.get(ch, [])
        return any(normalize_viet_syllable(r.split()[0]) == norm_syl for r in readings)

    tok_weights = [_syl_weight(t) for t in pa_tokens]
    total_pa_syls = sum(tok_weights)
    han_char_lists = [_CJK_CHAR_RE.findall(h) for h in han_chunks]
    han_counts = [max(1, len(chars)) for chars in han_char_lists]
    total_han_chars = sum(han_counts)

    # Case 3: PA has significantly more syllables than Hán (OCR missed some Hán lines)
    if total_han_chars > 0 and total_pa_syls > 1.28 * total_han_chars and n_h > 1:
        # Group PA into clause segments using punctuation, falling back to ~12-syl windows
        pa_clauses: list[str] = []
        buf: list[str] = []
        buf_w = 0
        for tok, w in zip(pa_tokens, tok_weights):
            buf.append(tok)
            buf_w += w
            if tok.endswith((".", "!", "?", ";", ":")) or (tok.endswith(",") and buf_w >= 6) or buf_w >= 16:
                pa_clauses.append(" ".join(buf))
                buf = []
                buf_w = 0
        if buf:
            pa_clauses.append(" ".join(buf))

        n_c = len(pa_clauses)
        if n_c >= n_h:
            clause_syls = [
                [normalize_viet_syllable(w) for w in _VIET_WORD_RE.findall(cl)]
                for cl in pa_clauses
            ]
            clause_weights = [max(1, len(s)) for s in clause_syls]

            def _phon_clause_score(hi: int, cj0: int, ck: int) -> float:
                h_chars = han_char_lists[hi]
                c_syls = [s for c_idx in range(cj0, cj0 + ck) for s in clause_syls[c_idx]]
                w_pa = sum(clause_weights[cj0 : cj0 + ck])
                target = max(1, len(h_chars))
                len_s = math.exp(-0.5 * (((w_pa - target) / max(2.5, 0.35 * target)) ** 2))
                # Phonetic overlap of known dictionary characters
                checked = 0
                matched = 0
                c_syl_set = set(c_syls)
                for ch in h_chars:
                    reads = CORE_HAN_VIET_DICT.get(ch)
                    if reads:
                        checked += 1
                        if any(normalize_viet_syllable(r.split()[0]) in c_syl_set for r in reads):
                            matched += 1
                phon_s = (matched / checked) if checked > 0 else 0.5
                pos_s = math.exp(-2.0 * (((hi + 0.5) / n_h) - ((cj0 + 0.5 * ck) / n_c)) ** 2)
                return 0.45 * len_s + 0.40 * phon_s + 0.15 * pos_s

            neg_inf = -1e9
            dp_c = [[neg_inf] * (n_c + 1) for _ in range(n_h + 1)]
            back_c: list[list[tuple[int, int] | None]] = [[None] * (n_c + 1) for _ in range(n_h + 1)]
            dp_c[0][0] = 0.0
            for i in range(n_h):
                for j in range(n_c + 1):
                    if dp_c[i][j] <= neg_inf / 2:
                        continue
                    # Allow skipping unmatched PA gap clauses before matching chunk i
                    if j < n_c:
                        skip_val = dp_c[i][j] - 0.02
                        if skip_val > dp_c[i][j + 1]:
                            dp_c[i][j + 1] = skip_val
                            back_c[i][j + 1] = (0, 1)
                    for ck in range(1, min(5, n_c - j + 1)):
                        val = dp_c[i][j] + 1.0 + _phon_clause_score(i, j, ck)
                        if val > dp_c[i + 1][j + ck]:
                            dp_c[i + 1][j + ck] = val
                            back_c[i + 1][j + ck] = (1, ck)
            # Allow trailing PA skip
            best_end_j = max(range(n_c + 1), key=lambda j: dp_c[n_h][j])
            if dp_c[n_h][best_end_j] > neg_inf / 2:
                out_c = [""] * n_h
                ci, cj = n_h, best_end_j
                while ci > 0 or cj > 0:
                    step = back_c[ci][cj]
                    if step is None:
                        break
                    dh, dc = step
                    if dh == 1:
                        out_c[ci - 1] = " ".join(pa_clauses[cj - dc : cj])
                    ci -= dh
                    cj -= dc
                return out_c

    # Case 2: Truncated prefix PA (e.g. TVLT2 Work #3 before blank page 25)
    active_n = n_h
    if total_han_chars > 0 and total_pa_syls < 0.72 * total_han_chars and n_h > 1:
        cum = 0
        best_m = 1
        best_diff = abs(han_counts[0] - total_pa_syls)
        for m in range(1, n_h + 1):
            cum += han_counts[m - 1]
            diff = abs(cum - total_pa_syls)
            if diff <= best_diff:
                best_diff = diff
                best_m = m
        active_n = best_m

    n_tok = len(pa_tokens)
    active_n = min(active_n, n_tok)
    active_han_chars = max(1, sum(han_counts[:active_n]))
    scale_ratio = total_pa_syls / active_han_chars
    if active_n <= 1:
        res = [clean_viet_text(" ".join(pa_tokens))] + [""] * (n_h - 1)
        return res

    # Prefix sums of syllable weights for O(1) span weight lookup
    pref_w = [0] * (n_tok + 1)
    for idx, w in enumerate(tok_weights):
        pref_w[idx + 1] = pref_w[idx] + w

    tok_first_norm = [_norm_tok(t) for t in pa_tokens]
    tok_last_norm = [_norm_last_tok(t) for t in pa_tokens]

    # Precompute expected cumulative token boundaries for beam search around target
    neg_inf = -1e9
    dp_p: list[list[float]] = [[neg_inf] * (n_tok + 1) for _ in range(active_n + 1)]
    back_p: list[list[int]] = [[-1] * (n_tok + 1) for _ in range(active_n + 1)]
    dp_p[0][0] = 0.0

    cum_target_syls = 0.0
    for i in range(active_n):
        target_w = max(1.0, han_counts[i] * scale_ratio)
        cum_target_syls += target_w
        h_chars = han_char_lists[i]
        h_ends_sent = han_chunks[i].rstrip("」』）》〉】").endswith(("。", "！", "？", "；"))
        h_first = h_chars[0] if h_chars else ""
        h_last = h_chars[-1] if h_chars else ""

        # Narrow search window around expected token index for speed on long essays
        min_j = i
        max_j = n_tok - (active_n - 1 - i)
        for j in range(min_j, max_j + 1):
            if dp_p[i][j] <= neg_inf / 2:
                continue
            # Scan k tokens forward so syllable weight is near target_w (bounded beam)
            lo_w = max(1.0, target_w * 0.45 - 2.0)
            hi_w = target_w * 1.65 + 4.0
            for nj in range(j + 1, max_j + 1):
                w_span = pref_w[nj] - pref_w[j]
                if w_span < lo_w and nj < max_j:
                    continue
                if w_span > hi_w and nj > j + 1:
                    break
                len_cost = ((w_span - target_w) ** 2) / max(4.0, target_w)
                bonus = 0.0
                end_tok = pa_tokens[nj - 1]
                if end_tok.endswith((".", "!", "?", ";")):
                    bonus += 0.65 if h_ends_sent else 0.20
                elif end_tok.endswith((":", ",")):
                    bonus += 0.20
                if h_first and _char_matches_syl(h_first, tok_first_norm[j]):
                    bonus += 0.30
                if h_last and _char_matches_syl(h_last, tok_last_norm[nj - 1]):
                    bonus += 0.30
                cand = dp_p[i][j] - len_cost + bonus
                if cand > dp_p[i + 1][nj]:
                    dp_p[i + 1][nj] = cand
                    back_p[i + 1][nj] = j

    if back_p[active_n][n_tok] < 0:
        # Proportional token split fallback
        out_fb = [""] * n_h
        cur_t = 0
        for i in range(active_n):
            take = (
                n_tok - cur_t
                if i == active_n - 1
                else max(1, min(n_tok - cur_t - (active_n - 1 - i), round(han_counts[i] * scale_ratio)))
            )
            out_fb[i] = clean_viet_text(" ".join(pa_tokens[cur_t : cur_t + take]))
            cur_t += take
        return out_fb

    bounds = [n_tok]
    curr_j = n_tok
    for i in range(active_n, 0, -1):
        prev_j = back_p[i][curr_j]
        bounds.append(prev_j)
        curr_j = prev_j
    bounds.reverse()

    result = [""] * n_h
    for i in range(active_n):
        result[i] = clean_viet_text(" ".join(pa_tokens[bounds[i] : bounds[i + 1]]))
    return result


def align_work_sentences(
    han_sents: list[str],
    viet_sents: list[str],
    sim_matrix: list[list[float]] | None = None,
) -> list[dict[str, Any]]:
    """Align Hán and Việt sentences within a single work/poem using Dynamic Programming.

    Supports alignment types `1-1`, `1-2`, `2-1`, `1-3`, `3-1`, `2-2` (and fallback
    `1-n` / `n-1` when extreme length imbalance occurs), combining:
    1. Character-to-word length ratio prior (1 Hán char ≈ 1.8 Việt words).
    2. Semantic similarity matrix (`sim_matrix` from Bertalign/LaBSE/BGE-M3 when provided,
       or offline lexical/numeric/punctuation anchor similarity fallback).
    3. Diagonal position coherence within the single work boundary.

    Args:
        han_sents: List of Hán sentences belonging to a single work.
        viet_sents: List of Việt sentences belonging to the same work.
        sim_matrix: Optional 2D similarity matrix of shape `[len(han_sents)][len(viet_sents)]`
            with values in `[0.0, 1.0]` (or `[-1.0, 1.0]`).

    Returns:
        List of alignment dictionaries, each containing:
        - `"han"`: aligned Hán string
        - `"viet"`: aligned Việt string
        - `"align_type"` / `"type"`: e.g. `"1-1"`, `"1-2"`, `"2-1"`, `"1-3"`, `"3-1"`, `"2-2"`
        - `"han_indices"`: list of 0-based Hán sentence indices
        - `"viet_indices"`: list of 0-based Việt sentence indices
        - `"score"`: float confidence score
        - `"pair"`: `(han_str, viet_str)` tuple
    """
    # Clean sentences while tracking original indices for sim_matrix lookup
    clean_h_items: list[tuple[int, str]] = []
    for idx, s in enumerate(han_sents or []):
        c = clean_han_text(s)
        if c:
            clean_h_items.append((idx, c))

    clean_v_items: list[tuple[int, str]] = []
    for idx, s in enumerate(viet_sents or []):
        c = clean_viet_text(s)
        if c:
            clean_v_items.append((idx, c))

    n_h = len(clean_h_items)
    n_v = len(clean_v_items)
    if n_h == 0 or n_v == 0:
        return []

    # Auto-compute cross-lingual semantic similarity matrix if not provided
    if sim_matrix is None and n_h > 1 and n_v > 1:
        try:
            from src.semantic_scorer import CrossLingualSemanticScorer
            scorer = CrossLingualSemanticScorer(prefer_neural=True)
            sim_matrix = scorer.compute_similarity_matrix(
                [item[1] for item in clean_h_items],
                [item[1] for item in clean_v_items],
            )
        except Exception:
            sim_matrix = None

    # Trivial 1-pair case
    if n_h == 1 and n_v == 1:
        h_str = clean_h_items[0][1]
        v_str = clean_v_items[0][1]
        score = compute_length_ratio_score(h_str, v_str)
        return [
            {
                "han": h_str,
                "viet": v_str,
                "align_type": "1-1",
                "type": "1-1",
                "han_indices": [clean_h_items[0][0]],
                "viet_indices": [clean_v_items[0][0]],
                "score": round(float(score), 4),
                "pair": (h_str, v_str),
            }
        ]

    def _get_pair_sim(h_pos: int, v_pos: int) -> float:
        orig_h_idx, h_txt = clean_h_items[h_pos]
        orig_v_idx, v_txt = clean_v_items[v_pos]
        anchor_sim = compute_anchor_similarity(h_txt, v_txt)
        if (
            sim_matrix is not None
            and 0 <= orig_h_idx < len(sim_matrix)
            and 0 <= orig_v_idx < len(sim_matrix[orig_h_idx])
        ):
            raw_sim = float(sim_matrix[orig_h_idx][orig_v_idx])
            # Clamp cosine similarity into [0, 1]
            sem_sim = max(0.0, min(1.0, (raw_sim + 1.0) / 2.0 if raw_sim < 0 else raw_sim))
            return 0.75 * sem_sim + 0.25 * anchor_sim
        return anchor_sim

    # Precompute pairwise similarity matrix for cleaned items
    pair_sims: list[list[float]] = [
        [_get_pair_sim(i, j) for j in range(n_v)] for i in range(n_h)
    ]

    def _score_bead(i0: int, j0: int, dh: int, dv: int) -> float:
        h_joined = "".join(clean_h_items[i][1] for i in range(i0, i0 + dh))
        v_joined = " ".join(clean_v_items[j][1] for j in range(j0, j0 + dv))

        len_score = compute_length_ratio_score(h_joined, v_joined)

        # Mean semantic/anchor similarity across the bead's submatrix
        sub_sims = [
            pair_sims[i][j]
            for i in range(i0, i0 + dh)
            for j in range(j0, j0 + dv)
        ]
        sem_score = sum(sub_sims) / len(sub_sims) if sub_sims else 0.5
        # Also reward anchor match on the merged strings (critical for 1-n / n-1 where
        # anchors in sentence 1 and sentence 2 jointly match the single counterpart!)
        merged_anchor = compute_anchor_similarity(h_joined, v_joined)
        combined_sem = max(sem_score, 0.5 * sem_score + 0.5 * merged_anchor)

        # Relative diagonal position penalty to prevent drift inside long works
        rel_h = (i0 + 0.5 * dh) / n_h
        rel_v = (j0 + 0.5 * dv) / n_v
        pos_score = math.exp(-2.0 * ((rel_h - rel_v) ** 2))

        local_quality = 0.50 * len_score + 0.38 * combined_sem + 0.12 * pos_score
        prior = BEAD_PRIORS.get((dh, dv), 0.72)

        # Weight by number of sentences covered ((dh + dv) / 2) so multi-sentence
        # beads compete fairly with sequences of 1-1 beads
        step_weight = 0.5 * (dh + dv)
        return step_weight * prior * local_quality

    # Dynamic Programming table over (i, j) for i in 0..n_h, j in 0..n_v
    neg_inf = -1e9
    dp: list[list[float]] = [[neg_inf] * (n_v + 1) for _ in range(n_h + 1)]
    backptr: list[list[tuple[int, int] | None]] = [
        [None] * (n_v + 1) for _ in range(n_h + 1)
    ]
    dp[0][0] = 0.0

    standard_beads = list(BEAD_PRIORS.keys())

    for i in range(n_h + 1):
        for j in range(n_v + 1):
            if dp[i][j] <= neg_inf / 2:
                continue
            for dh, dv in standard_beads:
                ni, nj = i + dh, j + dv
                if ni <= n_h and nj <= n_v:
                    cand_score = dp[i][j] + _score_bead(i, j, dh, dv)
                    if cand_score > dp[ni][nj]:
                        dp[ni][nj] = cand_score
                        backptr[ni][nj] = (dh, dv)

    # Fallback if extreme ratio prevented reaching (n_h, n_v) with up to 3:1 / 1:3 beads
    if backptr[n_h][n_v] is None:
        extended_beads = standard_beads + [
            (1, k) for k in range(4, min(n_v + 1, 9))
        ] + [
            (k, 1) for k in range(4, min(n_h + 1, 9))
        ]
        for i in range(n_h + 1):
            for j in range(n_v + 1):
                if dp[i][j] <= neg_inf / 2:
                    continue
                for dh, dv in extended_beads:
                    ni, nj = i + dh, j + dv
                    if ni <= n_h and nj <= n_v:
                        cand_score = dp[i][j] + _score_bead(i, j, dh, dv)
                        if cand_score > dp[ni][nj]:
                            dp[ni][nj] = cand_score
                            backptr[ni][nj] = (dh, dv)

    # Ultimate safety fallback: if still unreachable (e.g. 1 sentence vs 15 sentences),
    # collapse the entire single work as one (n_h, n_v) bead so zero sentences are lost
    if backptr[n_h][n_v] is None:
        h_joined = "".join(item[1] for item in clean_h_items)
        v_joined = clean_viet_text(" ".join(item[1] for item in clean_v_items))
        align_type = f"{n_h}-{n_v}"
        return [
            {
                "han": h_joined,
                "viet": v_joined,
                "align_type": align_type,
                "type": align_type,
                "han_indices": [item[0] for item in clean_h_items],
                "viet_indices": [item[0] for item in clean_v_items],
                "score": round(float(compute_length_ratio_score(h_joined, v_joined)), 4),
                "pair": (h_joined, v_joined),
            }
        ]

    # Backtrack from (n_h, n_v) to (0, 0)
    steps: list[tuple[int, int, int, int]] = []
    ci, cj = n_h, n_v
    while ci > 0 or cj > 0:
        step = backptr[ci][cj]
        if step is None:
            break
        dh, dv = step
        steps.append((ci - dh, cj - dv, dh, dv))
        ci -= dh
        cj -= dv
    steps.reverse()

    results: list[dict[str, Any]] = []
    for i0, j0, dh, dv in steps:
        h_joined = clean_han_text(
            "".join(clean_h_items[i][1] for i in range(i0, i0 + dh))
        )
        v_joined = clean_viet_text(
            " ".join(clean_v_items[j][1] for j in range(j0, j0 + dv))
        )
        h_indices = [clean_h_items[i][0] for i in range(i0, i0 + dh)]
        v_indices = [clean_v_items[j][0] for j in range(j0, j0 + dv)]
        align_type = f"{dh}-{dv}"
        bead_score = _score_bead(i0, j0, dh, dv) / (0.5 * (dh + dv))
        results.append(
            {
                "han": h_joined,
                "viet": v_joined,
                "align_type": align_type,
                "type": align_type,
                "han_indices": h_indices,
                "viet_indices": v_indices,
                "score": round(float(bead_score), 4),
                "pair": (h_joined, v_joined),
            }
        )

    return results
