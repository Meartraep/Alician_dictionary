from __future__ import annotations

import re
import sqlite3
from collections import Counter, defaultdict

from webui_backend.dictionary_core import TextProcessor
from webui_backend.translation_service import TranslationService, _ALICIAN_PART_RE


def main() -> None:
    service = TranslationService()
    conn = sqlite3.connect("translated.db")
    counts: Counter[str] = Counter()
    examples: dict[str, list[tuple[str, list[str]]]] = defaultdict(list)
    try:
        lyrics = [row[0] for row in conn.execute("SELECT lyric FROM songs WHERE lyric IS NOT NULL")]
        for lyric in lyrics:
            for block in TextProcessor.split_paragraphs(lyric):
                lines = [
                    item["raw"].strip() for item in block["lines"]
                    if item["raw"].strip() and not item["is_annotation"]
                ]
                for line in lines:
                    parts = _ALICIAN_PART_RE.findall(line)
                    selected = service._select_contextual_senses(parts)
                    families = []
                    for index, part in enumerate(parts):
                        if not re.fullmatch(r"[A-Za-z][A-Za-z'-]*", part):
                            continue
                        entry = selected.get(index) or service._best_word_entry(part)
                        if entry:
                            families.append(service._pos_family(entry["word_class"]))
                    core = [family for family in families if family in {"n", "pron", "v"}]
                    if core.count("v") != 1 or sum(family in {"n", "pron"} for family in core) < 2:
                        continue
                    verb_index = core.index("v")
                    order = "V-first" if verb_index == 0 else (
                        "V-last" if verb_index == len(core) - 1 else "V-middle"
                    )
                    counts[order] += 1
                    if len(examples[order]) < 10:
                        examples[order].append((line, core))
        print(dict(counts))
        for order, rows in examples.items():
            print(order)
            for line, core in rows:
                print(f"  {line} | {' '.join(core)}")
    finally:
        conn.close()
        service.close()


if __name__ == "__main__":
    main()
