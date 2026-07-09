from __future__ import annotations

import logging
import re
import threading
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from webui_backend.build_mode import is_lite_build
from webui_backend.dictionary_core import DatabaseHandler, DictionaryConfig, HistoryManager, TextProcessor

logger = logging.getLogger(__name__)

try:
    from Levenshtein import ratio as _lev_ratio
except Exception:
    from difflib import SequenceMatcher

    def _lev_ratio(left: str, right: str) -> float:
        return SequenceMatcher(None, left, right).ratio()


class DictionaryService:
    def __init__(self, enable_fuzzy: bool | None = None) -> None:
        self._lock = threading.RLock()
        self.enable_fuzzy = (not is_lite_build()) if enable_fuzzy is None else bool(enable_fuzzy)
        self.db_handler = DatabaseHandler(DictionaryConfig.CURRENT_DB)
        if not self.db_handler.connect():
            raise RuntimeError(f"Failed to connect to dictionary database: {DictionaryConfig.CURRENT_DB}")
        self.history_manager = HistoryManager()
        self.similarity_matcher = self._create_similarity_matcher() if self.enable_fuzzy else None
        self._similarity_index_built = False

    def _create_similarity_matcher(self) -> Any:
        try:
            from importlib import import_module

            module = import_module("webui_backend.similarity_matcher")
            return module.SimilarityMatcher()
        except Exception:
            logger.info("相似度模块不可用，已跳过模糊建议。", exc_info=True)
            return None

    def _ensure_connection(self) -> None:
        if not self.db_handler.conn:
            self.db_handler.connect()

    def _build_similarity_index(self) -> None:
        if self.similarity_matcher is None:
            return
        try:
            word_explanation_pairs = self.db_handler.get_all_words()
            if word_explanation_pairs:
                self.similarity_matcher.build_index(word_explanation_pairs)
        except Exception:
            logger.warning("构建相似度索引时发生异常", exc_info=True)

    def search(self, query: str, exact_match: bool = False) -> Dict[str, Any]:
        normalized_query = (query or "").strip()
        if not normalized_query:
            return {
                "ok": False, "query": "", "exact_match": bool(exact_match),
                "is_phrase": False, "sections": [], "message": "请输入要查询的词。",
                "suggestions": [],
            }
        with self._lock:
            self._ensure_connection()
            effective_exact = bool(exact_match)
            is_phrase = re.match(r"^\w+(\s+\w+)+$", normalized_query) is not None
            sections: List[Dict[str, Any]] = []
            if is_phrase:
                phrase_rows = self.db_handler.search_phrases(normalized_query, effective_exact)
                phrase_entries = []
                for phrase, explanation in phrase_rows:
                    stats = self.db_handler.get_phrase_stats(phrase, effective_exact) or (0, 0)
                    phrase_entries.append({
                        "word": phrase, "explanation": explanation, "word_class": "",
                        "kind": "phrase", "count": stats[0], "variety": stats[1],
                    })
                if phrase_entries:
                    sections.append({
                        "title": "爱丽丝语词组 -> 中文", "kind": "phrase", "entries": phrase_entries,
                    })
            else:
                alice_rows, chinese_rows = self.db_handler.search_words(normalized_query, effective_exact)
                alice_entries = []
                for word, explanation, word_class in alice_rows:
                    stats = self.db_handler.get_word_stats(word, effective_exact) or (0, 0)
                    alice_entries.append({
                        "word": word, "explanation": explanation, "word_class": word_class,
                        "kind": "alice", "count": stats[0], "variety": stats[1],
                    })
                chinese_entries = []
                for word, explanation, word_class in chinese_rows:
                    stats = self.db_handler.get_word_stats(word, effective_exact) or (0, 0)
                    chinese_entries.append({
                        "word": word, "explanation": explanation, "word_class": word_class,
                        "kind": "chinese", "count": stats[0], "variety": stats[1],
                    })
                if alice_entries:
                    sections.append({"title": "爱丽丝语 -> 中文", "kind": "alice", "entries": alice_entries})
                if chinese_entries:
                    sections.append({"title": "中文 -> 爱丽丝语", "kind": "chinese", "entries": chinese_entries})
            self.history_manager.add_record(normalized_query)
            context_examples: Dict[str, Any] | None = None
            suggestions: List[Dict[str, Any]] = []
            if self.enable_fuzzy and not sections and not is_phrase:
                context_examples = self._get_examples_payload(normalized_query)
                if context_examples.get("examples"):
                    sections.append({
                        "title": "上下文命中（词典未收录）",
                        "kind": "context",
                        "entries": [{
                            "word": normalized_query,
                            "explanation": "词典中未收录该词，但在歌词上下文中找到了匹配。",
                            "word_class": "未收录词",
                            "kind": "context",
                            "count": context_examples.get("total_after", 0),
                            "variety": len(context_examples.get("song_stats", [])),
                        }],
                    })
                if self.similarity_matcher is not None and not self._similarity_index_built:
                    self._build_similarity_index()
                    self._similarity_index_built = True
                if self.similarity_matcher is not None:
                    suggestions = self.similarity_matcher.find_similar(normalized_query)
            return {
                "ok": True, "query": normalized_query, "exact_match": effective_exact,
                "is_phrase": is_phrase, "sections": sections,
                "history": self.history_manager.get_history(),
                "message": "" if sections else f"未搜索到对应单词：'{normalized_query}'。",
                "suggestions": suggestions,
                "context_examples": context_examples,
                "features": {"fuzzy_search": self.enable_fuzzy},
            }

    def get_history(self) -> List[str]:
        with self._lock:
            return self.history_manager.get_history()

    def get_examples(self, word: str) -> Dict[str, Any]:
        normalized_word = (word or "").strip()
        if not normalized_word:
            return {
                "ok": False, "word": "", "examples": [], "song_stats": [],
                "total_before": 0, "total_after": 0, "deduplication_rate": 0,
                "message": "请输入要查询例句的词。",
            }
        with self._lock:
            self._ensure_connection()
            return self._get_examples_payload(normalized_word)

    def _get_examples_payload(self, word: str) -> Dict[str, Any]:
        songs = self.db_handler.find_songs_with_word(word)
        examples, song_stats = self._process_and_deduplicate_examples(songs, word)
        valid_stats = {k: v for k, v in song_stats.items() if v["before"] > 0}
        total_before = sum(v["before"] for v in valid_stats.values())
        total_after = len(examples)
        dedup_rate = ((total_before - total_after) / total_before * 100) if total_before > 0 else 0
        payload_examples = []
        for index, example in enumerate(examples):
            lyric = example["lyric"]
            paragraph = example["paragraph"]
            start_pos, end_pos = TextProcessor.find_paragraph_positions(lyric, paragraph)
            payload_examples.append({
                "id": index, "paragraph": paragraph, "title": example["title"],
                "album": example["album"], "lyric": lyric, "start": start_pos, "end": end_pos,
            })
        payload_stats = [
            {"album": album, "title": title, "before": stats["before"], "after": stats["after"]}
            for (album, title), stats in sorted(valid_stats.items())
        ]
        return {
            "ok": True, "word": word, "examples": payload_examples,
            "song_stats": payload_stats, "total_before": total_before, "total_after": total_after,
            "deduplication_rate": round(dedup_rate, 2),
            "message": "" if payload_examples else f"未找到包含 '{word}' 的例句。",
        }

    def update_song_lyric(self, title: str, album: str, new_lyric: str) -> Dict[str, Any]:
        normalized_title = (title or "").strip()
        normalized_album = (album or "").strip()
        lyric = new_lyric or ""
        if not normalized_title or not lyric.strip():
            return {"ok": False, "message": "标题和歌词不能为空。"}
        with self._lock:
            self._ensure_connection()
            success = self.db_handler.update_song_lyric(normalized_title, normalized_album, lyric)
            return {"ok": bool(success), "message": "歌词已保存。" if success else "保存失败，请检查数据库状态。"}

    def _process_and_deduplicate_examples(
        self, songs: List[Tuple[str, str, str]], word: str,
    ) -> Tuple[List[Dict[str, str]], Dict[Tuple[str, str], Dict[str, int]]]:
        unique_examples: List[Dict[str, str]] = []
        seen_examples = set()
        song_stats: Dict[Tuple[str, str], Dict[str, int]] = defaultdict(lambda: {"before": 0, "after": 0})
        for title, lyric, album in songs:
            if not title or not album:
                continue
            stripped_album = album.strip()
            stripped_title = title.strip()
            song_key = (stripped_album, stripped_title)
            raw_paragraphs = TextProcessor.extract_valid_examples(lyric, word)
            before_count = len(raw_paragraphs)
            if before_count == 0:
                continue
            after_count = 0
            for paragraph in raw_paragraphs:
                normalized_paragraph = TextProcessor.normalize_text(paragraph)
                example_id = (normalized_paragraph, stripped_album, stripped_title)
                if example_id in seen_examples:
                    continue
                seen_examples.add(example_id)
                unique_examples.append({
                    "paragraph": paragraph, "title": stripped_title,
                    "album": stripped_album, "lyric": lyric,
                })
                after_count += 1
            song_stats[song_key]["before"] = before_count
            song_stats[song_key]["after"] = after_count
        return unique_examples, song_stats

    def close(self) -> None:
        with self._lock:
            self.db_handler.close()
