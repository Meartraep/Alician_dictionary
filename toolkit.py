import os
import sys
import json
from pathlib import Path

def _get_app_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(os.path.dirname(sys.executable))
    return Path(__file__).resolve().parent


def _get_resource_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))
    return Path(__file__).resolve().parent


APP_ROOT = _get_app_root()
RESOURCE_ROOT = _get_resource_root()


def _run_text2vec_self_test(output_path: str) -> int:
    payload = {"ok": False, "available": False, "suggestions": []}
    try:
        from webui_backend.similarity_matcher import SimilarityMatcher

        matcher = SimilarityMatcher()
        matcher.build_index(
            [
                ("happy-test", "开心快乐"),
                ("sad-test", "悲伤难过"),
            ]
        )
        suggestions = matcher.find_similar("快乐", top_k=2)
        payload.update(
            ok=bool(matcher.available and suggestions),
            available=matcher.available,
            suggestions=suggestions,
        )
    except Exception as exc:
        payload["error"] = f"{type(exc).__name__}: {exc}"

    try:
        Path(output_path).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        return 2
    return 0 if payload["ok"] else 1


if len(sys.argv) >= 3 and sys.argv[1] == '--text2vec-self-test':
    sys.exit(_run_text2vec_self_test(sys.argv[2]))

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
from model_manager import (
    configure_model_environment,
    get_registered_model_path,
    default_model_path,
)
from unified_webui import launch_unified_webui

DATA_DIR_NAME = "Alician_Data"

_BUNDLED_DATA_FILES = [
    "translated.db",
    "word_checker_config.json",
    "alice_app.ico",
    "alice.ico",
]


def _safe_copy_file(src, dst):
    import shutil
    try:
        shutil.copy2(str(src), str(dst))
    except (PermissionError, OSError):
        pass


def _release_bundled_data_files(data_root: Path) -> None:
    data_root.mkdir(parents=True, exist_ok=True)
    for name in _BUNDLED_DATA_FILES:
        dst = data_root / name
        if dst.exists():
            continue
        src = RESOURCE_ROOT / name
        if src.exists():
            _safe_copy_file(src, dst)


def main(
    initial_tab: str = "dictionary",
    startup_query: str = "",
    startup_exact: bool = False,
) -> None:
    is_frozen = getattr(sys, 'frozen', False)

    if is_frozen:
        data_root = APP_ROOT / DATA_DIR_NAME
        _release_bundled_data_files(data_root)
        os.chdir(str(data_root))
    else:
        data_root = APP_ROOT

    local_db_path = data_root / "translated.db"
    # Existing installations keep their writable database beside the executable.
    # Upgrade that database in place before any service validates the new schema.
    from scripts.migrate_dictionary_senses import migrate as migrate_dictionary_senses

    migrate_dictionary_senses(local_db_path, backup=True)
    registered_model_path = ""
    configured_model_path = ""
    if is_frozen:
        registered_model_path = get_registered_model_path()
        configured_model_path = registered_model_path or default_model_path()
    app_settings = AppSettings(
        data_root / "app_settings.json",
        local_db_path,
        default_model_path=configured_model_path,
        prefer_default_model_path=bool(registered_model_path),
    )

    if is_frozen:
        model_path = configure_model_environment(
            app_settings.settings.get("model_path", "")
        )
        app_settings.settings["model_path"] = model_path
        app_settings.save()

    app_settings.db_path = local_db_path
    os.environ["ALICIAN_DB_PATH"] = str(local_db_path)
    from webui_backend.dictionary_core import DictionaryConfig

    DictionaryConfig.DB_NAME = str(local_db_path)
    DictionaryConfig.CURRENT_DB = str(local_db_path)

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
