from __future__ import annotations

import re
import sys
import threading
import queue
import tkinter as tk
from tkinter import filedialog
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import webview

PROJECT_ROOT = Path(__file__).resolve().parent
DICTIONARY_DIR = PROJECT_ROOT / "dictionary_app"
WRITING_DIR = PROJECT_ROOT / "writing_assistant"
for path in [PROJECT_ROOT, DICTIONARY_DIR, WRITING_DIR]:
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from dictionary_app.config import Config as DictionaryConfig
from dictionary_app.database_handler import DatabaseHandler
from dictionary_app.history_manager import HistoryManager
from dictionary_app.text_processor import TextProcessor
from writing_assistant.config_manager import ConfigManager
from writing_assistant.database_manager import DatabaseManager
from writing_assistant.highlight_manager import HighlightManager
from writing_assistant.word_checker import WordChecker

try:
    from Levenshtein import ratio as similarity_ratio
except Exception:
    from difflib import SequenceMatcher

    def similarity_ratio(left: str, right: str) -> float:
        return SequenceMatcher(None, left, right).ratio()


class DictionaryService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.db_handler = DatabaseHandler(DictionaryConfig.CURRENT_DB)
        if not self.db_handler.connect():
            raise RuntimeError(f"Failed to connect to dictionary database: {DictionaryConfig.CURRENT_DB}")
        self.history_manager = HistoryManager()

    def _ensure_connection(self) -> None:
        if not self.db_handler.conn:
            self.db_handler.connect()

    def search(self, query: str, exact_match: bool = False) -> Dict[str, Any]:
        normalized_query = (query or "").strip()
        if not normalized_query:
            return {
                "ok": False,
                "query": "",
                "exact_match": bool(exact_match),
                "is_phrase": False,
                "sections": [],
                "message": "请输入要查询的词。",
            }

        with self._lock:
            self._ensure_connection()
            is_phrase = re.match(r"^\w+(\s+\w+)+$", normalized_query) is not None
            sections: List[Dict[str, Any]] = []

            if is_phrase:
                phrase_rows = self.db_handler.search_phrases(normalized_query, bool(exact_match))
                phrase_entries = []
                for phrase, explanation in phrase_rows:
                    stats = self.db_handler.get_phrase_stats(phrase, bool(exact_match)) or (0, 0)
                    phrase_entries.append(
                        {
                            "word": phrase,
                            "explanation": explanation,
                            "word_class": "",
                            "kind": "phrase",
                            "count": stats[0],
                            "variety": stats[1],
                        }
                    )
                if phrase_entries:
                    sections.append(
                        {
                            "title": "爱丽丝语词组 -> 中文",
                            "kind": "phrase",
                            "entries": phrase_entries,
                        }
                    )
            else:
                alice_rows, chinese_rows = self.db_handler.search_words(normalized_query, bool(exact_match))

                alice_entries = []
                for word, explanation, word_class in alice_rows:
                    stats = self.db_handler.get_word_stats(word, bool(exact_match)) or (0, 0)
                    alice_entries.append(
                        {
                            "word": word,
                            "explanation": explanation,
                            "word_class": word_class,
                            "kind": "alice",
                            "count": stats[0],
                            "variety": stats[1],
                        }
                    )

                chinese_entries = []
                for word, explanation, word_class in chinese_rows:
                    stats = self.db_handler.get_word_stats(word, bool(exact_match)) or (0, 0)
                    chinese_entries.append(
                        {
                            "word": word,
                            "explanation": explanation,
                            "word_class": word_class,
                            "kind": "chinese",
                            "count": stats[0],
                            "variety": stats[1],
                        }
                    )

                if alice_entries:
                    sections.append(
                        {
                            "title": "爱丽丝语 -> 中文",
                            "kind": "alice",
                            "entries": alice_entries,
                        }
                    )
                if chinese_entries:
                    sections.append(
                        {
                            "title": "中文 -> 爱丽丝语",
                            "kind": "chinese",
                            "entries": chinese_entries,
                        }
                    )

            self.history_manager.add_record(normalized_query)

            return {
                "ok": True,
                "query": normalized_query,
                "exact_match": bool(exact_match),
                "is_phrase": is_phrase,
                "sections": sections,
                "history": self.history_manager.get_history(),
                "message": "" if sections else f"未找到 '{normalized_query}' 的匹配结果。",
            }

    def get_history(self) -> List[str]:
        with self._lock:
            return self.history_manager.get_history()

    def get_examples(self, word: str) -> Dict[str, Any]:
        normalized_word = (word or "").strip()
        if not normalized_word:
            return {
                "ok": False,
                "word": "",
                "examples": [],
                "song_stats": [],
                "total_before": 0,
                "total_after": 0,
                "deduplication_rate": 0,
                "message": "请输入要查询例句的词。",
            }

        with self._lock:
            self._ensure_connection()
            songs = self.db_handler.find_songs_with_word(normalized_word)
            examples, song_stats = self._process_and_deduplicate_examples(songs, normalized_word)

            valid_stats = {k: v for k, v in song_stats.items() if v["before"] > 0}
            total_before = sum(v["before"] for v in valid_stats.values())
            total_after = len(examples)
            dedup_rate = ((total_before - total_after) / total_before * 100) if total_before > 0 else 0

            payload_examples = []
            for index, example in enumerate(examples):
                lyric = example["lyric"]
                paragraph = example["paragraph"]
                start_pos, end_pos = TextProcessor.find_paragraph_positions(lyric, paragraph)
                payload_examples.append(
                    {
                        "id": index,
                        "paragraph": paragraph,
                        "title": example["title"],
                        "album": example["album"],
                        "lyric": lyric,
                        "start": start_pos,
                        "end": end_pos,
                    }
                )

            payload_stats = [
                {
                    "album": album,
                    "title": title,
                    "before": stats["before"],
                    "after": stats["after"],
                }
                for (album, title), stats in sorted(valid_stats.items())
            ]

            return {
                "ok": True,
                "word": normalized_word,
                "examples": payload_examples,
                "song_stats": payload_stats,
                "total_before": total_before,
                "total_after": total_after,
                "deduplication_rate": round(dedup_rate, 2),
                "message": "" if payload_examples else f"未找到包含 '{normalized_word}' 的例句。",
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
            return {
                "ok": bool(success),
                "message": "歌词已保存。" if success else "保存失败，请检查数据库状态。",
            }

    def _process_and_deduplicate_examples(
        self,
        songs: List[Tuple[str, str, str]],
        word: str,
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
                unique_examples.append(
                    {
                        "paragraph": paragraph,
                        "title": stripped_title,
                        "album": stripped_album,
                        "lyric": lyric,
                    }
                )
                after_count += 1

            song_stats[song_key]["before"] = before_count
            song_stats[song_key]["after"] = after_count

        return unique_examples, song_stats

    def close(self) -> None:
        with self._lock:
            self.db_handler.close()


class VirtualTextArea:
    def __init__(self, text: str):
        self.text = text or ""
        self._tk_text = self.text if self.text.endswith("\n") else self.text + "\n"
        self._line_offsets = self._build_line_offsets(self._tk_text)
        self.tags: Dict[str, List[Tuple[int, int]]] = {"unknown": [], "lowstat": []}

    @staticmethod
    def _build_line_offsets(text: str) -> List[int]:
        offsets = [0]
        for index, char in enumerate(text):
            if char == "\n":
                offsets.append(index + 1)
        return offsets

    def get(self, start: str, end: str) -> str:
        _ = (start, end)
        return self._tk_text

    def tag_remove(self, tag_name: str, start: str, end: str) -> None:
        _ = (start, end)
        if tag_name in self.tags:
            self.tags[tag_name] = []

    def tag_add(self, tag_name: str, start: str, end: str) -> None:
        if tag_name not in self.tags:
            self.tags[tag_name] = []
        start_offset = self._index_to_offset(start)
        end_offset = self._index_to_offset(end)
        if end_offset < start_offset:
            start_offset, end_offset = end_offset, start_offset
        if start_offset == end_offset:
            return
        self.tags[tag_name].append((start_offset, end_offset))

    def update_idletasks(self) -> None:
        return

    def _index_to_offset(self, index: str) -> int:
        if index == "end":
            return len(self._tk_text)
        if "." not in index:
            return 0

        line_part, col_part = index.split(".", 1)
        try:
            line = max(1, int(line_part))
            col = max(0, int(col_part))
        except Exception:
            return 0

        line_index = line - 1
        if line_index >= len(self._line_offsets):
            return len(self._tk_text)

        base_offset = self._line_offsets[line_index]
        return min(len(self._tk_text), base_offset + col)


class WritingAssistantService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.config_manager = ConfigManager()
        self.db_manager = DatabaseManager()
        self.highlight_manager = HighlightManager(self.config_manager)
        self._status_message = ""
        self.reload_known_words()

    def reload_known_words(self) -> str:
        with self._lock:
            self._status_message = self.highlight_manager.load_known_words_from_db(self.db_manager)
            return self._status_message

    def get_status_message(self) -> str:
        with self._lock:
            return self._status_message

    def get_settings(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "strict_case": bool(self.config_manager.get("strict_case", True)),
                "max_undo_steps": int(self.config_manager.get("max_undo_steps", 100)),
                "excluded_words": list(self.config_manager.get("excluded_words", [])),
            }

    def save_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            strict_case = bool(settings.get("strict_case", self.config_manager.get("strict_case", True)))

            try:
                max_undo_steps = int(settings.get("max_undo_steps", self.config_manager.get("max_undo_steps", 100)))
            except Exception:
                max_undo_steps = int(self.config_manager.get("max_undo_steps", 100))
            max_undo_steps = max(1, min(1000, max_undo_steps))

            excluded_words = settings.get("excluded_words", self.config_manager.get("excluded_words", []))
            if not isinstance(excluded_words, list):
                excluded_words = []
            normalized_excluded = []
            seen = set()
            for value in excluded_words:
                word = str(value).strip()
                if not word or word in seen:
                    continue
                seen.add(word)
                normalized_excluded.append(word)

            self.config_manager.set("strict_case", strict_case)
            self.config_manager.set("max_undo_steps", max_undo_steps)
            self.config_manager.set("excluded_words", normalized_excluded)
            self.config_manager.save_config()

            self.reload_known_words()
            return {
                "ok": True,
                "message": "设置已保存。",
                "settings": self.get_settings(),
                "status": self._status_message,
            }

    def check_text(self, text: str) -> Dict[str, Any]:
        with self._lock:
            area = VirtualTextArea(text or "")
            checker = WordChecker(None, area, self.highlight_manager, self.config_manager)
            checker.reset_state()
            unknown_count = checker.check_words() or 0

            unknown_ranges = sorted(area.tags.get("unknown", []), key=lambda item: (item[0], item[1]))
            lowstat_ranges = sorted(area.tags.get("lowstat", []), key=lambda item: (item[0], item[1]))

            unknowns, lowstats = self.highlight_manager.categorize_sidebar_items()
            ordered = self.highlight_manager.sort_sidebar_items(unknowns, lowstats)
            sidebar_items = []
            for _, key, info in ordered:
                display_word = info.get("display", key)
                stats_key = display_word if self.config_manager.get("strict_case") else str(display_word).lower()
                count, variety = self.highlight_manager.word_stats.get(stats_key, (0, 0))
                sidebar_items.append(
                    {
                        "key": key,
                        "display": display_word,
                        "type": info.get("type", "unknown"),
                        "pos": int(info.get("pos", 0)),
                        "reasons": sorted(list(info.get("reasons", set()))),
                        "count": int(count),
                        "variety": int(variety),
                    }
                )

            strict_label = "严格区分大小写" if self.config_manager.get("strict_case") else "不区分大小写"
            status_text = (
                f"状态：已检查 - 未知词 {unknown_count} 个 - 已加载 "
                f"{len(self.highlight_manager.known_words)} 个已知词（{strict_label}）"
            )

            return {
                "ok": True,
                "unknown_count": int(unknown_count),
                "unknown_ranges": unknown_ranges,
                "lowstat_ranges": lowstat_ranges,
                "sidebar_items": sidebar_items,
                "status": status_text,
            }

    def lookup_explanations(self, selected_text: str) -> Dict[str, Any]:
        text = (selected_text or "").strip()
        if not text:
            return {"ok": False, "message": "请选择要查询的内容。", "explanations": [], "similar_words": []}

        with self._lock:
            explanations: Dict[str, str] = {}
            similar_words: Dict[str, Dict[str, Any]] = {}

            conn = self.db_manager.get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT PHRASE FROM phrase")
            all_phrases = [row[0] for row in cursor.fetchall()]
            all_phrases.sort(key=len, reverse=True)

            cursor.execute("SELECT words FROM dictionary")
            all_words = [row[0] for row in cursor.fetchall()]

            strict_case = bool(self.config_manager.get("strict_case"))
            remaining_text = text
            matched_phrases: List[str] = []

            for phrase in all_phrases:
                if phrase in remaining_text:
                    matched_phrases.append(phrase)
                    remaining_text = remaining_text.replace(phrase, " ")

            for phrase in matched_phrases:
                if strict_case:
                    cursor.execute("SELECT explanation FROM phrase WHERE PHRASE = ?", (phrase,))
                else:
                    cursor.execute("SELECT explanation FROM phrase WHERE LOWER(PHRASE) = LOWER(?)", (phrase,))
                result = cursor.fetchone()
                explanations[phrase] = result[0] if result else "未找到释义"

            remaining_words = re.findall(r"\b\w+\b", remaining_text)
            for word in remaining_words:
                if not word.strip():
                    continue

                if strict_case:
                    cursor.execute("SELECT explanation FROM dictionary WHERE words = ?", (word,))
                else:
                    cursor.execute("SELECT explanation FROM dictionary WHERE LOWER(words) = LOWER(?)", (word,))
                result = cursor.fetchone()

                if result:
                    explanations[word] = result[0]
                    continue

                explanations[word] = "未找到释义"
                best_match = None
                best_score = 0.0
                for dict_word in all_words:
                    score = similarity_ratio(word, dict_word) if strict_case else similarity_ratio(word.lower(), dict_word.lower())
                    if score > best_score and score > 0.6:
                        best_score = score
                        best_match = dict_word

                if best_match:
                    if strict_case:
                        cursor.execute("SELECT explanation FROM dictionary WHERE words = ?", (best_match,))
                    else:
                        cursor.execute("SELECT explanation FROM dictionary WHERE LOWER(words) = LOWER(?)", (best_match,))
                    similar_result = cursor.fetchone()
                    if similar_result:
                        similar_words[word] = {
                            "similar_word": best_match,
                            "explanation": similar_result[0],
                            "score": round(best_score, 4),
                        }

            if not explanations:
                if strict_case:
                    cursor.execute("SELECT explanation FROM dictionary WHERE words = ?", (text,))
                else:
                    cursor.execute("SELECT explanation FROM dictionary WHERE LOWER(words) = LOWER(?)", (text,))
                result = cursor.fetchone()
                explanations[text] = result[0] if result else "未找到释义"

            explanation_items = [{"word": key, "explanation": value} for key, value in explanations.items()]
            similar_items = [
                {
                    "word": key,
                    "similar_word": value["similar_word"],
                    "explanation": value["explanation"],
                    "score": value["score"],
                }
                for key, value in similar_words.items()
            ]

            return {
                "ok": True,
                "message": "",
                "explanations": explanation_items,
                "similar_words": similar_items,
            }

    def close(self) -> None:
        with self._lock:
            self.db_manager.close_connection()


class UnifiedAPI:
    def __init__(
        self,
        initial_tab: str,
        startup_query: Optional[str],
        startup_exact: bool,
        update_checker: Any = None,
        app_settings: Any = None,
    ) -> None:
        self._lock = threading.RLock()
        self.update_checker = update_checker
        self.app_settings = app_settings
        self.initial_tab = initial_tab if initial_tab in {"dictionary", "writing"} else "dictionary"
        self.startup_query = (startup_query or "").strip()
        self.startup_exact = bool(startup_exact)
        self._main_window = None
        self._detached_windows: Dict[str, Any] = {}
        self._closed = False
        self._tasks: "queue.Queue[Optional[Tuple[Any, Tuple[Any, ...], Dict[str, Any], Dict[str, Any], threading.Event]]]" = queue.Queue()
        self._worker_ready = threading.Event()
        self._worker_failed: Optional[BaseException] = None
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="UnifiedWebUIWorker",
            daemon=True,
        )
        self._worker_thread.start()

    def _worker_loop(self) -> None:
        try:
            self.dictionary_service = DictionaryService()
            self.writing_service = WritingAssistantService()
        except Exception as exc:
            self._worker_failed = exc
            self._worker_ready.set()
            return

        self._worker_ready.set()
        while True:
            task = self._tasks.get()
            if task is None:
                break

            func, args, kwargs, box, done = task
            try:
                box["value"] = func(*args, **kwargs)
            except Exception as exc:  # pragma: no cover - defensive bridge boundary
                box["error"] = exc
            finally:
                done.set()

        try:
            self.dictionary_service.close()
        except Exception:
            pass
        try:
            self.writing_service.close()
        except Exception:
            pass

    def _invoke(self, func: Any, *args: Any, allow_closed: bool = False, **kwargs: Any) -> Any:
        if threading.current_thread() is self._worker_thread:
            return func(*args, **kwargs)

        self._worker_ready.wait(timeout=30)
        if not self._worker_ready.is_set():
            raise RuntimeError("Unified service worker startup timed out.")

        if self._worker_failed is not None:
            raise RuntimeError(str(self._worker_failed)) from self._worker_failed

        if not allow_closed and self._closed:
            raise RuntimeError("Unified API is already closed.")

        box: Dict[str, Any] = {}
        done = threading.Event()
        self._tasks.put((func, args, kwargs, box, done))
        done.wait()

        if "error" in box:
            error = box["error"]
            raise RuntimeError(str(error)) from error
        return box.get("value")

    def _bootstrap_impl(self) -> Dict[str, Any]:
        return {
            "initial_tab": self.initial_tab,
            "startup_query": self.startup_query,
            "startup_exact": self.startup_exact,
            "dictionary_history": self.dictionary_service.get_history(),
            "writing_settings": self.writing_service.get_settings(),
            "writing_status": self.writing_service.get_status_message(),
        }

    def set_main_window(self, window: Any) -> None:
        self._main_window = window

    def bootstrap(self) -> Dict[str, Any]:
        try:
            writing_settings = ConfigManager().config
        except Exception:
            writing_settings = {"strict_case": True, "max_undo_steps": 100, "excluded_words": []}
        try:
            dictionary_history = HistoryManager().get_history()
        except Exception:
            dictionary_history = []
        app_settings = self.app_settings.get_public_settings() if self.app_settings is not None else {
            "auto_update": True,
            "auto_update_status": "",
        }
        return {
            "initial_tab": self.initial_tab,
            "startup_query": self.startup_query,
            "startup_exact": self.startup_exact,
            "dictionary_history": dictionary_history,
            "writing_settings": writing_settings,
            "writing_status": "后台服务正在加载...",
            "app_settings": app_settings,
        }

    def detach_native_window(self, app_id: str, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        app = app_id if app_id in {"dictionary", "writing"} else ""
        if not app:
            return {"ok": False, "message": "未知模块。"}

        with self._lock:
            existing = self._detached_windows.get(app)
            if existing is not None:
                try:
                    existing.show()
                except Exception:
                    pass
                return {"ok": True, "message": "窗口已打开。"}

        index_path = PROJECT_ROOT / "webui" / "index.html"
        url = f"{index_path.as_uri()}#window=detached&app={app}"
        title = "词典工具" if app == "dictionary" else "写作助手"

        try:
            win = webview.create_window(
                title=title,
                url=url,
                js_api=self,
                width=980 if app == "dictionary" else 1040,
                height=720,
                x=int(x) if x is not None else None,
                y=int(y) if y is not None else None,
                resizable=True,
                min_size=(520, 360),
                text_select=True,
            )
        except Exception as exc:
            return {"ok": False, "message": f"打开独立窗口失败: {exc}"}

        if win is None:
            return {"ok": False, "message": "打开独立窗口失败。"}

        with self._lock:
            self._detached_windows[app] = win

        def on_closed() -> None:
            with self._lock:
                if self._detached_windows.get(app) is win:
                    self._detached_windows.pop(app, None)
                main_window = self._main_window
            if main_window is not None:
                try:
                    main_window.evaluate_js(f"window.__nativeAppReturned && window.__nativeAppReturned({app!r});")
                except Exception:
                    pass

        win.events.closed += on_closed
        return {"ok": True, "message": "已打开独立窗口。"}

    def dictionary_search(self, query: str, exact_match: bool = False) -> Dict[str, Any]:
        return self._invoke(self.dictionary_service.search, query, bool(exact_match))

    def dictionary_history(self) -> List[str]:
        return self._invoke(self.dictionary_service.get_history)

    def dictionary_examples(self, word: str) -> Dict[str, Any]:
        return self._invoke(self.dictionary_service.get_examples, word)

    def dictionary_update_lyric(self, title: str, album: str, lyric: str) -> Dict[str, Any]:
        ret = self._invoke(self.dictionary_service.update_song_lyric, title, album, lyric)
        if ret and ret.get("ok") and self.app_settings is not None:
            self.app_settings.mark_local_database_changed()
        return ret

    def writing_check_text(self, text: str) -> Dict[str, Any]:
        return self._invoke(self.writing_service.check_text, text)

    def writing_get_settings(self) -> Dict[str, Any]:
        return self._invoke(self.writing_service.get_settings)

    def writing_save_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        return self._invoke(self.writing_service.save_settings, settings or {})

    def writing_lookup(self, selected_text: str) -> Dict[str, Any]:
        return self._invoke(self.writing_service.lookup_explanations, selected_text)

    def writing_query_dictionary(self, query: str, exact_match: bool = False) -> Dict[str, Any]:
        return self._invoke(self.dictionary_service.search, query, bool(exact_match))

    def app_get_settings(self) -> Dict[str, Any]:
        if self.app_settings is None:
            return {"auto_update": True, "auto_update_status": ""}
        return self.app_settings.get_public_settings()

    def app_save_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        if self.app_settings is None:
            return {"ok": False, "message": "设置管理器不可用。", "settings": self.app_get_settings()}
        public = self.app_settings.set_auto_update(bool((settings or {}).get("auto_update", True)))
        return {"ok": True, "message": "设置已保存。", "settings": public}

    def _writing_export_text_impl(self, content: str, suggested_name: str = "writing_assistant.txt") -> Dict[str, Any]:
        text = str(content or "")
        name = str(suggested_name or "writing_assistant.txt").strip() or "writing_assistant.txt"
        if not name.lower().endswith(".txt"):
            name += ".txt"

        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass

        try:
            save_path = filedialog.asksaveasfilename(
                title="导出文本",
                defaultextension=".txt",
                initialfile=name,
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            )
        finally:
            root.destroy()

        if not save_path:
            return {"ok": False, "path": "", "message": "用户取消保存。"}

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(text)
            return {"ok": True, "path": save_path, "message": "导出成功。"}
        except Exception as exc:
            return {"ok": False, "path": "", "message": f"导出失败: {exc}"}

    def writing_export_text(self, content: str, suggested_name: str = "writing_assistant.txt") -> Dict[str, Any]:
        return self._invoke(self._writing_export_text_impl, content, suggested_name)

    def close(self) -> Dict[str, Any]:
        self.shutdown()
        return {"ok": True}

    def shutdown(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        try:
            if self._worker_thread.is_alive():
                self._tasks.put(None)
                self._worker_thread.join(timeout=8)
        finally:
            if self.update_checker is not None:
                try:
                    self.update_checker.perform_update(None)
                except Exception:
                    pass


def launch_unified_webui(
    initial_tab: str = "dictionary",
    startup_query: Optional[str] = None,
    startup_exact: bool = False,
    update_checker: Any = None,
    app_settings: Any = None,
) -> None:
    api = UnifiedAPI(initial_tab, startup_query, startup_exact, update_checker, app_settings)
    index_path = Path(__file__).resolve().parent / "webui" / "index.html"
    if not index_path.exists():
        raise FileNotFoundError(f"Web UI entry file not found: {index_path}")

    main_window = webview.create_window(
        title="Alician Unified Workspace",
        url=index_path.as_uri(),
        js_api=api,
        width=1320,
        height=860,
        resizable=True,
        text_select=True,
    )
    api.set_main_window(main_window)

    try:
        webview.start(
            private_mode=False,
            storage_path=str(PROJECT_ROOT / ".webview_profile"),
        )
    finally:
        api.shutdown()
