from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DB_PATH = Path(__file__).resolve().parent.parent / "translated.db"
TXT_PATH = Path(__file__).resolve().parent.parent / "Alician(1).txt"

ANNOTATION_RE = re.compile(r"^(.+?)：(.+)$")
POS_RE = re.compile(r"\b(adj|adv|art|conj|interj|n|num|prep|pron|v|vi|vt)\.", re.I)
NUMBERED_MEANING_RE = re.compile(r"[（(]\s*(\d+)\s*[）)]\s*([^（）()]*)")
CHINESE_CHAR_RE = re.compile(r"[\u3400-\u9fff]")

SONG_HEADER_RE = re.compile(
    r"^\d+\.\s*"  
    r"|interlude"
    r"|純音楽|纯音乐"
)

def _is_alcian_word(token: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z'-]*", token))

def _is_song_header(line: str) -> bool:
    if re.match(r"^\d+\.", line):
        return True
    if re.search(r"-interlude-", line, re.I):
        return True
    return False

def _is_meta_line(line: str) -> bool:
    return line in {"纯音乐", "(纯音乐)", "純音楽"}

def _clean_alcian_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r'[「」"“”]', '', line)
    line = re.sub(r'\s+', ' ', line)
    return line.strip()

def _extract_glosses(annotation: str) -> List[str]:
    annotation = annotation.strip()
    numbered = NUMBERED_MEANING_RE.findall(annotation)
    if numbered:
        glosses = []
        for _, meaning in numbered:
            meaning = meaning.strip(" ，,、；;\t\r\n")
            if meaning and CHINESE_CHAR_RE.search(meaning):
                glosses.append(meaning)
        if glosses:
            return glosses
    
    segments = POS_RE.split(annotation)
    glosses = []
    for segment in segments:
        segment = segment.strip(" .,;，。、；\t\r\n")
        segment = re.sub(r"[（(]\?[）)]", "", segment)
        segment = segment.strip()
        if not segment:
            continue
        sub_parts = re.split(r"[，,、；;]", segment)
        for part in sub_parts:
            part = part.strip().rstrip(".")
            if part and CHINESE_CHAR_RE.search(part):
                glosses.append(part)
    return glosses

def _extract_alcian_words(line: str) -> List[str]:
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", line)
    return words

def parse_songs_table(db_path: Path) -> Dict[Tuple[str, str], List[Dict]]:
    """Parse songs table → { (title, album): [{'alcian_line': str, 'words': [{'word': str, 'pos': str, 'glosses': [str]}]}] }"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    result = {}
    try:
        rows = conn.execute(
            "SELECT id, title, Album, lyric FROM songs WHERE lyric IS NOT NULL AND TRIM(lyric) <> ''"
        ).fetchall()
        for row in rows:
            key = (row["title"].strip(), (row["Album"] or "").strip())
            entries = []
            lyric = row["lyric"] or ""
            lines = lyric.splitlines()
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if not line:
                    i += 1
                    continue
                if _is_alcian_word(line.split()[0] if line.split() else ""):
                    alcian_line = _clean_alcian_line(line)
                    words_data = []
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j].strip()
                        if not next_line:
                            j += 1
                            continue
                        ann_match = ANNOTATION_RE.match(next_line)
                        if ann_match:
                            word = ann_match.group(1).strip()
                            rest = ann_match.group(2).strip()
                            pos_match = POS_RE.search(rest)
                            pos = pos_match.group(0).rstrip(".") if pos_match else ""
                            glosses = _extract_glosses(rest)
                            words_data.append({
                                "word": word,
                                "pos": pos,
                                "glosses": glosses,
                            })
                            j += 1
                        else:
                            break
                    if words_data:
                        entries.append({
                            "alcian_line": alcian_line,
                            "words": words_data,
                        })
                    i = j
                else:
                    i += 1
            if entries:
                result[key] = entries
    finally:
        conn.close()
    return result

def parse_txt_file(txt_path: Path) -> List[Dict]:
    """Parse Alician(1).txt → [
        {'song_title': str, 'album': str, 'pairs': [{'alcian': str, 'chinese': str}]}
    ]"""
    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    raw_lines = content.strip().splitlines()
    
    songs = []
    current_song = None
    current_album = "アリスシャッハと氷の世界樹"  
    album_order = [
        "アリスシャッハと氷の世界樹",
        "アリスシャッハと追憶の図書館",
        "SCHACH",
        "Single",
    ]
    album_index = 0
    i = 0
    
    album_markers = {
        "Maharajah": 1,
        "▷ NEW GAME": 2,
        "Forbidden Wonderland": 3,
    }
    
    while i < len(raw_lines):
        line = raw_lines[i].strip()
        if not line:
            i += 1
            continue
        
        if _is_meta_line(line):
            current_song = None
            i += 1
            continue
        
        if _is_song_header(line):
            title = line
            if album_index == 0 and i < 1200:
                pass
            else:
                for marker, idx in album_markers.items():
                    if marker.lower() in title.lower():
                        album_index = idx
                        break
            current_album = album_order[album_index]
            current_song = {
                "song_title": title,
                "album": current_album,
                "pairs": [],
            }
            songs.append(current_song)
            i += 1
            continue
        
        if _is_alcian_word(line.split()[0] if line.split() else ""):
            alcian_line = _clean_alcian_line(line)
            i += 1
            chinese_line = ""
            while i < len(raw_lines) and not raw_lines[i].strip():
                i += 1
            if i < len(raw_lines):
                next_line = raw_lines[i].strip()
                if not _is_alcian_word(next_line.split()[0] if next_line.split() else ""):
                    if not _is_song_header(next_line) and not _is_meta_line(next_line):
                        chinese_line = next_line.strip()
                        i += 1
            
            if current_song is not None:
                current_song["pairs"].append({
                    "alcian": alcian_line,
                    "chinese": chinese_line,
                })
            else:
                songs.append({
                    "song_title": "",
                    "album": current_album,
                    "pairs": [{"alcian": alcian_line, "chinese": chinese_line}],
                })
                current_song = songs[-1]
        else:
            i += 1
    
    return songs

def _clean_gloss(gloss: str) -> str:
    gloss = gloss.strip("?()（）. .,;，。、；\t\r\n")
    gloss = re.sub(r"[（(][^）)]*[）)]", "", gloss)
    gloss = gloss.strip("?()（）. .,;，。、；\t\r\n")
    return gloss

def _gloss_variants(gloss: str) -> List[str]:
    """Generate variants of the gloss for matching."""
    gloss = _clean_gloss(gloss)
    variants = [gloss]
    if gloss.endswith("的") and len(gloss) > 1:
        variants.append(gloss[:-1])
    if gloss.endswith("地") and len(gloss) > 1:
        variants.append(gloss[:-1])
    if gloss.endswith("了") and len(gloss) > 1:
        variants.append(gloss[:-1])
    if "（" not in gloss and "(" not in gloss:
        pass
    return variants

def find_gloss_in_text(gloss: str, text: str, used_ranges: List[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
    """Find gloss as substring in text, avoiding already-used ranges."""
    for variant in _gloss_variants(gloss):
        if not variant or len(variant) < 1:
            continue
        if not CHINESE_CHAR_RE.search(variant):
            continue
        pos = 0
        while True:
            idx = text.find(variant, pos)
            if idx == -1:
                break
            end = idx + len(variant)
            overlap = False
            for used_start, used_end in used_ranges:
                if idx < used_end and end > used_start:
                    overlap = True
                    break
            if not overlap:
                return (idx, end)
            pos = end
    return None

def align_line(words_data: List[Dict], chinese_text: str) -> List[Dict]:
    """Align each Alcian word to a position in the Chinese translation."""
    clean_chinese = chinese_text.strip()
    if not clean_chinese:
        clean_chinese = ""
    
    used_ranges: List[Tuple[int, int]] = []
    alignments = []
    
    for wp, wd in enumerate(words_data):
        word = wd["word"]
        pos_tag = wd["pos"]
        glosses = wd["glosses"]
        
        best_match = None
        best_range = None
        
        for gloss in glosses:
            match_range = find_gloss_in_text(gloss, clean_chinese, used_ranges)
            if match_range is not None:
                if best_match is None or len(gloss) > len(best_match):
                    best_match = gloss
                    best_range = match_range
        
        if best_match is not None and best_range is not None:
            used_ranges.append(best_range)
            matched_text = clean_chinese[best_range[0]:best_range[1]]
            natural_order = best_range[0]
        else:
            best_match = glosses[0] if glosses else ""
            matched_text = ""
            natural_order = -1
        
        alignments.append({
            "word_position": wp + 1,
            "alcian_word": word,
            "alcian_pos": pos_tag,
            "dictionary_gloss": best_match,
            "all_glosses": "|".join(glosses),
            "matched_chinese": matched_text,
            "natural_order": natural_order,
        })
    
    return alignments

def match_songs(
    parsed_db: Dict[Tuple[str, str], List[Dict]],
    parsed_txt: List[Dict],
) -> List[Dict]:
    """Match parsed database entries with txt entries."""
    results = []
    
    for txt_song in parsed_txt:
        txt_title = txt_song["song_title"]
        txt_album = txt_song["album"]
        
        best_key = None
        best_entries = None
        
        for (db_title, db_album), entries in parsed_db.items():
            if db_album == txt_album:
                txt_clean = re.sub(r'[^\w]', '', txt_title.lower())
                db_clean = re.sub(r'[^\w]', '', db_title.lower())
                if txt_clean[:6] == db_clean[:6] or db_clean in txt_clean or txt_clean in db_clean:
                    best_key = (db_title, db_album)
                    best_entries = entries
                    break
        
        if best_entries is None:
            continue
        
        results.append({
            "db_key": best_key,
            "txt_title": txt_title,
            "album": txt_album,
            "db_entries": best_entries,
            "txt_pairs": txt_song["pairs"],
        })
    
    return results

def build_alignment(db_path: Path, txt_path: Path):
    parsed_db = parse_songs_table(db_path)
    parsed_txt = parse_txt_file(txt_path)
    
    print(f"Parsed {len(parsed_db)} songs from database")
    print(f"Parsed {len(parsed_txt)} songs from txt file")
    
    matched = match_songs(parsed_db, parsed_txt)
    print(f"Matched {len(matched)} songs")
    
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("DROP TABLE IF EXISTS word_alignment")
        conn.execute("""
            CREATE TABLE word_alignment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                song_id INTEGER,
                song_title TEXT,
                album TEXT,
                alcian_line TEXT NOT NULL,
                chinese_translation TEXT NOT NULL,
                word_position INTEGER NOT NULL,
                alcian_word TEXT NOT NULL,
                alcian_pos TEXT,
                dictionary_gloss TEXT,
                all_glosses TEXT,
                matched_chinese TEXT,
                natural_order INTEGER
            )
        """)
        
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, Album FROM songs")
        song_lookup = {(row[1].strip(), (row[2] or "").strip()): row[0] for row in cursor.fetchall()}
        
        total_rows = 0
        seen_pairs = set()
        
        for match in matched:
            db_key = match["db_key"]
            song_id = song_lookup.get(db_key)
            song_title = db_key[0]
            album = db_key[1]
            
            db_entries_by_line = {}
            for entry in match["db_entries"]:
                db_entries_by_line[entry["alcian_line"]] = entry
            
            for pair in match["txt_pairs"]:
                alcian = pair["alcian"]
                chinese = pair["chinese"]
                
                pair_key = (song_id, alcian, chinese)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                
                db_entry = db_entries_by_line.get(alcian)
                if db_entry is None:
                    for key in db_entries_by_line:
                        if key.replace(" ", "") == alcian.replace(" ", ""):
                            db_entry = db_entries_by_line[key]
                            break
                
                if db_entry is None:
                    continue
                
                alignments = align_line(db_entry["words"], chinese)
                
                if not alignments:
                    continue
                
                valid_orders = [a["natural_order"] for a in alignments if a["natural_order"] >= 0]
                if valid_orders:
                    sorted_alignments = sorted(
                        enumerate(alignments),
                        key=lambda x: (x[1]["natural_order"] if x[1]["natural_order"] >= 0 else 99999, x[0])
                    )
                    for rank, (_, alignment) in enumerate(sorted_alignments):
                        alignment["natural_order"] = alignment["natural_order"] if alignment["natural_order"] >= 0 else rank + 1000
                
                sorted_by_natural = sorted(
                    alignments,
                    key=lambda a: a["natural_order"]
                )
                
                for final_order, alignment in enumerate(sorted_by_natural):
                    conn.execute(
                        """INSERT INTO word_alignment (
                            song_id, song_title, album, alcian_line, chinese_translation,
                            word_position, alcian_word, alcian_pos, dictionary_gloss,
                            all_glosses, matched_chinese, natural_order
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            song_id, song_title, album,
                            alcian, chinese,
                            alignment["word_position"],
                            alignment["alcian_word"],
                            alignment["alcian_pos"],
                            alignment["dictionary_gloss"],
                            alignment["all_glosses"],
                            alignment["matched_chinese"],
                            alignment["natural_order"],
                        ),
                    )
                    total_rows += 1
        
        conn.commit()
        print(f"Inserted {total_rows} rows into word_alignment table")
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_word_alignment_song ON word_alignment(song_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_word_alignment_word ON word_alignment(alcian_word)")
        
        stats = conn.execute("""
            SELECT COUNT(*), COUNT(DISTINCT alcian_word), 
                   SUM(CASE WHEN matched_chinese != '' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN matched_chinese == '' THEN 1 ELSE 0 END)
            FROM word_alignment
        """).fetchone()
        print(f"Stats: total={stats[0]}, unique_words={stats[1]}, matched={stats[2]}, unmatched={stats[3]}")
        
        sample = conn.execute(
            "SELECT alcian_line, chinese_translation, alcian_word, dictionary_gloss, matched_chinese, natural_order "
            "FROM word_alignment WHERE song_title LIKE '%Alice Music%' "
            "ORDER BY alcian_line, natural_order LIMIT 30"
        ).fetchall()
        
        print("\n=== Sample alignments (Alice Music) ===")
        current_line = ""
        for row in sample:
            if row[0] != current_line:
                current_line = row[0]
                print(f"\nAlcian: {row[0]}")
                print(f"Chinese: {row[1]}")
                print(f"  {'Word':<15} {'Gloss':<20} {'Matched':<15} {'Order'}")
            print(f"  {row[2]:<15} {row[3]:<20} {row[4]:<15} {row[5]}")
        
    finally:
        conn.close()

if __name__ == "__main__":
    build_alignment(DB_PATH, TXT_PATH)
