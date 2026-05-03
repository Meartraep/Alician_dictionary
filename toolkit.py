import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from update_checker import UpdateChecker
from unified_webui import launch_unified_webui


def main(
    initial_tab: str = "dictionary",
    startup_query: str = "",
    startup_exact: bool = False,
) -> None:
    local_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translated.db")
    update_checker = UpdateChecker(local_db_path)
    update_checker.start_background_check()

    launch_unified_webui(
        initial_tab=initial_tab,
        startup_query=startup_query,
        startup_exact=startup_exact,
        update_checker=update_checker,
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
