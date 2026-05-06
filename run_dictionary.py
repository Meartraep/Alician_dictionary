import os
import sys

from toolkit import main


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
