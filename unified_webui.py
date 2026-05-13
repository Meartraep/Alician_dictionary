import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
for path in [
    PROJECT_ROOT,
    PROJECT_ROOT / "dictionary_app",
    PROJECT_ROOT / "writing_assistant",
    PROJECT_ROOT / "Dictionary_database_manager_main" / "dictionary_manager",
]:
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from webui_backend.launcher import launch_unified_webui
from webui_backend.unified_api import UnifiedAPI
