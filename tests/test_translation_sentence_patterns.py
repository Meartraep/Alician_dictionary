from __future__ import annotations

import unittest

from webui_backend.translation_service import TranslationService


class TranslationSentencePatternTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.service = TranslationService()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.service.close()

    def test_pattern_resolves_ambiguous_chinese_noun_as_verb(self) -> None:
        result = self.service.translate("我爱世界", "zh_to_alician")
        semantic = [
            token for token in result["tokens"]
            if token.get("status") not in {"space", "punct"}
        ]
        self.assertEqual(result["result_text"], "Mii Amie Shelista")
        self.assertEqual([token["word_class"] for token in semantic], ["pron.", "v.", "n."])
        self.assertTrue(all(
            token.get("order_method") == "database_sentence_pattern"
            for token in semantic
        ))

    def test_core_pattern_can_resolve_sense_with_tense_modifier(self) -> None:
        result = self.service.translate("我将爱世界", "zh_to_alician")
        love = next(token for token in result["tokens"] if token.get("source") == "爱")
        self.assertEqual(love["word_class"], "v.")
        self.assertEqual(love["method"], "sentence_pattern_sense")

    def test_reverse_translation_records_attested_parse_pattern(self) -> None:
        result = self.service.translate("Ranya Shelista Mii", "alician_to_zh")
        semantic = [
            token for token in result["tokens"]
            if token.get("status") not in {"space", "punct"}
        ]
        self.assertEqual(result["result_text"], "我看见世界")
        self.assertTrue(all(token.get("matched_sentence_pattern") for token in semantic))


if __name__ == "__main__":
    unittest.main()
