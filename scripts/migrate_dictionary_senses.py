from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


POS_RE = re.compile(r"(?<![A-Za-z])(adj|adv|art|conj|interj|n|num|prep|pron|vi|vt|v)\.", re.I)
NUMBER_RE = re.compile(r"[（(]\s*(?:\d+|[一二三四五六七八九十]+)\s*[）)]")


def _split_top_level(text: str) -> list[str]:
    parts, current = [], []
    depth = 0
    for char in text:
        if char in "（(【[":
            depth += 1
        elif char in "）)】]":
            depth = max(0, depth - 1)
        if depth == 0 and char in "，,、；;\n":
            value = "".join(current).strip()
            if value:
                parts.append(value)
            current = []
        else:
            current.append(char)
    value = "".join(current).strip()
    if value:
        parts.append(value)
    return parts


def _split_numbered(text: str) -> list[str]:
    matches = list(NUMBER_RE.finditer(text))
    if not matches:
        return [text.strip()] if text.strip() else []
    prefix = text[: matches[0].start()].strip()
    parts = [prefix] if prefix else []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = text[match.end() : end].strip(" ，,、；;\t\r\n")
        if value:
            parts.append(value)
    return parts


def split_senses(explanation: str | None, default_pos: str | None) -> list[tuple[str, str]]:
    source = str(explanation or "").strip()
    initial_pos = str(default_pos or "").strip()
    if not source:
        return [("", initial_pos)]

    markers = list(POS_RE.finditer(source))
    groups: list[tuple[str, str]] = []
    position, active_pos = 0, initial_pos
    for marker in markers:
        before = source[position : marker.start()].strip()
        if before:
            groups.append((before, active_pos))
        active_pos = marker.group(1).lower() + "."
        position = marker.end()
    tail = source[position:].strip()
    if tail:
        groups.append((tail, active_pos))
    if not groups:
        groups = [(source, initial_pos)]

    senses: list[tuple[str, str]] = []
    for text, pos in groups:
        numbered = _split_numbered(text)
        for numbered_part in numbered:
            for meaning in _split_top_level(numbered_part):
                meaning = meaning.strip()
                if meaning:
                    senses.append((meaning, pos))
    return senses or [(source, initial_pos)]


def migrate(db_path: Path, backup: bool = True) -> tuple[int, int]:
    conn = sqlite3.connect(db_path)
    try:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(dictionary)")]
        if "headword_id" in columns and conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='dictionary_headwords'"
        ).fetchone():
            return conn.execute("SELECT COUNT(*) FROM dictionary_headwords").fetchone()[0], conn.execute(
                "SELECT COUNT(*) FROM dictionary"
            ).fetchone()[0]

        if backup:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = db_path.with_name(f"{db_path.stem}.before_senses_{stamp}{db_path.suffix}")
            conn.close()
            shutil.copy2(db_path, backup_path)
            conn = sqlite3.connect(db_path)

        rows = conn.execute(
            "SELECT id, words, explanation, count, variety, class, time FROM dictionary ORDER BY id"
        ).fetchall()
        with conn:
            conn.execute("ALTER TABLE dictionary RENAME TO dictionary_legacy")
            conn.execute(
                "CREATE TABLE dictionary_headwords ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, words TEXT NOT NULL, display_explanation TEXT, "
                "display_class TEXT, count INTEGER DEFAULT 0, variety INTEGER DEFAULT 0, time TEXT)"
            )
            conn.execute(
                "CREATE TABLE dictionary ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, headword_id INTEGER NOT NULL, words TEXT NOT NULL, "
                "explanation TEXT NOT NULL, class TEXT, sense_order INTEGER NOT NULL, "
                "count INTEGER DEFAULT 0, variety INTEGER DEFAULT 0, time TEXT, "
                "FOREIGN KEY(headword_id) REFERENCES dictionary_headwords(id) ON DELETE CASCADE)"
            )
            for old_id, word, explanation, count, variety, word_class, entry_time in rows:
                conn.execute(
                    "INSERT INTO dictionary_headwords "
                    "(id, words, display_explanation, display_class, count, variety, time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (old_id, word, explanation, word_class, count, variety, entry_time),
                )
                for order, (meaning, pos) in enumerate(split_senses(explanation, word_class), 1):
                    conn.execute(
                        "INSERT INTO dictionary "
                        "(headword_id, words, explanation, class, sense_order, count, variety, time) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (old_id, word, meaning, pos, order, count, variety, entry_time),
                    )
            conn.execute("CREATE INDEX idx_dictionary_words ON dictionary(words)")
            conn.execute("CREATE INDEX idx_dictionary_explanation ON dictionary(explanation)")
            conn.execute("CREATE INDEX idx_dictionary_headword_order ON dictionary(headword_id, sense_order)")
            conn.execute("CREATE INDEX idx_dictionary_headwords_words ON dictionary_headwords(words)")
            conn.execute("DROP TABLE dictionary_legacy")
        return len(rows), conn.execute("SELECT COUNT(*) FROM dictionary").fetchone()[0]
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Normalize dictionary to one sense per row.")
    parser.add_argument("db", nargs="?", default="translated.db")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()
    headwords, senses = migrate(Path(args.db), backup=not args.no_backup)
    print(f"Migrated {headwords} headwords into {senses} sense rows.")
