# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
import re
import tkinter as tk
from typing import List, Optional, Tuple
from tkinter import scrolledtext
import os
import sys

# 确保能找到正确的 config.py 文件
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config


class TextProcessor:
    # 预编译常用正则表达式
    _WHITESPACE_PATTERN = re.compile(r'\s+')
    
    @staticmethod
    def normalize_text(text: str) -> str:
        if not text:
            return ""
        
        # 优化：避免不必要的字符串替换操作
        # 直接使用splitlines和join处理换行符
        lines = []
        for line in text.splitlines():
            # 替换特殊空白字符
            line = line.replace('\u3000', ' ').replace('\t', ' ').replace('\u00A0', ' ')
            stripped = line.strip()
            if stripped:
                # 优化：仅对非空行应用空白字符替换
                normalized = TextProcessor._WHITESPACE_PATTERN.sub(' ', stripped)
                lines.append(normalized)
        
        return '\n'.join(lines)

    @staticmethod
    def extract_valid_examples(lyric: str, search_word: str) -> List[str]:
        return TextProcessor.extract_all_valid_paragraphs(lyric, search_word)

    @staticmethod
    def extract_all_valid_paragraphs(lyric: str, search_word: Optional[str] = None) -> List[str]:
        if not lyric:
            return []
            
        # 直接使用splitlines避免额外的rstrip操作
        lines = lyric.splitlines()
        valid = []
        used = set()
        total_lines = len(lines)
        
        # 优化：避免不必要的正则表达式编译
        has_search_word = bool(search_word)
        if has_search_word:
            # 使用预编译模式
            pattern = TextProcessor._get_compiled_pattern(search_word)

        for i in range(total_lines):
            if i in used:
                continue
            
            is_first = (i == 0)
            # 优化：避免重复计算和strip操作
            has_empty_above = is_first or (not lines[i-1] or lines[i-1].isspace())
            has_empty_below = (i == total_lines-1) or (i+1 < total_lines and (not lines[i+1] or lines[i+1].isspace()))
            
            if is_first or (has_empty_above and has_empty_below):
                para_lines = []
                empty_cnt = 0
                j = i
                while j < total_lines and empty_cnt < 2:
                    line = lines[j]
                    para_lines.append(line)
                    used.add(j)
                    # 优化：使用更高效的空字符串检查
                    if not line or line.isspace():
                        empty_cnt += 1
                    j += 1
                
                # 优化：避免不必要的规范化操作
                raw = '\n'.join(para_lines)
                if raw.strip() and (not has_search_word or pattern.search(raw)):
                    valid.append(raw)
        return valid

    @staticmethod
    def find_paragraph_positions(lyric: str, paragraph: str) -> Tuple[int, int]:
        if not lyric or not paragraph:
            return 0, 0
        
        # 首先尝试直接查找原始段落（避免不必要的规范化）
        try:
            start_pos = lyric.find(paragraph)
            if start_pos != -1:
                return (start_pos, start_pos + len(paragraph))
        except Exception:
            pass
        
        # 如果直接查找失败，再使用规范化方法
        norm_lyric_lines = []
        lyric_lines = lyric.split('\n')
        norm_lyric_lines = [TextProcessor.normalize_text(line) for line in lyric_lines]
        
        para_lines = paragraph.split('\n')
        norm_para = [TextProcessor.normalize_text(line) for line in para_lines]
        para_len = len(norm_para)
        start_idx = -1

        # 查找匹配的段落起始位置
        for i in range(len(norm_lyric_lines) - para_len + 1):
            match = True
            for j in range(para_len):
                if norm_lyric_lines[i+j] != norm_para[j]:
                    match = False
                    break
            if match:
                start_idx = i
                break
        
        if start_idx == -1:
            return (0, min(len(paragraph), len(lyric)))
        
        # 计算字符位置（优化：避免重复分割字符串）
        start_pos = 0
        for i in range(start_idx):
            start_pos += len(lyric_lines[i]) + 1
        
        end_pos = start_pos
        for j in range(para_len):
            end_pos += len(lyric_lines[start_idx + j]) + 1
        end_pos -= 1
        return (start_pos, end_pos)

    # 存储已编译的正则表达式，避免重复编译
    _compiled_patterns = {}
    
    @classmethod
    def _get_compiled_pattern(cls, word: str) -> re.Pattern:
        """获取或编译正则表达式模式"""
        if word not in cls._compiled_patterns:
            # 预编译并存储正则表达式
            cls._compiled_patterns[word] = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
        return cls._compiled_patterns[word]
    
    @classmethod
    def highlight_text(cls, text_widget: scrolledtext.ScrolledText, text: str, word: str) -> None:
        if not word:
            return
        
        text_widget.tag_remove("highlight", 1.0, tk.END)
        # 使用预编译的正则表达式
        pattern = cls._get_compiled_pattern(word)
        
        for match in pattern.finditer(text):
            s, e = match.span()
            text_widget.tag_add("highlight", f"1.0 + {s} chars", f"1.0 + {e} chars")
        text_widget.tag_configure("highlight", background=Config.HIGHLIGHT_COLOR)
