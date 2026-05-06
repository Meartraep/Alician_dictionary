import os
import re
import sys
import tkinter as tk
from tkinter import scrolledtext
from typing import List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config


class TextProcessor:
    _WHITESPACE_PATTERN = re.compile(r"\s+")
    _COLON_PATTERN = re.compile(r"[：:]")
    _compiled_patterns = {}

    @staticmethod
    def normalize_text(text: str) -> str:
        if not text:
            return ""

        lines = []
        for line in text.splitlines():
            line = line.replace("\u3000", " ").replace("\t", " ").replace("\u00A0", " ")
            stripped = line.strip()
            if stripped:
                lines.append(TextProcessor._WHITESPACE_PATTERN.sub(" ", stripped))
        return "\n".join(lines)

    @staticmethod
    def is_annotation_line(line: str) -> bool:
        return bool(line and TextProcessor._COLON_PATTERN.search(line))

    @staticmethod
    def split_paragraphs(lyric: str) -> List[dict]:
        if not lyric:
            return []

        lines = lyric.splitlines()
        paragraphs = []
        current_lines = []

        def flush() -> None:
            if current_lines:
                paragraphs.append(TextProcessor._build_paragraph(current_lines))
                current_lines.clear()

        for raw_line in lines:
            if not raw_line.strip():
                if current_lines:
                    current_lines.append(raw_line)
                continue

            if not TextProcessor.is_annotation_line(raw_line):
                flush()
                current_lines.append(raw_line)
            else:
                if current_lines:
                    current_lines.append(raw_line)

        flush()
        return paragraphs

    @staticmethod
    def _build_paragraph(lines: List[str]) -> dict:
        items = []
        for raw in lines:
            items.append(
                {
                    "raw": raw,
                    "normalized": TextProcessor.normalize_text(raw),
                    "is_annotation": TextProcessor.is_annotation_line(raw),
                }
            )
        return {"lines": items, "text": "\n".join(item["raw"] for item in items)}

    @staticmethod
    def extract_valid_examples(lyric: str, search_word: str) -> List[str]:
        return TextProcessor.extract_all_valid_paragraphs(lyric, search_word)

    @staticmethod
    def extract_all_valid_paragraphs(lyric: str, search_word: Optional[str] = None) -> List[str]:
        if not lyric:
            return []

        paragraphs = TextProcessor.split_paragraphs(lyric)
        valid = []
        has_search_word = bool(search_word)
        pattern = TextProcessor._get_compiled_pattern(search_word) if has_search_word else None

        for paragraph in paragraphs:
            if not paragraph["text"].strip():
                continue

            if has_search_word:
                if not any(
                    pattern.search(line["raw"])
                    for line in paragraph["lines"]
                    if not line["is_annotation"]
                ):
                    continue

            valid.append(paragraph["text"])

        return valid

    @staticmethod
    def find_paragraph_positions(lyric: str, paragraph: str) -> Tuple[int, int]:
        if not lyric or not paragraph:
            return 0, 0

        target = TextProcessor.normalize_text(paragraph)
        offset = 0

        for block in TextProcessor.split_paragraphs(lyric):
            block_text = block["text"]
            if TextProcessor.normalize_text(block_text) == target:
                start_pos = lyric.find(block_text, offset)
                if start_pos != -1:
                    return start_pos, start_pos + len(block_text)
            offset = lyric.find(block_text, offset)
            if offset != -1:
                offset += len(block_text)

        start_pos = lyric.find(paragraph)
        if start_pos != -1:
            return start_pos, start_pos + len(paragraph)

        return 0, min(len(paragraph), len(lyric))

    @classmethod
    def _get_compiled_pattern(cls, word: str) -> re.Pattern:
        if word not in cls._compiled_patterns:
            cls._compiled_patterns[word] = re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE)
        return cls._compiled_patterns[word]

    @classmethod
    def highlight_text(cls, text_widget: scrolledtext.ScrolledText, text: str, word: str) -> None:
        if not word:
            return

        text_widget.tag_remove("word_highlight", 1.0, tk.END)
        pattern = cls._get_compiled_pattern(word)

        for match in pattern.finditer(text):
            s, e = match.span()
            text_widget.tag_add("word_highlight", f"1.0 + {s} chars", f"1.0 + {e} chars")
        text_widget.tag_configure("word_highlight", background=Config.HIGHLIGHT_COLOR)

    @staticmethod
    def center_text_range(text_widget: scrolledtext.ScrolledText, start_index: str, end_index: str) -> None:
        """
        尽量把指定范围滚动到可视区域中间。
        先用 displaylines 估算位置，再用 bbox 做小幅修正。
        """
        try:
            text_widget.update_idletasks()

            line_info = text_widget.dlineinfo("1.0")
            if not line_info:
                text_widget.see(start_index)
                return

            line_height = max(1, line_info[3])
            viewport_height = max(1, text_widget.winfo_height())
            visible_lines = max(1, viewport_height // line_height)

            try:
                start_display = int(text_widget.count("1.0", start_index, "displaylines")[0])
                end_display = int(text_widget.count("1.0", end_index, "displaylines")[0])
                total_display = int(text_widget.count("1.0", "end-1c", "displaylines")[0]) + 1
                paragraph_display = max(1, end_display - start_display + 1)

                target_mid_display = start_display + paragraph_display // 2
                desired_top_display = max(0, target_mid_display - visible_lines // 2)
                max_top_display = max(0, total_display - visible_lines)
                desired_top_display = min(desired_top_display, max_top_display)

                text_widget.yview_moveto(desired_top_display / max(1, total_display))
            except Exception:
                start_line = int(text_widget.index(start_index).split(".")[0])
                end_line = int(text_widget.index(end_index).split(".")[0])
                paragraph_lines = max(1, end_line - start_line + 1)
                target_mid_line = start_line + paragraph_lines // 2
                desired_top_line = max(1, target_mid_line - visible_lines // 2)
                text_widget.yview_moveto((desired_top_line - 1) / max(1, int(text_widget.index("end-1c").split(".")[0])))

            text_widget.update_idletasks()

            # 小幅修正：如果目标范围仍然偏下，继续向上滚动一点，保证不会贴近底部。
            for _ in range(3):
                bbox = text_widget.bbox(start_index)
                if not bbox:
                    break
                _, y, _, h = bbox
                if y <= viewport_height * 0.28:
                    break
                step = max(1, int((y - viewport_height * 0.30) / max(1, h)))
                text_widget.yview_scroll(-step, "units")
                text_widget.update_idletasks()
        except Exception:
            try:
                text_widget.see(start_index)
            except Exception:
                pass
