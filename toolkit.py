import os
import sys
from pathlib import Path

def _get_app_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(os.path.dirname(sys.executable))
    return Path(__file__).resolve().parent

APP_ROOT = _get_app_root()

# Frozen subprocess dispatch — re-launched by the packaged exe to run
# modal tools (db diff dialog / db exporter) in isolated processes.
if getattr(sys, 'frozen', False) and len(sys.argv) > 1:
    if sys.argv[1] == '--db-update-dialog' and len(sys.argv) >= 4:
        from db_update_dialog import _build_diff, _show_diff_window
        local_path = sys.argv[2]
        remote_temp_path = sys.argv[3]
        diffs = _build_diff(local_path, remote_temp_path)
        accepted = _show_diff_window(diffs)
        if accepted:
            with open(remote_temp_path, "rb") as src:
                with open(local_path, "wb") as dst:
                    dst.write(src.read())
            print("ACCEPTED", flush=True)
        else:
            print("REJECTED", flush=True)
        try:
            os.remove(remote_temp_path)
        except Exception:
            pass
        sys.exit(0)
    if sys.argv[1] == '--db-exporter':
        import tkinter as tk
        from db_exporter import DBExporter
        root = tk.Tk()
        default_format = "xlsx"
        if len(sys.argv) > 2 and str(sys.argv[2]).lower() in ("xlsx", "csv"):
            default_format = str(sys.argv[2]).lower()
        DBExporter(root, default_format=default_format)
        root.mainloop()
        sys.exit(0)

sys.path.insert(0, str(APP_ROOT))

from app_settings import AppSettings
from registry_helper import is_first_launch, mark_launched
from unified_webui import launch_unified_webui

_DATA_FILES = [
    "translated.db",
    "app_settings.json",
    "word_checker_config.json",
    "search_history.json",
    "db_update.log",
    "update_checker.log",
]


def _safe_copy_file(src, dst):
    import shutil
    try:
        shutil.copy2(str(src), str(dst))
    except (PermissionError, OSError):
        pass


def _migrate_data_files(old_root, new_root):
    if old_root is None or new_root is None:
        return
    old_p = Path(old_root)
    new_p = Path(new_root)
    if old_p == new_p or not old_p.is_dir():
        return

    new_p.mkdir(parents=True, exist_ok=True)
    for name in _DATA_FILES:
        src = old_p / name
        if src.is_file():
            _safe_copy_file(src, new_p / name)


def _ensure_local_db_exists(data_root: Path) -> Path:
    local_db_path = data_root / "translated.db"
    if local_db_path.exists():
        return local_db_path

    source_db_path = APP_ROOT / "translated.db"
    if source_db_path.exists() and source_db_path.resolve() != local_db_path.resolve():
        data_root.mkdir(parents=True, exist_ok=True)
        _safe_copy_file(source_db_path, local_db_path)

    return local_db_path


class WelcomeAPI:
    def __init__(self, default_dir: str, allow_data_dir_selection: bool) -> None:
        self._closed = False
        self._default_dir = default_dir
        self._allow_data_dir_selection = bool(allow_data_dir_selection)
        self.data_dir = ""

    def close(self) -> bool:
        import webview

        self._closed = True
        for win in webview.windows:
            try:
                win.destroy()
            except Exception:
                pass
        return True

    def set_data_dir(self, path: str) -> bool:
        if not self._allow_data_dir_selection:
            self.data_dir = ""
            return True
        self.data_dir = (path or "").strip()
        return True

    def browse_data_dir(self) -> str:
        if not self._allow_data_dir_selection:
            return ""
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        try:
            path = filedialog.askdirectory(
                title="选择数据存储目录",
                initialdir=self._default_dir,
            )
        finally:
            root.destroy()
        return path or ""


def show_welcome_window(allow_data_dir_selection: bool) -> str:
    import webview

    project_root = APP_ROOT
    welcome_path = project_root / "webui" / "welcome.html"
    if not welcome_path.exists():
        mark_launched()
        return ""

    api = WelcomeAPI(str(APP_ROOT), allow_data_dir_selection)
    welcome_url = f"{welcome_path.as_uri()}#allowDataDir={'1' if allow_data_dir_selection else '0'}"
    webview.create_window(
        title="欢迎使用 Meartraep 工具集",
        url=welcome_url,
        js_api=api,
        width=560,
        height=460,
        resizable=False,
    )
    webview.start()
    mark_launched()
    return api.data_dir


def main(
    initial_tab: str = "dictionary",
    startup_query: str = "",
    startup_exact: bool = False,
) -> None:
    project_root = APP_ROOT
    settings_path = project_root / "app_settings.json"
    is_frozen = getattr(sys, 'frozen', False)

    app_settings = AppSettings(settings_path, project_root / "translated.db")

    if is_first_launch():
        chosen_dir = show_welcome_window(is_frozen)
        if chosen_dir:
            app_settings.settings["data_dir"] = chosen_dir
            app_settings.settings["_last_data_root"] = chosen_dir
            app_settings.save()

    if is_frozen:
        data_root = app_settings.resolve_data_root(APP_ROOT)
        if str(data_root) != str(APP_ROOT):
            data_root.mkdir(parents=True, exist_ok=True)

        last_root_raw = str(app_settings.settings.get("_last_data_root") or "").strip()
        last_root = Path(last_root_raw) if last_root_raw else None
        if last_root is not None and last_root.resolve() != data_root.resolve():
            _migrate_data_files(last_root, data_root)
        app_settings.settings["_last_data_root"] = str(data_root.resolve())
        if str(data_root) != str(APP_ROOT):
            app_settings.settings_path = data_root / "app_settings.json"
            app_settings.save()
        else:
            app_settings.save()

        local_db_path = _ensure_local_db_exists(data_root)
    else:
        data_root = APP_ROOT
        app_settings.settings["data_dir"] = ""
        app_settings.settings["_last_data_root"] = str(APP_ROOT.resolve())
        app_settings.save()
        local_db_path = APP_ROOT / "translated.db"

    app_settings.db_path = local_db_path

    if is_frozen and not local_db_path.exists():
        import shutil
        bundled_db = Path(sys._MEIPASS) / "translated.db"
        if bundled_db.exists():
            shutil.copy2(str(bundled_db), str(local_db_path))

    update_checker = None
    from update_checker import UpdateChecker

    update_checker = UpdateChecker(str(local_db_path), app_settings=app_settings)

    launch_unified_webui(
        initial_tab=initial_tab,
        startup_query=startup_query,
        startup_exact=startup_exact,
        update_checker=update_checker,
        app_settings=app_settings,
        data_root=data_root,
    )


if __name__ == "__main__":
    search_word = sys.argv[1] if len(sys.argv) > 1 else ""
    exact_match = False
    if len(sys.argv) > 2 and sys.argv[2].lower() != '--db-update-dialog' and sys.argv[2].lower() != '--db-exporter':
        exact_match = str(sys.argv[2]).lower() == "true"

    main(
        initial_tab="dictionary",
        startup_query=search_word,
        startup_exact=exact_match,
    )
