import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app_settings import AppSettings
from registry_helper import is_first_launch, mark_launched
from unified_webui import launch_unified_webui


class WelcomeAPI:
    def __init__(self) -> None:
        self._closed = False

    def close(self) -> bool:
        import webview

        self._closed = True
        for win in webview.windows:
            try:
                win.destroy()
            except Exception:
                pass
        return True


def show_welcome_window() -> None:
    import webview

    project_root = Path(__file__).resolve().parent
    welcome_path = project_root / "webui" / "welcome.html"
    if not welcome_path.exists():
        mark_launched()
        return

    api = WelcomeAPI()
    webview.create_window(
        title="欢迎使用 Meartraep 工具集",
        url=welcome_path.as_uri(),
        js_api=api,
        width=560,
        height=440,
        resizable=False,
    )
    webview.start()
    mark_launched()


def main(
    initial_tab: str = "dictionary",
    startup_query: str = "",
    startup_exact: bool = False,
) -> None:
    project_root = Path(__file__).resolve().parent
    local_db_path = project_root / "translated.db"
    app_settings = AppSettings(project_root / "app_settings.json", local_db_path)

    if is_first_launch():
        show_welcome_window()

    update_checker = None
    if app_settings.get_public_settings().get("auto_update", True):
        from update_checker import UpdateChecker

        update_checker = UpdateChecker(str(local_db_path), app_settings=app_settings)
        update_checker.start_background_check()

    launch_unified_webui(
        initial_tab=initial_tab,
        startup_query=startup_query,
        startup_exact=startup_exact,
        update_checker=update_checker,
        app_settings=app_settings,
    )


if __name__ == "__main__":
    search_word = sys.argv[1] if len(sys.argv) > 1 else ""
    exact_match = False
    if len(sys.argv) > 2:
        exact_match = str(sys.argv[2]).lower() == "true"

    main(
        initial_tab="dictionary",
        startup_query=search_word,
        startup_exact=exact_match,
    )
