"""Semantic Cross-Lingual Similarity Engine for Classical Chinese and Vietnamese.

Implements Stage 2 semantic alignment enhancement:
- Detects neural embedding backends (`sentence-transformers` with `BAAI/bge-m3` or
  `sentence-transformers/LaBSE`, or Hugging Face `transformers`) when available
  (e.g., on Kaggle GPU or servers with PyTorch).
- Provides a deterministic, highly-optimized offline lexical/anchor/phonetic
  similarity scorer when deep neural backends are not installed.
"""

from __future__ import annotations

import math
import re
from typing import Any, List, Optional, Tuple

_CJK_CHAR_RE = re.compile(
    r"[\u3007\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002ebef]"
)
_VIET_WORD_RE = re.compile(r"[A-Za-zÀ-ỹà-ỹ0-9]+")

# Sino-Vietnamese concept anchors for offline semantic scoring
_CORE_SEMANTIC_ANCHORS: list[tuple[str, tuple[str, ...]]] = [
    # Numerals
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
    ("十", ("mười", "thập", "10")),
    ("百", ("trăm", "bách", "100")),
    ("千", ("nghìn", "ngàn", "thiên", "1000", "1.000")),
    ("萬", ("vạn", "muôn", "10000", "10.000")),
    ("半", ("nửa", "rưỡi", "bán")),
    # Cosmos & Nature
    ("天", ("trời", "thiên")),
    ("地", ("đất", "địa")),
    ("日", ("ngày", "nhật", "mặt trời")),
    ("月", ("trăng", "nguyệt", "tháng")),
    ("星", ("sao", "tinh")),
    ("山", ("núi", "sơn", "non")),
    ("水", ("nước", "thủy", "sông")),
    ("江", ("sông", "giang")),
    ("海", ("biển", "hải")),
    ("風", ("gió", "phong")),
    ("雲", ("mây", "vân")),
    ("雨", ("mưa", "vũ")),
    ("雪", ("tuyết",)),
    ("霜", ("sương",)),
    ("春", ("xuân", "mùa xuân")),
    ("夏", ("hạ", "mùa hè")),
    ("秋", ("thu", "mùa thu")),
    ("冬", ("đông", "mùa đông")),
    ("花", ("hoa", "bông")),
    ("樹", ("cây", "thụ")),
    ("木", ("cây", "gỗ", "mộc")),
    # Society & Humanity
    ("王", ("vua", "vương")),
    ("帝", ("đế", "vua", "hoàng")),
    ("君", ("vua", "quân", "chàng")),
    ("臣", ("tôi", "thần", "quan")),
    ("民", ("dân", "người dân")),
    ("人", ("người", "nhân", "kẻ")),
    ("父", ("cha", "phụ", "bố")),
    ("母", ("mẹ", "mẫu")),
    ("子", ("con", "tử", "thầy")),
    ("僧", ("sư", "tăng", "thầy")),
    ("佛", ("phật", "bụt")),
    ("心", ("lòng", "tâm", "dạ")),
    ("國", ("nước", "quốc")),
    ("道", ("đạo", "đường")),
    ("詩", ("thơ", "thi")),
    ("酒", ("rượu", "tửu")),
    ("死", ("chết", "tử", "mất")),
    ("生", ("sống", "sinh", "đời")),
]


class CrossLingualSemanticScorer:
    """Computes pairwise semantic similarity between Classical Chinese and Vietnamese sentences."""

    def __init__(self, model_name: str = "BAAI/bge-m3", prefer_neural: bool = True) -> None:
        self.model_name = model_name
        self.prefer_neural = prefer_neural
        self._model = None
        self._backend = "offline_anchor"

        if prefer_neural:
            self._try_load_neural_backend()

    def _try_load_neural_backend(self) -> bool:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self._model = SentenceTransformer(self.model_name)
            self._backend = "sentence_transformers"
            return True
        except Exception:
            self._model = None
            self._backend = "offline_anchor"
            return False

    @property
    def backend_name(self) -> str:
        return self._backend

    def compute_anchor_similarity(self, han_text: str, viet_text: str) -> float:
        """Compute offline anchor and structural similarity in [0.0, 1.0]."""
        if not han_text or not viet_text:
            return 0.0

        viet_lower = viet_text.lower()
        viet_tokens = set(_VIET_WORD_RE.findall(viet_lower))

        matches = 0.0
        checks = 0.0

        # Punctuation anchors (questions, exclamations, quotes)
        if ("？" in han_text or "?" in han_text) or ("?" in viet_text):
            checks += 1.0
            if ("？" in han_text or "?" in han_text) == ("?" in viet_text):
                matches += 1.0

        if ("！" in han_text or "!" in han_text) or ("!" in viet_text):
            checks += 0.8
            if ("！" in han_text or "!" in han_text) == ("!" in viet_text):
                matches += 0.8

        # Lexical anchors
        for han_char, viet_equivalents in _CORE_SEMANTIC_ANCHORS:
            if han_char in han_text:
                checks += 1.0
                if any(
                    (eq in viet_tokens if " " not in eq else eq in viet_lower)
                    for eq in viet_equivalents
                ):
                    matches += 1.0

        if checks == 0.0:
            return 0.5  # Neutral baseline
        return min(1.0, max(0.0, (matches + 0.5) / (checks + 1.0)))

    def compute_similarity_matrix(
        self,
        han_sents: List[str],
        viet_sents: List[str],
    ) -> List[List[float]]:
        """Compute an [N x M] similarity matrix with values in [0.0, 1.0]."""
        n_h = len(han_sents)
        n_v = len(viet_sents)
        if n_h == 0 or n_v == 0:
            return []

        if self._backend == "sentence_transformers" and self._model is not None:
            try:
                import numpy as np  # type: ignore

                h_emb = self._model.encode(han_sents, normalize_embeddings=True)
                v_emb = self._model.encode(viet_sents, normalize_embeddings=True)
                sim_matrix = np.matmul(h_emb, v_emb.T)
                # Map cosine similarity [-1.0, 1.0] to [0.0, 1.0]
                norm_sim = np.clip((sim_matrix + 1.0) / 2.0, 0.0, 1.0)
                return norm_sim.tolist()
            except Exception:
                # Fallback to offline scoring if neural encode fails
                pass

        # Offline anchor-based computation
        matrix: List[List[float]] = []
        for h in han_sents:
            row: List[float] = []
            for v in viet_sents:
                score = self.compute_anchor_similarity(h, v)
                row.append(round(score, 4))
            matrix.append(row)
        return matrix
