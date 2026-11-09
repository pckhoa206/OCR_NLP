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
import os
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
    r"\[\s*MASK\s*\]|[\u3007\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002ebef\u25a0-\u25a3]",
    re.IGNORECASE,
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
    pending_han: list[str] = []

    for blk in blocks:
        raw_han = ""
        raw_viet = ""
        raw_phien_am = ""

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
            else:
                aligned_pairs.append((cleaned_han, cleaned_viet))
        elif cleaned_han and not cleaned_viet:
            # Buffer Hán to merge with the next block (n-1)
            pending_han.append(cleaned_han)
        elif cleaned_viet and not cleaned_han and aligned_pairs:
            # Continuation of Vietnamese translation from previous block (1-n)
            prev_h, prev_v = aligned_pairs[-1]
            aligned_pairs[-1] = (prev_h, clean_viet_text(f"{prev_v} {cleaned_viet}"))

    # If trailing pending_han remains and we already have at least one pair, attach to last pair
    if pending_han and aligned_pairs:
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
    """
    if not blocks:
        return []

    aligned_rows: list[tuple[str, str, str, str]] = []
    for blk in blocks:
        raw_han = ""
        raw_dich_am = ""
        raw_dich_nghia = ""
        raw_dich_tho = ""

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
        elif not cleaned_han and aligned_rows and (cleaned_dich_nghia or cleaned_dich_tho):
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
            use_neural = os.environ.get("USE_NEURAL_EMBEDDINGS", "0") == "1"
            scorer = CrossLingualSemanticScorer(prefer_neural=use_neural)
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
