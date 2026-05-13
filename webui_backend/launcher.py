from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import webview

from webui_backend.unified_api import UnifiedAPI, PROJECT_ROOT


def launch_unified_webui(
    initial_tab: str = "dictionary",
    startup_query: Optional[str] = None,
    startup_exact: bool = False,
    update_checker: Any = None,
    app_settings: Any = None,
) -> None:
    api = UnifiedAPI(initial_tab, startup_query, startup_exact, update_checker, app_settings)
    index_path = PROJECT_ROOT / "webui" / "index.html"
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
        confirm_close=True,
    )
    api.set_main_window(main_window)

    try:
        webview.start(
            private_mode=False,
            storage_path=str(PROJECT_ROOT / ".webview_profile"),
        )
    finally:
        api.shutdown()
