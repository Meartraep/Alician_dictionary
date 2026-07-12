from __future__ import annotations

import datetime
import os
import sys
import threading
import queue
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import webview

from webui_backend.build_mode import feature_flags, is_lite_build
from webui_backend.dictionary_service import DictionaryService
from webui_backend.writing_service import WritingAssistantService
from webui_backend.dbmanager_service import DatabaseManagerService
from webui_backend.dictionary_core import DictionaryConfig, HistoryManager
from webui_backend.writing_config import ConfigManager

PROJECT_ROOT = Path(__file__).resolve().parent.parent

VALID_TABS = {"dictionary", "writing", "translator", "dbmanager"}
DETACHED_TITLES = {
    "dictionary": "词典工具",
    "writing": "写作助手",
    "translator": "翻译器",
    "dbmanager": "数据库管理",
}
DETACHED_WIDTHS = {"dictionary": 980, "writing": 1040, "translator": 960, "dbmanager": 1100}


class UnifiedAPI:
    def __init__(
        self, initial_tab: str, startup_query: Optional[str], startup_exact: bool,
        update_checker: Any = None, app_settings: Any = None,
        data_root: Any = None,
    ) -> None:
        self._lock = threading.RLock()
        # Keep service objects private so pywebview does not recursively expose
        # their internals as JavaScript API methods.
        self._update_checker = update_checker
        self._app_settings = app_settings
        self._data_root = Path(data_root) if data_root is not None else PROJECT_ROOT
        self._features = feature_flags()
        if self._features["lite"] and initial_tab == "translator":
            initial_tab = "dictionary"
        self.initial_tab = initial_tab if initial_tab in VALID_TABS else "dictionary"
        self.startup_query = (startup_query or "").strip()
        self.startup_exact = bool(startup_exact)
        self._main_window = None
        self._detached_windows: Dict[str, Any] = {}
        self._closed = False
        self._dictionary_service: Any = None
        self._writing_service: Any = None
        self._translation_service: Any = None
        self._dbmanager_service: Any = None
        _Event = threading.Event
        self._tasks: "queue.Queue[Optional[Tuple[Any, Tuple[Any, ...], Dict[str, Any], Dict[str, Any], _Event]]]" = queue.Queue()
        self._worker_ready = threading.Event()
        self._worker_failed: Optional[BaseException] = None
        self._worker_thread = threading.Thread(
            target=self._worker_loop, name="UnifiedWebUIWorker", daemon=True)
        self._worker_thread.start()

    def _resolve_dbmanager_db_path(self) -> Path:
        if not getattr(sys, 'frozen', False):
            return PROJECT_ROOT / "translated.db"

        primary_db_path = self._data_root / "translated.db"
        if primary_db_path.exists():
            return primary_db_path

        fallback_db_path = PROJECT_ROOT / "translated.db"
        if fallback_db_path.exists():
            return fallback_db_path

        return primary_db_path

    def _configure_runtime_paths(self, data_root: Path) -> None:
        db_path = Path(data_root) / "translated.db"
        os.environ["ALICIAN_DB_PATH"] = str(db_path)
        DictionaryConfig.DB_NAME = str(db_path)
        DictionaryConfig.CURRENT_DB = str(db_path)
        if self._app_settings is not None:
            self._app_settings.db_path = db_path
        if self._update_checker is not None and hasattr(self._update_checker, "local_db_path"):
            self._update_checker.local_db_path = str(db_path)

    def _open_worker_services(self) -> None:
        self._configure_runtime_paths(self._data_root)
        self._dictionary_service = DictionaryService(enable_fuzzy=self._features["fuzzy_search"])
        self._writing_service = WritingAssistantService()
        if self._features["translator"]:
            from importlib import import_module

            module = import_module("webui_backend.translation_service")
            self._translation_service = module.TranslationService(str(self._resolve_dbmanager_db_path()))
        db_path = str(self._resolve_dbmanager_db_path())
        self._dbmanager_service = DatabaseManagerService(db_path)

    def _close_worker_services(self) -> None:
        for svc in ("_dictionary_service", "_writing_service", "_translation_service", "_dbmanager_service"):
            try:
                current = getattr(self, svc, None)
                if current is not None:
                    current.close()
            except Exception:
                pass
            setattr(self, svc, None)

    def _worker_loop(self) -> None:
        try:
            self._open_worker_services()
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
            except Exception as exc:
                box["error"] = exc
            finally:
                done.set()
        self._close_worker_services()

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
            raise RuntimeError(str(box["error"])) from box["error"]
        return box.get("value")

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
        app_settings = self._app_settings.get_public_settings() if self._app_settings is not None else {
            "auto_update": True, "auto_update_status": ""}
        return {
            "initial_tab": self.initial_tab, "startup_query": self.startup_query,
            "startup_exact": self.startup_exact, "dictionary_history": dictionary_history,
            "writing_settings": writing_settings, "writing_status": "后台服务正在加载...",
            "app_settings": app_settings,
            "features": dict(self._features),
        }

    def detach_native_window(self, app_id: str, x: Optional[int] = None,
                             y: Optional[int] = None) -> Dict[str, Any]:
        app = app_id if app_id in VALID_TABS else ""
        if not app:
            return {"ok": False, "message": "未知模块。"}
        if app == "translator" and not self._features["translator"]:
            return {"ok": False, "message": "轻量版不包含翻译器。"}
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
        title = DETACHED_TITLES.get(app, app)
        win_width = DETACHED_WIDTHS.get(app, 980)
        try:
            win = webview.create_window(
                title=title, url=url, js_api=self, width=win_width, height=720,
                x=int(x) if x is not None else None, y=int(y) if y is not None else None,
                resizable=True, min_size=(520, 360), text_select=True,
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
                    main_window.evaluate_js(
                        f"window.__nativeAppReturned && window.__nativeAppReturned({app!r});")
                except Exception:
                    pass
        win.events.closed += on_closed
        return {"ok": True, "message": "已打开独立窗口。"}

    def _clear_native_window_on_top(self, app_id: str) -> None:
        with self._lock:
            win = self._detached_windows.get(app_id)
        if win is None:
            return
        try:
            win.on_top = False
        except Exception:
            pass

    def focus_native_window(self, app_id: str) -> Dict[str, Any]:
        app = app_id if app_id in VALID_TABS else ""
        if not app:
            return {"ok": False, "message": "未知模块。"}
        if app == "translator" and not self._features["translator"]:
            return {"ok": False, "message": "轻量版不包含翻译器。"}
        with self._lock:
            existing = self._detached_windows.get(app)
        if existing is None:
            return {"ok": False, "message": "窗口未打开。"}
        try:
            try:
                existing.restore()
            except Exception:
                pass
            existing.show()
            try:
                existing.on_top = True
                timer = threading.Timer(1.2, self._clear_native_window_on_top, args=(app,))
                timer.daemon = True
                timer.start()
            except Exception:
                pass
            return {"ok": True, "message": "窗口已前置。"}
        except Exception as exc:
            return {"ok": False, "message": f"前置窗口失败: {exc}"}

    def dictionary_search(self, query: str, exact_match: bool = False) -> Dict[str, Any]:
        return self._invoke(lambda: self._dictionary_service.search(query, bool(exact_match)))

    def dictionary_history(self) -> List[str]:
        return self._invoke(lambda: self._dictionary_service.get_history())

    def dictionary_examples(self, word: str) -> Dict[str, Any]:
        return self._invoke(lambda: self._dictionary_service.get_examples(word))

    def dictionary_update_lyric(self, title: str, album: str, lyric: str) -> Dict[str, Any]:
        ret = self._invoke(lambda: self._dictionary_service.update_song_lyric(title, album, lyric))
        if ret and ret.get("ok") and self._app_settings is not None:
            self._app_settings.mark_local_database_changed()
        return ret

    def writing_check_text(self, text: str) -> Dict[str, Any]:
        return self._invoke(lambda: self._writing_service.check_text(text))

    def writing_get_settings(self) -> Dict[str, Any]:
        return self._invoke(lambda: self._writing_service.get_settings())

    def writing_save_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        return self._invoke(lambda: self._writing_service.save_settings(settings or {}))

    def writing_lookup(self, selected_text: str) -> Dict[str, Any]:
        return self._invoke(lambda: self._writing_service.lookup_explanations(selected_text))

    def writing_query_dictionary(self, query: str, exact_match: bool = False) -> Dict[str, Any]:
        return self._invoke(lambda: self._dictionary_service.search(query, bool(exact_match)))

    def translator_translate(self, text: str, direction: str = "auto") -> Dict[str, Any]:
        if not self._features["translator"]:
            return {
                "ok": False,
                "direction": direction or "auto",
                "source_text": str(text or ""),
                "result_text": "",
                "tokens": [],
                "stats": {"exact": 0, "approximate": 0, "unknown": 0},
                "message": "轻量版不包含翻译器。",
            }
        return self._invoke(lambda: self._translation_service.translate(text, direction))

    def app_get_settings(self) -> Dict[str, Any]:
        if self._app_settings is None:
            return {"auto_update": True, "auto_update_status": "", "alic_font": False, "alic_hover_enabled": True, "alic_hover_delay": 300, "update_check_status": "就绪"}
        public = self._app_settings.get_public_settings()
        return public

    def app_save_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        if self._app_settings is None:
            return {"ok": False, "message": "设置管理器不可用。", "settings": self.app_get_settings()}
        s = settings or {}
        if "auto_update" in s:
            self._app_settings.settings["auto_update"] = bool(s["auto_update"])
        if "alic_font" in s:
            self._app_settings.settings["alic_font"] = bool(s["alic_font"])
        if "alic_hover_enabled" in s:
            self._app_settings.settings["alic_hover_enabled"] = bool(s["alic_hover_enabled"])
        if "alic_hover_delay" in s:
            delay = max(0, min(1000, int(s["alic_hover_delay"])))
            self._app_settings.settings["alic_hover_delay"] = delay
        self._app_settings.save()
        public = self._app_settings.get_public_settings()
        return {"ok": True, "message": "设置已保存。", "settings": public}

    def app_force_download_update(self) -> Dict[str, Any]:
        if self._update_checker is None:
            return {"ok": False, "message": "更新检查器不可用"}
        return self._update_checker.force_download_and_diff()

    def app_check_for_update(self) -> Dict[str, Any]:
        if self._update_checker is None:
            return {"ok": False, "message": "更新检查器不可用"}
        return self._update_checker.manual_check_for_update()

    def _writing_export_text_impl(self, content: str,
                                  suggested_name: str = "writing.txt") -> Dict[str, Any]:
        text = str(content or "")
        name = str(suggested_name or "writing.txt").strip() or "writing.txt"
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
                title="导出文本", defaultextension=".txt", initialfile=name,
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
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

    def writing_export_text(self, content: str,
                            suggested_name: str = "writing.txt") -> Dict[str, Any]:
        return self._invoke(self._writing_export_text_impl, content, suggested_name)

    def dbmanager_get_tables(self) -> List[str]:
        return self._invoke(lambda: self._dbmanager_service.get_tables())

    def dbmanager_get_fields(self, table_name: str) -> List[str]:
        return self._invoke(lambda: self._dbmanager_service.get_fields(table_name))

    def dbmanager_get_all_data(self, table_name: str) -> Dict[str, Any]:
        return self._invoke(lambda: self._dbmanager_service.get_all_data(table_name))

    def dbmanager_search(self, table_name: str, keyword: str,
                         exact_match: bool = False) -> Dict[str, Any]:
        return self._invoke(
            lambda: self._dbmanager_service.search_records(table_name, keyword, bool(exact_match)))

    def dbmanager_add_record(self, table_name: str, values: Dict[str, str]) -> Dict[str, Any]:
        ret = self._invoke(lambda: self._dbmanager_service.add_record(table_name, values))
        if ret and ret.get("ok") and self._app_settings is not None:
            self._app_settings.mark_local_database_changed()
        return ret

    def dbmanager_update_record(self, table_name: str, record_id: int,
                                values: Dict[str, str]) -> Dict[str, Any]:
        ret = self._invoke(lambda: self._dbmanager_service.update_record(table_name, record_id, values))
        if ret and ret.get("ok") and self._app_settings is not None:
            self._app_settings.mark_local_database_changed()
        return ret

    def dbmanager_batch_update(self, table_name: str, edits: List[Dict[str, Any]]) -> Dict[str, Any]:
        ret = self._invoke(lambda: self._dbmanager_service.batch_update(table_name, edits))
        if ret and ret.get("ok"):
            try:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                lines = [f"[{timestamp}] 表: {table_name}, 提交了 {ret.get('committed', 0)} 条更改"]
                for edit in (edits or []):
                    rid = edit.get("id", "?")
                    vals = edit.get("values", {})
                    lines.append(f"  id={rid}: {vals}")
                lines.append("")
                with open(self._data_root / "db_update.log", "a", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
            except Exception:
                pass
            if self._app_settings is not None:
                self._app_settings.mark_local_database_changed()
        return ret

    def dbmanager_delete_records(self, table_name: str, ids: List[int]) -> Dict[str, Any]:
        ret = self._invoke(lambda: self._dbmanager_service.delete_records(table_name, ids))
        if ret and ret.get("ok") and self._app_settings is not None:
            self._app_settings.mark_local_database_changed()
        return ret

    def dbmanager_global_search(self, keyword: str,
                                exact_match: bool = False) -> Dict[str, Any]:
        return self._invoke(lambda: self._dbmanager_service.global_search(keyword, bool(exact_match)))

    def dbmanager_global_replace(self, keyword: str, replacement: str,
                                 match_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        ret = self._invoke(lambda: self._dbmanager_service.global_replace(keyword, replacement, match_records))
        if ret and ret.get("ok") and self._app_settings is not None:
            self._app_settings.mark_local_database_changed()
        return ret

    def _update_word_count_impl(self) -> Dict[str, Any]:
        from update_word_count import main as run_word_count

        try:
            run_word_count(verbose=False)
            return {"ok": True, "message": "词频/泛度更新完成。"}
        except Exception as exc:
            return {"ok": False, "message": f"词频/泛度更新失败: {exc}"}

    def dbmanager_update_word_count(self) -> Dict[str, Any]:
        ret = self._invoke(self._update_word_count_impl)
        if ret and ret.get("ok") and self._app_settings is not None:
            self._app_settings.mark_local_database_changed()
        return ret

    def _classify_words_impl(self) -> Dict[str, Any]:
        from classify_words import classify_words as run_classify

        try:
            run_classify()
            return {"ok": True, "message": "词性统计更新完成。"}
        except Exception as exc:
            return {"ok": False, "message": f"词性统计更新失败: {exc}"}

    def dbmanager_classify_words(self) -> Dict[str, Any]:
        ret = self._invoke(self._classify_words_impl)
        if ret and ret.get("ok") and self._app_settings is not None:
            self._app_settings.mark_local_database_changed()
        return ret

    def dbmanager_export_db(self) -> Dict[str, Any]:
        import subprocess

        exporter_path = PROJECT_ROOT / "db_exporter.py"
        if not getattr(sys, 'frozen', False) and not exporter_path.exists():
            return {"ok": False, "message": "导出工具 db_exporter.py 不存在。"}
        try:
            if getattr(sys, 'frozen', False):
                subprocess.Popen(
                    [str(sys.executable), '--db-exporter', 'xlsx'],
                )
            else:
                subprocess.Popen(
                    [str(sys.executable), str(exporter_path), 'xlsx'],
                    cwd=str(PROJECT_ROOT),
                )
            return {"ok": True, "message": "导出工具已启动。"}
        except Exception as exc:
            return {"ok": False, "message": f"启动导出工具失败: {exc}"}

    def dbmanager_export_csv(self) -> Dict[str, Any]:
        import subprocess

        exporter_path = PROJECT_ROOT / "db_exporter.py"
        if not getattr(sys, 'frozen', False) and not exporter_path.exists():
            return {"ok": False, "message": "导出工具 db_exporter.py 不存在。"}
        try:
            if getattr(sys, 'frozen', False):
                subprocess.Popen(
                    [str(sys.executable), '--db-exporter', 'csv'],
                )
            else:
                subprocess.Popen(
                    [str(sys.executable), str(exporter_path), 'csv'],
                    cwd=str(PROJECT_ROOT),
                )
            return {"ok": True, "message": "CSV导出工具已启动。"}
        except Exception as exc:
            return {"ok": False, "message": f"启动CSV导出工具失败: {exc}"}

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
            pass

