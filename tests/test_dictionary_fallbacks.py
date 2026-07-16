import os
import threading
import unittest
from unittest.mock import patch

import Levenshtein
import numpy as np

from webui_backend.build_mode import feature_flags
from webui_backend.dictionary_service import DictionaryService
from webui_backend import similarity_matcher as similarity_module
from webui_backend.similarity_matcher import SimilarityMatcher


class _History:
    def __init__(self):
        self.items = []

    def add_record(self, query):
        self.items.append(query)

    def get_history(self):
        return list(self.items)


class _Database:
    conn = True

    def __init__(self, rows=None):
        self.rows = rows or [
            ("Aasye", "升起"),
            ("Abelu", "绽开"),
            ("Ailent", "日子，每一天"),
        ]

    def search_words(self, query, exact):
        return [], []

    def get_all_words(self):
        return list(self.rows)


class _SemanticMatcher:
    def __init__(self):
        self.queries = []

    def find_similar(self, query):
        self.queries.append(query)
        return [{
            "explanation": "开放，盛开",
            "words": ["Abelu"],
            "similarity": 0.91,
            "method": "semantic",
        }]


class _VectorModel:
    def encode(self, texts):
        vectors = {
            "绽开，开放": [10.0, 0.0],
            "升起，上升": [0.0, 5.0],
            "花朵开放": [2.0, 0.0],
        }
        return np.asarray([vectors[text] for text in texts], dtype=float)


def _service(semantic_matcher=None):
    service = DictionaryService.__new__(DictionaryService)
    service._lock = threading.RLock()
    service.enable_fuzzy = True
    service.enable_semantic = semantic_matcher is not None
    service.db_handler = _Database()
    service.history_manager = _History()
    service.similarity_matcher = semantic_matcher
    service._similarity_index_built = True
    service._spelling_candidates = None
    service._ensure_connection = lambda: None
    service._get_examples_payload = lambda query, position: {
        "ok": True, "word": query, "examples": [], "song_stats": [],
        "total_before": 0, "total_after": 0,
    }
    return service


class DictionaryFallbackTests(unittest.TestCase):
    def test_python_levenshtein_is_available(self):
        self.assertTrue(callable(Levenshtein.distance))
        self.assertTrue(callable(Levenshtein.ratio))

    def test_alician_miss_uses_spelling_distance(self):
        result = _service().search("Aasyf")
        self.assertEqual(result["suggestions"][0]["words"], ["Aasye"])
        self.assertEqual(result["suggestions"][0]["distance"], 1)
        self.assertEqual(result["suggestions"][0]["method"], "spelling")

    def test_chinese_miss_uses_semantic_matcher_not_spelling(self):
        matcher = _SemanticMatcher()
        result = _service(matcher).search("开花")
        self.assertEqual(matcher.queries, ["开花"])
        self.assertEqual(result["suggestions"][0]["method"], "semantic")
        self.assertNotIn("distance", result["suggestions"][0])

    def test_text2vec_scores_are_cosine_normalized(self):
        matcher = SimilarityMatcher()
        matcher._model = _VectorModel()
        with patch.object(similarity_module, "_NP", np):
            matcher.build_index([("Abelu", "绽开，开放"), ("Aasye", "升起，上升")])
            result = matcher.find_similar("花朵开放", top_k=1)
        self.assertEqual(result[0]["words"], ["Abelu"])
        self.assertEqual(result[0]["similarity"], 1.0)

    def test_lite_keeps_spelling_fallback_but_disables_bundled_semantic_model(self):
        with patch.dict(os.environ, {"ALICIAN_LITE_BUILD": "1"}):
            flags = feature_flags()
        self.assertTrue(flags["fuzzy_search"])
        self.assertFalse(flags["semantic_search"])


if __name__ == "__main__":
    unittest.main()
