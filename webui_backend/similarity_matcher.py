from __future__ import annotations

import logging
import os
import site
import sys
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

_EXTERNAL_PATH_ENV = "ALICIAN_EXTERNAL_LIB_PATH"
_MODEL_PATH_ENV = "ALICIAN_TEXT2VEC_MODEL_PATH"
_BUNDLED_MODEL_DIR = "text2vec_model"


def _add_optional_dependency_paths() -> None:
    candidates = []
    env_paths = os.environ.get(_EXTERNAL_PATH_ENV, "")
    if env_paths:
        candidates.extend(env_paths.split(os.pathsep))

    exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else ""
    if exe_dir:
        candidates.extend(
            [
                os.path.join(exe_dir, "external_libs"),
                os.path.join(exe_dir, "site-packages"),
            ]
        )

    # A frozen Full build must be self-contained. Do not silently borrow a
    # system Python installation during validation or on end-user machines.
    # Explicit sibling/external paths above remain available for diagnostics.
    if not exe_dir:
        try:
            candidates.append(site.getusersitepackages())
        except Exception:
            pass

        try:
            candidates.extend(site.getsitepackages())
        except Exception:
            pass

    for path in candidates:
        if path and os.path.isdir(path) and path not in sys.path:
            sys.path.append(path)


_MODEL_NAME = "shibing624/text2vec-base-chinese"
_OPTIONAL_DEPS_CHECKED = False
_SENTENCE_MODEL_CLS: Any = None
_NP: Any = None


def _model_path() -> str:
    configured_path = os.environ.get(_MODEL_PATH_ENV, "").strip()
    if configured_path and os.path.isdir(configured_path):
        return configured_path

    if getattr(sys, "frozen", False):
        resource_root = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        bundled_path = os.path.join(resource_root, _BUNDLED_MODEL_DIR)
        if os.path.isfile(os.path.join(bundled_path, "config.json")):
            return bundled_path

    return _MODEL_NAME


def _load_optional_dependencies() -> bool:
    global _OPTIONAL_DEPS_CHECKED, _SENTENCE_MODEL_CLS, _NP

    if _SENTENCE_MODEL_CLS is not None and _NP is not None:
        return True
    if _OPTIONAL_DEPS_CHECKED:
        return False

    _OPTIONAL_DEPS_CHECKED = True
    _add_optional_dependency_paths()

    hf_offline_was_set = "HF_HUB_OFFLINE" in os.environ
    if not hf_offline_was_set:
        os.environ["HF_HUB_OFFLINE"] = "1"

    try:
        from text2vec import SentenceModel
        import numpy as np
    except Exception as e:
        if not hf_offline_was_set:
            os.environ.pop("HF_HUB_OFFLINE", None)
        logger.info(f"text2vec 可选依赖不可用: {e}")
        return False

    _SENTENCE_MODEL_CLS = SentenceModel
    _NP = np
    return True


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
        if not _load_optional_dependencies():
            return False
        try:
            model_path = _model_path()
            # Full builds bundle a CPU model. Pinning inference to CPU prevents
            # target machines from requiring CUDA or other GPU runtimes.
            self._model = _SENTENCE_MODEL_CLS(model_path, device="cpu")
            logger.info(f"text2vec SentenceModel 加载成功: {model_path}")
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
            embeddings = _NP.asarray(self._model.encode(self._explanations), dtype=float)
            norms = _NP.linalg.norm(embeddings, axis=1, keepdims=True)
            self._embeddings = embeddings / _NP.maximum(norms, 1e-12)
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
            query_embedding = _NP.asarray(self._model.encode([query]), dtype=float)
            query_norms = _NP.linalg.norm(query_embedding, axis=1, keepdims=True)
            query_embedding = query_embedding / _NP.maximum(query_norms, 1e-12)
            scores = _NP.clip(_NP.dot(query_embedding, self._embeddings.T)[0], -1.0, 1.0)

            top_indices = _NP.argsort(scores)[-top_k:][::-1]

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
                        "method": "semantic",
                    }
                )
            return results
        except Exception as e:
            logger.warning(f"相似度搜索失败: {e}")
            return []
