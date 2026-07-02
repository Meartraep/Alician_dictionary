from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

_HF_OFFLINE_WAS_SET = "HF_HUB_OFFLINE" in os.environ
if not _HF_OFFLINE_WAS_SET:
    os.environ["HF_HUB_OFFLINE"] = "1"

try:
    from text2vec import SentenceModel
    import numpy as np

    HAS_TEXT2VEC = True
except Exception:
    HAS_TEXT2VEC = False
    if not _HF_OFFLINE_WAS_SET:
        os.environ.pop("HF_HUB_OFFLINE", None)

_MODEL_NAME = "shibing624/text2vec-base-chinese"


class SimilarityMatcher:
    def __init__(self) -> None:
        self._model: Any = None
        self._explanations: List[str] = []
        self._explanation_to_words: Dict[str, List[str]] = {}
        self._embeddings: Any = None
        self._ready = False

    @property
    def available(self) -> bool:
        return self._ready

    def _ensure_model(self) -> bool:
        if self._model is not None:
            return True
        if not HAS_TEXT2VEC:
            return False
        try:
            self._model = SentenceModel(_MODEL_NAME)
            logger.info("text2vec SentenceModel 加载成功")
            return True
        except Exception as e:
            logger.warning(f"text2vec 模型加载失败: {e}")
            self._model = None
            return False

    def build_index(self, word_explanation_pairs: List[Tuple[str, str]]) -> None:
        if not self._ensure_model():
            return

        self._explanation_to_words.clear()
        for word, explanation in word_explanation_pairs:
            exp = (explanation or "").strip()
            if not exp:
                continue
            if exp not in self._explanation_to_words:
                self._explanation_to_words[exp] = []
            if word not in self._explanation_to_words[exp]:
                self._explanation_to_words[exp].append(word)

        self._explanations = list(self._explanation_to_words.keys())
        if not self._explanations:
            return

        try:
            self._embeddings = self._model.encode(self._explanations)
            self._ready = True
            logger.info(f"相似度索引构建完成，共 {len(self._explanations)} 条中文释义")
        except Exception as e:
            logger.warning(f"相似度索引构建失败: {e}")
            self._ready = False

    def find_similar(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        if not self._ready or self._model is None or self._embeddings is None:
            return []

        query = (query or "").strip()
        if not query:
            return []

        try:
            query_embedding = self._model.encode([query])
            scores = np.dot(query_embedding, self._embeddings.T)[0]

            top_indices = np.argsort(scores)[-top_k:][::-1]

            results: List[Dict[str, Any]] = []
            for idx in top_indices:
                score = float(scores[idx])
                if score <= 0:
                    continue
                explanation = self._explanations[idx]
                words = self._explanation_to_words.get(explanation, [])
                results.append(
                    {
                        "explanation": explanation,
                        "words": words,
                        "similarity": round(score, 4),
                    }
                )
            return results
        except Exception as e:
            logger.warning(f"相似度搜索失败: {e}")
            return []
