from __future__ import annotations

import argparse
import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable, Optional

from webui_backend.dictionary_core import TextProcessor


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "translated.db"
DEFAULT_SOURCE = ROOT / "Alician(1).txt"
HEADING_RE = re.compile(r"^(\d+)\.(.+)$")
HAN_RE = re.compile(r"[\u3400-\u9fff]")


@dataclass(frozen=True)
class SourcePair:
    order: int
    alician: str
    chinese: str


@dataclass
class SourceSong:
    number: int
    title: str
    album: str
    pairs: list[SourcePair]
    source_line: int


@dataclass(frozen=True)
class DatabaseSentence:
    order: int
    alician: str
    word_glosses_text: str
    word_glosses_json: str


@dataclass(frozen=True)
class Alignment:
    db_order: Optional[int]
    txt_order: Optional[int]
    db_alician: str
    txt_alician: str
    chinese: str
    status: str
    score: float
    method: str
    notes: str = ""
    word_glosses_text: str = ""
    word_glosses_json: str = "[]"


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(char for char in value if char.isalnum())


def title_aliases(title: str) -> set[str]:
    title = unicodedata.normalize("NFKC", str(title or "")).strip()
    aliases = {normalize(title)}
    without_parentheses = re.sub(r"[（(][^）)]*[）)]", "", title).strip()
    if without_parentheses:
        aliases.add(normalize(without_parentheses))
    for inner in re.findall(r"[（(]([^）)]*)[）)]", title):
        if inner.strip():
            aliases.add(normalize(inner))
    return {alias for alias in aliases if alias}


def parse_source(path: Path) -> tuple[list[SourceSong], list[str]]:
    text = path.read_text(encoding="utf-8-sig")
    raw_lines = text.splitlines()
    nonempty = [
        (index + 1, line.strip())
        for index, line in enumerate(raw_lines)
        if line.strip()
    ]
    album_positions: dict[int, str] = {}
    for index in range(len(nonempty) - 1):
        next_match = HEADING_RE.match(nonempty[index + 1][1])
        if next_match and int(next_match.group(1)) == 1:
            album_positions[index] = nonempty[index][1]

    headings: list[tuple[int, int, int, str, str]] = []
    current_album = ""
    for index, (line_number, line) in enumerate(nonempty):
        if index in album_positions:
            current_album = album_positions[index]
            continue
        match = HEADING_RE.match(line)
        if match:
            headings.append((index, line_number, int(match.group(1)), match.group(2).strip(), current_album))

    songs: list[SourceSong] = []
    warnings: list[str] = []
    album_indexes = set(album_positions)
    for heading_index, (position, line_number, number, title, album) in enumerate(headings):
        end = headings[heading_index + 1][0] if heading_index + 1 < len(headings) else len(nonempty)
        content = [
            (source_line, line)
            for index, (source_line, line) in enumerate(
                nonempty[position + 1:end], start=position + 1
            )
            if index not in album_indexes
        ]
        pairs: list[SourcePair] = []
        pending_alician: Optional[tuple[int, str]] = None
        for source_line, line in content:
            if HAN_RE.search(line):
                if pending_alician is None:
                    pairs.append(SourcePair(len(pairs) + 1, "", line))
                    warnings.append(
                        f"TXT 第 {source_line} 行歌曲 {title!r} 有中文译文但没有对应爱丽丝语原句。"
                    )
                else:
                    pairs.append(SourcePair(len(pairs) + 1, pending_alician[1], line))
                    pending_alician = None
                continue
            if pending_alician is not None:
                if normalize(pending_alician[1]) == normalize(line):
                    pairs.append(SourcePair(len(pairs) + 1, pending_alician[1], line))
                    pending_alician = None
                    continue
                pairs.append(SourcePair(len(pairs) + 1, pending_alician[1], ""))
                warnings.append(
                    f"TXT 第 {pending_alician[0]} 行歌曲 {title!r} 的爱丽丝语原句没有中文译文。"
                )
            pending_alician = (source_line, line)
        if pending_alician is not None:
            pairs.append(SourcePair(len(pairs) + 1, pending_alician[1], ""))
            warnings.append(
                f"TXT 第 {pending_alician[0]} 行歌曲 {title!r} 的爱丽丝语原句没有中文译文。"
            )
        songs.append(SourceSong(number, title, album, pairs, line_number))
    return songs, warnings


def extract_song_sentences(lyric: str) -> list[DatabaseSentence]:
    sentences: list[DatabaseSentence] = []
    for paragraph in TextProcessor.split_paragraphs(str(lyric or "")):
        sentence_lines = [
            str(line["raw"] or "").strip()
            for line in paragraph["lines"]
            if str(line["raw"] or "").strip() and not line["is_annotation"]
        ]
        annotations = [
            str(line["raw"] or "").strip()
            for line in paragraph["lines"]
            if str(line["raw"] or "").strip() and line["is_annotation"]
        ]
        glosses = []
        for annotation in annotations:
            parts = re.split(r"[：:]", annotation, maxsplit=1)
            glosses.append({
                "word": parts[0].strip(),
                "gloss": parts[1].strip() if len(parts) > 1 else "",
                "raw": annotation,
            })
        glosses_json = json.dumps(glosses, ensure_ascii=False, separators=(",", ":"))
        for sentence in sentence_lines:
            sentences.append(DatabaseSentence(
                len(sentences) + 1,
                sentence,
                "\n".join(annotations),
                glosses_json,
            ))
    return sentences


def title_similarity(source: str, target: str) -> tuple[float, str]:
    source_aliases = title_aliases(source)
    target_aliases = title_aliases(target)
    if source_aliases & target_aliases:
        return 1.0, "title_alias"
    best = 0.0
    for left in source_aliases:
        for right in target_aliases:
            best = max(best, SequenceMatcher(None, left, right).ratio())
    return best, "title_similarity"


def match_source_songs(
    source_songs: Iterable[SourceSong], db_songs: list[sqlite3.Row],
) -> tuple[dict[int, SourceSong], list[SourceSong], list[str]]:
    matched: dict[int, SourceSong] = {}
    unmatched: list[SourceSong] = []
    warnings: list[str] = []
    used_db_ids: set[int] = set()
    for source in source_songs:
        candidates = []
        for row in db_songs:
            if int(row["id"]) in used_db_ids:
                continue
            score, method = title_similarity(source.title, str(row["title"] or ""))
            album_score, _ = title_similarity(source.album, str(row["Album"] or ""))
            candidates.append((score + album_score * 0.08, score, method, row))
        candidates.sort(key=lambda item: item[0], reverse=True)
        if not candidates or candidates[0][1] < 0.82:
            unmatched.append(source)
            continue
        _, score, method, row = candidates[0]
        db_id = int(row["id"])
        matched[db_id] = source
        used_db_ids.add(db_id)
        if score < 1.0:
            warnings.append(
                f"歌曲标题近似匹配：TXT {source.title!r} -> songs {row['title']!r} ({score:.3f}, {method})"
            )
    return matched, unmatched, warnings


def sentence_similarity(left: str, right: str) -> float:
    left_norm, right_norm = normalize(left), normalize(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def substitution_score(similarity: float) -> float:
    if similarity >= 0.98:
        return 3.0
    if similarity >= 0.88:
        return 2.0 + similarity
    if similarity >= 0.68:
        return similarity
    return -2.2


def align_song(
    db_sentences: list[DatabaseSentence], source_pairs: list[SourcePair],
) -> list[Alignment]:
    rows, columns = len(db_sentences), len(source_pairs)
    gap = -1.0
    scores = [[float("-inf")] * (columns + 1) for _ in range(rows + 1)]
    back: list[list[str]] = [[""] * (columns + 1) for _ in range(rows + 1)]
    scores[0][0] = 0.0
    for row in range(1, rows + 1):
        scores[row][0] = row * gap
        back[row][0] = "db_only"
    for column in range(1, columns + 1):
        scores[0][column] = column * gap
        back[0][column] = "txt_only"

    for row in range(1, rows + 1):
        for column in range(1, columns + 1):
            similarity = sentence_similarity(
                db_sentences[row - 1].alician, source_pairs[column - 1].alician
            )
            options = [
                (scores[row - 1][column - 1] + substitution_score(similarity), "match"),
                (scores[row - 1][column] + gap, "db_only"),
                (scores[row][column - 1] + gap, "txt_only"),
            ]
            scores[row][column], back[row][column] = max(options, key=lambda item: item[0])

    operations: list[tuple[str, Optional[int], Optional[int]]] = []
    row, column = rows, columns
    while row or column:
        operation = back[row][column]
        if operation == "match":
            operations.append((operation, row - 1, column - 1))
            row -= 1
            column -= 1
        elif operation == "db_only":
            operations.append((operation, row - 1, None))
            row -= 1
        else:
            operations.append(("txt_only", None, column - 1))
            column -= 1
    operations.reverse()

    alignments: list[Alignment] = []
    for operation, db_index, txt_index in operations:
        db_sentence = db_sentences[db_index] if db_index is not None else None
        pair = source_pairs[txt_index] if txt_index is not None else None
        if operation == "db_only" and db_sentence is not None:
            alignments.append(Alignment(
                db_sentence.order, None, db_sentence.alician, "", "",
                "missing_translation", 0.0, "sequence_gap",
                word_glosses_text=db_sentence.word_glosses_text,
                word_glosses_json=db_sentence.word_glosses_json,
            ))
            continue
        if operation == "txt_only" and pair is not None:
            alignments.append(Alignment(
                None, pair.order, "", pair.alician, pair.chinese,
                "unmatched_txt", 0.0, "sequence_gap",
            ))
            continue
        if pair is None or db_sentence is None:
            continue
        similarity = sentence_similarity(db_sentence.alician, pair.alician)
        if not pair.chinese.strip():
            status, method = "missing_translation", "source_translation_blank"
        elif similarity >= 0.999:
            status, method = "aligned_exact", "normalized_exact"
        elif similarity >= 0.9:
            status, method = "aligned_close", "sequence_similarity"
        elif similarity >= 0.72:
            status, method = "aligned_probable", "sequence_similarity"
        elif similarity >= 0.55:
            status, method = "aligned_low_confidence", "sequence_similarity"
        else:
            # A low-scoring diagonal is retained for auditability but is not
            # presented as a trustworthy semantic alignment.
            status, method = "aligned_low_confidence", "sequence_position"
        alignments.append(Alignment(
            db_sentence.order, pair.order, db_sentence.alician, pair.alician, pair.chinese,
            status, round(similarity, 6), method,
            word_glosses_text=db_sentence.word_glosses_text,
            word_glosses_json=db_sentence.word_glosses_json,
        ))
    return alignments


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sentence_alignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER NOT NULL,
            song_title TEXT NOT NULL,
            album TEXT,
            song_sentence_order INTEGER,
            txt_sentence_order INTEGER,
            alician_sentence TEXT NOT NULL DEFAULT '',
            txt_alician_sentence TEXT NOT NULL DEFAULT '',
            chinese_translation TEXT NOT NULL DEFAULT '',
            word_glosses_text TEXT NOT NULL DEFAULT '',
            word_glosses_json TEXT NOT NULL DEFAULT '[]',
            alignment_status TEXT NOT NULL,
            match_score REAL NOT NULL DEFAULT 0,
            match_method TEXT NOT NULL DEFAULT '',
            source_file TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(song_id) REFERENCES songs(id)
        );
        CREATE INDEX IF NOT EXISTS idx_sentence_alignments_song_order
            ON sentence_alignments(song_id, song_sentence_order);
        CREATE INDEX IF NOT EXISTS idx_sentence_alignments_status
            ON sentence_alignments(alignment_status);
        """
    )
    existing_columns = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(sentence_alignments)")
    }
    if "word_glosses_text" not in existing_columns:
        conn.execute(
            "ALTER TABLE sentence_alignments ADD COLUMN word_glosses_text TEXT NOT NULL DEFAULT ''"
        )
    if "word_glosses_json" not in existing_columns:
        conn.execute(
            "ALTER TABLE sentence_alignments ADD COLUMN word_glosses_json TEXT NOT NULL DEFAULT '[]'"
        )


def import_alignments(db_path: Path, source_path: Path, dry_run: bool = False) -> dict[str, object]:
    source_songs, parse_warnings = parse_source(source_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        db_songs = conn.execute(
            "SELECT id, title, Album, lyric FROM songs ORDER BY id"
        ).fetchall()
        matched, unmatched_source, match_warnings = match_source_songs(source_songs, db_songs)
        output: list[tuple[sqlite3.Row, Alignment]] = []
        for row in db_songs:
            db_sentences = extract_song_sentences(str(row["lyric"] or ""))
            source_song = matched.get(int(row["id"]))
            if source_song is None:
                alignments = [
                    Alignment(
                        order, None, sentence.alician, "", "",
                        "missing_song_translation", 0.0, "no_source_song",
                        word_glosses_text=sentence.word_glosses_text,
                        word_glosses_json=sentence.word_glosses_json,
                    )
                    for order, sentence in enumerate(db_sentences, start=1)
                ]
            else:
                alignments = align_song(db_sentences, source_song.pairs)
            output.extend((row, alignment) for alignment in alignments)

        counts: dict[str, int] = {}
        for _, alignment in output:
            counts[alignment.status] = counts.get(alignment.status, 0) + 1

        if not dry_run:
            ensure_schema(conn)
            conn.execute("DELETE FROM sentence_alignments")
            conn.executemany(
                """
                INSERT INTO sentence_alignments (
                    song_id, song_title, album, song_sentence_order, txt_sentence_order,
                    alician_sentence, txt_alician_sentence, chinese_translation,
                    word_glosses_text, word_glosses_json,
                    alignment_status, match_score, match_method, source_file, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        int(row["id"]), str(row["title"] or ""), str(row["Album"] or ""),
                        alignment.db_order, alignment.txt_order,
                        alignment.db_alician, alignment.txt_alician, alignment.chinese,
                        alignment.word_glosses_text, alignment.word_glosses_json,
                        alignment.status, alignment.score, alignment.method,
                        source_path.name, alignment.notes,
                    )
                    for row, alignment in output
                ],
            )
            conn.commit()

        return {
            "source_songs": len(source_songs),
            "matched_songs": len(matched),
            "unmatched_source_songs": [song.title for song in unmatched_source],
            "database_songs": len(db_songs),
            "database_songs_without_source": [
                str(row["title"] or "") for row in db_songs if int(row["id"]) not in matched
            ],
            "alignment_rows": len(output),
            "status_counts": counts,
            "warnings": parse_warnings + match_warnings,
            "dry_run": dry_run,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import sentence-level Alician-Chinese alignments.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    summary = import_alignments(args.db.resolve(), args.source.resolve(), args.dry_run)
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
