import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import sqlite3
import re
from tkinter import font
import os
import sys
import threading
from collections import defaultdict
from typing import List, Dict, Tuple, Optional





class Config:
    APP_TITLE = "爱丽丝语词典"
    INITIAL_SIZE = "1000x600"
    MIN_SIZE = "800x500"
    DB_NAME = "translated.db"  # 数据库文件名
    REQUIRED_TABLES = {"dictionary": ["words", "explanation"], "songs": ["title", "lyric", "Album"]}
    
    if sys.platform == 'win32':
        FONT_FAMILY = "SimHei"
        DEFAULT_FONT_SIZE = 10
        ENTRY_FONT_SIZE = 12
    elif sys.platform == 'darwin':
        FONT_FAMILY = "PingFang SC"
        DEFAULT_FONT_SIZE = 11
        ENTRY_FONT_SIZE = 13
    else:
        FONT_FAMILY = "WenQuanYi Zen Hei"
        DEFAULT_FONT_SIZE = 10
        ENTRY_FONT_SIZE = 12
    
    LABEL_FONT_SIZE = 9
    EXAMPLE_MIN_HEIGHT = 4
    SOURCES_BOX_HEIGHT = 9
    HIGHLIGHT_COLOR = "#FFD700"
    CURRENT_HIGHLIGHT_COLOR = "#FFFFCC"
    INFO_COLOR = "#666666"
    CURRENT_DB = DB_NAME


class DatabaseHandler:
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None

    def connect(self) -> bool:
        try:
            # 检查连接是否已经存在且有效
            if self.conn is not None:
                try:
                    # 测试连接是否有效
                    self.conn.execute("SELECT 1")
                    return True
                except sqlite3.Error:
                    # 连接无效，需要重新连接
                    self.close()
            
            # 新增：检查数据库文件是否存在
            if not self.db_name.startswith(':memory:') and not os.path.exists(self.db_name):
                messagebox.showerror("数据库错误", f"数据库文件不存在: {self.db_name}")
                return False
            
            # 确保之前的连接已关闭
            self.close()
            
            self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
            self.conn.execute("PRAGMA cache_size = -1000")
            self.conn.execute("PRAGMA synchronous = OFF")
            self.cursor = self.conn.cursor()
            return self._verify_database_structure()
        except sqlite3.Error as e:
            messagebox.showerror("数据库错误", f"连接数据库失败: {str(e)}")
            self.close()  # 确保连接已关闭
            return False
            
    def __del__(self):
        """析构函数确保连接关闭"""
        self.close()

    def _verify_database_structure(self) -> bool:
        try:
            for table, fields in Config.REQUIRED_TABLES.items():
                self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
                if not self.cursor.fetchone():
                    raise Exception(f"缺少{table}表")
                
                self.cursor.execute(f"PRAGMA table_info({table})")
                table_fields = [row[1] for row in self.cursor.fetchall()]
                for field in fields:
                    if field not in table_fields:
                        raise Exception(f"{table}表缺少字段: {field}")
            return True
        except Exception as e:
            messagebox.showerror("数据库错误", f"数据库结构验证失败: {str(e)}")
            return False

    # 新增：is_exact参数控制精确/模糊匹配，True为精确匹配（区分大小写+完全匹配）
    def search_words(self, query: str, is_exact: bool) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        if not self.cursor:
            return [], []
        
        # 精确匹配逻辑：不转小写+完全匹配（=）
        if is_exact:
            self.cursor.execute("SELECT words, explanation FROM dictionary WHERE words = ? LIMIT 20", (query,))
            alice_res = self.cursor.fetchall()
            self.cursor.execute("SELECT words, explanation FROM dictionary WHERE explanation = ? LIMIT 20", (query,))
            chinese_res = self.cursor.fetchall()
        # 模糊匹配逻辑：转小写+包含匹配（LIKE %query%）
        else:
            self.cursor.execute("SELECT words, explanation FROM dictionary WHERE LOWER(words) LIKE LOWER(?) LIMIT 20", (f'%{query}%',))
            alice_res = self.cursor.fetchall()
            self.cursor.execute("SELECT words, explanation FROM dictionary WHERE LOWER(explanation) LIKE LOWER(?) LIMIT 20", (f'%{query}%',))
            chinese_res = self.cursor.fetchall()
        
        return alice_res, chinese_res

    def get_all_words(self) -> List[Tuple[str, str]]:
        return self.cursor.fetchall() if (self.cursor and self.cursor.execute("SELECT words, explanation FROM dictionary")) else []

    def find_songs_with_word(self, word: str) -> List[Tuple[str, str, str]]:
        if not self.cursor or not word:
            return []
        
        self.cursor.execute("SELECT title, lyric, Album FROM songs WHERE lyric LIKE ? OR title LIKE ? OR Album LIKE ?", (f'%{word.lower()}%',)*3)
        return self.cursor.fetchall()

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None


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


class UIBuilder:
    def __init__(self, root: tk.Tk, app: 'AliceDictionaryApp'):
        self.root = root
        self.app = app
        self.setup_fonts()
        
        self.main_frame = None
        self.left_frame = None
        self.right_frame = None
        self.query_entry = None
        self.search_button = None
        self.results_canvas = None
        self.results_scrollbar = None
        self.results_container = None
        self.examples_canvas = None
        self.examples_scrollbar = None
        self.examples_content = None
        self.progress_label = None
        self.examples_frame = None
        # 新增：精确查找复选框变量
        self.exact_match_var = tk.BooleanVar(value=False)

    def setup_fonts(self) -> None:
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(family=Config.FONT_FAMILY, size=Config.DEFAULT_FONT_SIZE)
        self.root.option_add("*Font", default_font)
        
        # 配置PanedWindow样式，实现分隔线高亮效果
        style = ttk.Style()
        style.configure("TPanedwindow", background=Config.INFO_COLOR)
        style.configure("TSash", background=Config.INFO_COLOR, sashthickness=8)
        style.map("TSash", background=[("active", "#FFD700")])

    def create_main_window(self) -> None:
        self.root.title(Config.APP_TITLE)
        self.root.geometry(Config.INITIAL_SIZE)
        self.root.minsize(*Config.MIN_SIZE.split('x'))
        if sys.platform == 'darwin':
            self.root.tk.call('tk::unsupported::MacWindowStyle', 'style', self.root._w, 'plain')

    def create_widgets(self) -> None:
        self._create_main_frames()
        self._create_query_area()
        self._create_results_area()
        self._create_examples_area()
        self.root.update_idletasks()

    def _create_main_frames(self) -> None:
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 使用PanedWindow实现左右两栏的宽度调整
        self.paned_window = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)
        
        # 左侧查询结果栏
        self.left_frame = ttk.Frame(self.paned_window, padding="5")
        self.paned_window.add(self.left_frame, weight=1)
        
        # 右侧例句栏
        self.right_frame = ttk.Frame(self.paned_window, padding="5")
        self.paned_window.add(self.right_frame, weight=1)

    def _create_query_area(self) -> None:
        query_frame = ttk.Frame(self.left_frame)
        query_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.query_entry = ttk.Entry(query_frame, font=(Config.FONT_FAMILY, Config.ENTRY_FONT_SIZE))
        self.query_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.query_entry.bind('<Return>', lambda e: self.app.search_word())
        self.query_entry.focus_set()
        
        # 新增：精确查找复选框（放在搜索按钮左侧）
        exact_checkbox = ttk.Checkbutton(
            query_frame, 
            text="精确查找", 
            variable=self.exact_match_var,
            onvalue=True,
            offvalue=False
        )
        exact_checkbox.pack(side=tk.RIGHT, padx=(5, 5))
        
        self.search_button = ttk.Button(query_frame, text="查找", command=self.app.search_word)
        self.search_button.pack(side=tk.RIGHT)

    def _create_results_area(self) -> None:
        result_frame = ttk.LabelFrame(self.left_frame, text="查询结果", padding="5")
        result_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建主Canvas和滚动条框架
        canvas_frame = ttk.Frame(result_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.results_canvas = tk.Canvas(canvas_frame)
        self.results_scrollbar_y = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.results_canvas.yview)
        self.results_scrollbar_x = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.results_canvas.xview)
        self.results_container = ttk.Frame(self.results_canvas)
        
        # 配置Canvas滚动区域和滚动条
        self.results_container.bind("<Configure>", lambda e: self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all")))
        self.results_canvas.bind("<Configure>", lambda e: self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all")))
        self.results_canvas.create_window((0, 0), window=self.results_container, anchor="nw")
        self.results_canvas.configure(yscrollcommand=self.results_scrollbar_y.set, xscrollcommand=self.results_scrollbar_x.set)
        
        # 存储事件绑定，以便后续清理
        self._mouse_wheel_bindings = []
        # 为整个左侧栏框架和canvas添加鼠标滚轮事件绑定，确保整个左侧栏区域都能响应
        for evt in ["<MouseWheel>", "<Button-4>", "<Button-5>"]:
            # 为left_frame添加事件绑定
            binding_id = self.left_frame.bind(evt, self.app.on_mouse_wheel)
            self._mouse_wheel_bindings.append((self.left_frame, evt, binding_id))
            # 为canvas添加事件绑定
            binding_id = self.results_canvas.bind(evt, self.app.on_mouse_wheel)
            self._mouse_wheel_bindings.append((self.results_canvas, evt, binding_id))
            # 为results_container添加事件绑定
            binding_id = self.results_container.bind(evt, self.app.on_mouse_wheel)
            self._mouse_wheel_bindings.append((self.results_container, evt, binding_id))
        
        # 绑定键盘左右箭头事件
        self.results_canvas.bind("<Left>", lambda e: self.results_canvas.xview_scroll(-1, "units"))
        self.results_canvas.bind("<Right>", lambda e: self.results_canvas.xview_scroll(1, "units"))
        # 绑定键盘上下箭头事件，用于控制垂直滚动
        self.results_canvas.bind("<Up>", lambda e: self.results_canvas.yview_scroll(-1, "units"))
        self.results_canvas.bind("<Down>", lambda e: self.results_canvas.yview_scroll(1, "units"))
        # 为results_container添加焦点绑定，确保键盘事件能被捕获
        self.results_container.bind("<FocusIn>", lambda e: self.results_canvas.focus_set())
        
        # 布局组件
        self.results_canvas.grid(row=0, column=0, sticky="nsew")
        self.results_scrollbar_y.grid(row=0, column=1, sticky="ns")
        self.results_scrollbar_x.grid(row=1, column=0, sticky="ew")
        
        # 配置grid权重，使Canvas能自动扩展
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        
        # 存储引用到主应用
        self.app._result_canvas = self.results_canvas

    def _create_examples_area(self) -> None:
        example_title_frame = ttk.Frame(self.right_frame)
        example_title_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(example_title_frame, text="例句:").pack(side=tk.LEFT)
        
        self.examples_frame = ttk.Frame(self.right_frame)
        self.examples_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建主Canvas和滚动条框架
        canvas_frame = ttk.Frame(self.examples_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.examples_canvas = tk.Canvas(canvas_frame)
        self.examples_scrollbar_y = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.examples_canvas.yview)
        self.examples_scrollbar_x = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.examples_canvas.xview)
        self.examples_content = ttk.Frame(self.examples_canvas)
        
        # 配置Canvas滚动区域和滚动条
        self.examples_content.bind("<Configure>", lambda e: self.examples_canvas.configure(scrollregion=self.examples_canvas.bbox("all")))
        self.examples_canvas.bind("<Configure>", lambda e: self.examples_canvas.configure(scrollregion=self.examples_canvas.bbox("all")))
        self.examples_canvas.create_window((0, 0), window=self.examples_content, anchor="nw")
        self.examples_canvas.configure(yscrollcommand=self.examples_scrollbar_y.set, xscrollcommand=self.examples_scrollbar_x.set)
        
        # 为整个examples_frame和canvas添加鼠标滚轮事件绑定，确保整个右侧栏区域都能响应
        for evt in ["<MouseWheel>", "<Button-4>", "<Button-5>"]:
            binding_id = self.examples_frame.bind(evt, self.app.on_mouse_wheel)
            self._mouse_wheel_bindings.append((self.examples_frame, evt, binding_id))
            binding_id = self.examples_canvas.bind(evt, self.app.on_mouse_wheel)
            self._mouse_wheel_bindings.append((self.examples_canvas, evt, binding_id))
            binding_id = self.examples_content.bind(evt, self.app.on_mouse_wheel)
            self._mouse_wheel_bindings.append((self.examples_content, evt, binding_id))
        
        # 绑定键盘左右箭头事件
        self.examples_canvas.bind("<Left>", lambda e: self.examples_canvas.xview_scroll(-1, "units"))
        self.examples_canvas.bind("<Right>", lambda e: self.examples_canvas.xview_scroll(1, "units"))
        # 绑定键盘上下箭头事件，用于控制垂直滚动
        self.examples_canvas.bind("<Up>", lambda e: self.examples_canvas.yview_scroll(-1, "units"))
        self.examples_canvas.bind("<Down>", lambda e: self.examples_canvas.yview_scroll(1, "units"))
        # 为examples_content添加焦点绑定，确保键盘事件能被捕获
        self.examples_content.bind("<FocusIn>", lambda e: self.examples_canvas.focus_set())
        
        # 布局组件
        self.examples_canvas.grid(row=0, column=0, sticky="nsew")
        self.examples_scrollbar_y.grid(row=0, column=1, sticky="ns")
        self.examples_scrollbar_x.grid(row=1, column=0, sticky="ew")
        
        # 配置grid权重，使Canvas能自动扩展
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        
        self.progress_label = ttk.Label(self.right_frame, text="", font=(Config.FONT_FAMILY, Config.LABEL_FONT_SIZE))
        self.progress_label.pack(anchor=tk.CENTER, pady=(5, 0))

    def clear_results(self) -> None:
        # 收集所有子组件，然后移除事件绑定并销毁
        children = list(self.results_container.winfo_children())  # 转换为列表以避免迭代时修改
        for widget in children:
            # 移除组件上的所有事件绑定
            try:
                widget.unbind("<Button-1>")
                widget.unbind("<Enter>")
                widget.unbind("<Leave>")
            except:
                pass
            widget.destroy()
        self.root.update_idletasks()

    def clear_examples(self) -> None:
        # 收集所有子组件，然后移除事件绑定并销毁
        children = list(self.examples_content.winfo_children())  # 转换为列表以避免迭代时修改
        for widget in children:
            # 移除组件上的所有事件绑定
            try:
                widget.unbind("<Button-1>")
                widget.unbind("<Enter>")
                widget.unbind("<Leave>")
            except:
                pass
            widget.destroy()
        self.root.update_idletasks()

    def add_result_section(self, title: str) -> None:
        ttk.Label(self.results_container, text=title, font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "bold")).pack(anchor=tk.W, pady=(5, 2))

    def add_result_entry(self, word: str, explanation: str, result_type: str, index: int) -> None:
        frame = ttk.Frame(self.results_container)
        frame.pack(fill=tk.X, padx=5, pady=3)
        
        # 设置事件标签，支持事件冒泡
        frame.bindtags((frame, self.results_container, "all"))
        
        word_frame = ttk.Frame(frame)
        word_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 添加滚轮事件绑定
        for evt in ["<MouseWheel>", "<Button-4>", "<Button-5>"]:
            frame.bind(evt, self.app.on_mouse_wheel)
            word_frame.bind(evt, self.app.on_mouse_wheel)
        
        if result_type == "alice":
            label1 = ttk.Label(word_frame, text=f"爱丽丝语: {word}", font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "bold"))
            label1.pack(anchor=tk.W)
            label2 = ttk.Label(word_frame, text=f"中文翻译: {explanation}", wraplength=400)
            label2.pack(anchor=tk.W)
            # 为标签添加滚轮事件绑定
            for evt in ["<MouseWheel>", "<Button-4>", "<Button-5>"]:
                label1.bind(evt, self.app.on_mouse_wheel)
                label2.bind(evt, self.app.on_mouse_wheel)
        else:
            label1 = ttk.Label(word_frame, text=f"中文: {explanation}", font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "bold"))
            label1.pack(anchor=tk.W)
            label2 = ttk.Label(word_frame, text=f"爱丽丝语: {word}", wraplength=400)
            label2.pack(anchor=tk.W)
            # 为标签添加滚轮事件绑定
            for evt in ["<MouseWheel>", "<Button-4>", "<Button-5>"]:
                label1.bind(evt, self.app.on_mouse_wheel)
                label2.bind(evt, self.app.on_mouse_wheel)
        
        button = ttk.Button(frame, text="查询例句", command=lambda w=word: self.app.start_show_examples(w))
        button.pack(side=tk.RIGHT, padx=5)
        # 为按钮添加滚轮事件绑定
        for evt in ["<MouseWheel>", "<Button-4>", "<Button-5>"]:
            button.bind(evt, self.app.on_mouse_wheel)

    def add_no_results_message(self, query: str) -> None:
        ttk.Label(self.results_container, text=f"未找到 '{query}' 的翻译", font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE)).pack(anchor=tk.W, pady=5)
        self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all"))

    def add_no_result_example_button(self, query: str) -> None:
        btn_frame = ttk.Frame(self.results_container)
        btn_frame.pack(fill=tk.X, pady=(5, 10))
        ttk.Button(btn_frame, text=f"查询包含 '{query}' 的例句", command=lambda w=query: self.app.start_show_examples(w)).pack(anchor=tk.CENTER)

    def add_examples_header(self, count: int) -> None:
        ttk.Label(self.examples_content, text=f"找到 {count} 个例句:", font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "bold")).pack(anchor=tk.W, pady=(5, 5))

    def add_example_entry(self, example: Dict[str, str], index: int, search_word: str) -> None:
        frame = ttk.LabelFrame(self.examples_content, text=f"例句 {index + 1}", padding="5")
        frame.pack(fill=tk.X, padx=5, pady=5)
        # 减少不必要的事件绑定，使用事件冒泡
        frame.bindtags((frame, self.examples_content, "all"))
        
        button = ttk.Button(frame, text="查看完整歌词", command=lambda idx=index, t=example['title'], a=example['album'], l=example['lyric'], p=example['paragraph']: self.app.show_full_lyric(idx, t, a, l, p))
        button.pack(anchor=tk.W, pady=(0, 2))
        
        label = ttk.Label(frame, text=f"来源: {example['album']} - {example['title']}", font=(Config.FONT_FAMILY, Config.LABEL_FONT_SIZE), foreground=Config.INFO_COLOR)
        label.pack(anchor=tk.W, pady=(0, 5))
        
        text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE))
        text_widget.pack(fill=tk.X, expand=True)
        text_widget.insert(tk.END, example['paragraph'])
        TextProcessor.highlight_text(text_widget, example['paragraph'], search_word)
        
        line_count = example['paragraph'].count('\n') + 1
        text_widget.configure(height=max(line_count, Config.EXAMPLE_MIN_HEIGHT), state=tk.DISABLED)
        
        # 为所有子组件添加鼠标滚轮事件绑定
        for evt in ["<MouseWheel>", "<Button-4>", "<Button-5>"]:
            frame.bind(evt, self.app.on_mouse_wheel)
            button.bind(evt, self.app.on_mouse_wheel)
            label.bind(evt, self.app.on_mouse_wheel)
            text_widget.bind(evt, self.app.on_mouse_wheel)

    def add_no_examples_message(self, word: str) -> None:
        ttk.Label(self.examples_content, text=f"未找到包含 '{word}' 的例句").pack(pady=10)
        self.examples_canvas.configure(scrollregion=self.examples_canvas.bbox("all"))


class AliceDictionaryApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.current_word = ""
        self.current_matched_word = ""
        self.current_examples: List[Dict[str, str]] = []
        self.current_song_stats = defaultdict(lambda: {'before': 0, 'after': 0})
        self.is_processing = False
        
        # 仅使用默认数据库
        self.db_handler = DatabaseHandler(Config.CURRENT_DB)
        
        if not self.db_handler.connect():
            messagebox.showerror("数据库错误", f"无法连接到默认数据库: {Config.DB_NAME}")
            self.root.destroy()
            return
        
        self.ui = UIBuilder(root, self)
        self.ui.create_main_window()
        self.ui.create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # 为后续清理存储必要的引用
        self._result_canvas = None
        self._examples_canvas = None

    def on_mouse_wheel(self, event: tk.Event) -> None:
        # 优化鼠标滚轮事件处理，直接判断事件源所属区域
        widget = event.widget
        
        # 快速判断：如果是examples_content或其后代，滚动examples_canvas
        try:
            # 检查widget是否在right_frame及其子元素中
            current_widget = widget
            while current_widget:
                if current_widget == self.ui.right_frame:
                    # 是右侧区域，滚动examples_canvas
                    self._handle_scroll(event, self.ui.examples_canvas)
                    return "break"  # 阻止事件继续传播
                elif current_widget == self.ui.left_frame:
                    # 是左侧区域，滚动results_canvas
                    self._handle_scroll(event, self.ui.results_canvas)
                    return "break"  # 阻止事件继续传播
                # 继续向上查找父组件
                current_widget = current_widget.master
        except Exception:
            # 如果出现异常，使用备选方案
            pass
        
        # 备选方案：使用_is_widget_inside方法
        if self._is_widget_inside(widget, self.ui.examples_canvas):
            self._handle_scroll(event, self.ui.examples_canvas)
            return "break"  # 阻止事件继续传播
        elif self._is_widget_inside(widget, self.ui.results_canvas):
            self._handle_scroll(event, self.ui.results_canvas)
            return "break"  # 阻止事件继续传播

    def _is_widget_inside(self, widget: tk.Widget, container: tk.Canvas) -> bool:
        """检查widget是否在container Canvas内，处理嵌套widget情况"""
        if widget == container:
            return True
        
        try:
            # 获取container的根坐标和尺寸
            container_x = container.winfo_rootx()
            container_y = container.winfo_rooty()
            container_width = container.winfo_width()
            container_height = container.winfo_height()
            container_x2 = container_x + container_width
            container_y2 = container_y + container_height
            
            # 检查widget的根坐标是否在container内
            widget_x = widget.winfo_rootx()
            widget_y = widget.winfo_rooty()
            widget_width = widget.winfo_width()
            widget_height = widget.winfo_height()
            widget_x2 = widget_x + widget_width
            widget_y2 = widget_y + widget_height
            
            # 检查两个矩形是否有重叠
            if (widget_x2 < container_x or widget_x > container_x2 or
                widget_y2 < container_y or widget_y > container_y2):
                return False
            
            # 遍历widget的父元素链，检查是否与container相关
            current = widget
            while current.master:
                if current.master == container or current.master.winfo_parent() == container.winfo_id():
                    return True
                current = current.master
            
            # 特殊处理Canvas内的Frame容器
            if hasattr(container, 'winfo_children'):
                for child in container.winfo_children():
                    if isinstance(child, tk.Frame) and self._is_widget_inside(widget, child):
                        return True
            
            return True
        except Exception:
            return False

    def _handle_scroll(self, event: tk.Event, canvas: tk.Canvas) -> str:
        delta = -event.delta if sys.platform == 'darwin' else event.delta
        if delta:
            canvas.yview_scroll(int(-1 * (delta / 120)), "units")
        else:
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
        return "break"

    def search_word(self) -> None:
        try:
            query = self.ui.query_entry.get().strip()
            if not query:
                messagebox.showinfo("提示", "请输入要查询的单词")
                return
            
            # 新增：获取精确查找复选框状态
            is_exact_match = self.ui.exact_match_var.get()
            self.current_word = query
            self.ui.clear_results()
            
            # 只在必要时创建或重新连接数据库
            if not self.db_handler:
                self.db_handler = DatabaseHandler(Config.CURRENT_DB)
            self.db_handler.connect()
            
            # 新增：传递精确匹配状态到搜索方法
            alice_res, chinese_res = self.db_handler.search_words(query, is_exact_match)
            found = False
            
            # 批量添加结果，减少UI更新次数
            if alice_res:
                self.ui.add_result_section("爱丽丝语 -> 中文:")
                for idx, (word, exp) in enumerate(alice_res):
                    self.ui.add_result_entry(word, exp, "alice", idx)
                found = True
            
            if chinese_res:
                self.ui.add_result_section("中文 -> 爱丽丝语:")
                for idx, (word, exp) in enumerate(chinese_res):
                    self.ui.add_result_entry(word, exp, "chinese", idx)
                found = True
            
            if not found:
                self.ui.add_no_results_message(query)
                self.ui.add_no_result_example_button(query)
            
            # 所有结果添加完成后，一次性更新UI和滚动区域
            self.ui.results_canvas.update_idletasks()
            self.ui.results_canvas.configure(scrollregion=self.ui.results_canvas.bbox("all"))
        except Exception as e:
            messagebox.showerror("错误", f"搜索时发生错误: {str(e)}")

    def start_show_examples(self, word: str) -> None:
        if self.is_processing or not word:
            return
        # 重置统计数据，避免残留旧数据
        self.current_matched_word = word
        self.current_song_stats = defaultdict(lambda: {'before': 0, 'after': 0})
        self.is_processing = True
        self.ui.progress_label.config(text="正在查找例句，请稍候...")
        self.root.update()
        self.ui.clear_examples()
        threading.Thread(target=self.process_examples, args=(word,), daemon=True).start()

    def process_examples(self, word: str) -> None:
        if not word:
            self.is_processing = False
            return
        
        try:
            # 重用主应用的数据库连接，避免创建新连接
            if not self.db_handler or not self.db_handler.conn:
                self.db_handler = DatabaseHandler(Config.CURRENT_DB)
                self.db_handler.connect()
            
            songs = self.db_handler.find_songs_with_word(word)
            # 处理例句并去重，过滤无效统计项
            self.current_examples, self.current_song_stats = self._process_and_deduplicate_examples(songs, word)
        except Exception as e:
            print(f"例句处理异常: {str(e)}")  # 调试用
            self.current_examples = []
            self.current_song_stats = defaultdict(lambda: {'before': 0, 'after': 0})
        finally:
            # 强制垃圾回收以释放内存
            import gc
            gc.collect()
            
        self.root.after(0, self.finish_show_examples)

    def _process_and_deduplicate_examples(self, songs: List[Tuple[str, str, str]], word: str) -> Tuple[List[Dict[str, str]], Dict[Tuple[str, str], Dict[str, int]]]:
        unique_examples = []
        seen_examples = set()
        song_stats = defaultdict(lambda: {'before': 0, 'after': 0})

        for title, lyric, album in songs:
            # 跳过空标题/专辑的无效歌曲
            if not title or not album:
                continue
            
            # 优化：提前strip字符串，避免重复strip
            stripped_album = album.strip()
            stripped_title = title.strip()
            song_key = (stripped_album, stripped_title)
            
            # 提取有效例句（含目标单词的段落）
            raw_paragraphs = TextProcessor.extract_valid_examples(lyric, word)
            before_count = len(raw_paragraphs)
            
            # 过滤：无原始例句的歌曲不加入统计
            if before_count == 0:
                continue
            
            after_count = 0
            # 去重并收集有效例句
            for para in raw_paragraphs:
                normalized_para = TextProcessor.normalize_text(para)
                # 用（标准化段落+专辑+标题）作为唯一标识，避免不同歌曲的相同段落被误判为重复
                example_id = (normalized_para, stripped_album, stripped_title)
                if example_id not in seen_examples:
                    seen_examples.add(example_id)
                    unique_examples.append({
                        'paragraph': para,
                        'title': stripped_title,
                        'album': stripped_album,
                        'lyric': lyric
                    })
                    after_count += 1
            
            # 记录有效统计（仅含原始例句数>0的歌曲）
            song_stats[song_key]['before'] = before_count
            song_stats[song_key]['after'] = after_count

        return unique_examples, song_stats

    def finish_show_examples(self) -> None:
        self.ui.progress_label.config(text="")
        self.is_processing = False
        
        if not self.current_examples:
            self.ui.add_no_examples_message(self.current_matched_word)
            # 清空统计数据，避免后续显示无效信息
            self.current_song_stats = defaultdict(lambda: {'before': 0, 'after': 0})
            # 更新滚动区域
            self.ui.examples_canvas.update_idletasks()
            self.ui.examples_canvas.configure(scrollregion=self.ui.examples_canvas.bbox("all"))
        else:
            # 批量添加所有例句
            self.ui.add_examples_header(len(self.current_examples))
            for idx, example in enumerate(self.current_examples):
                self.ui.add_example_entry(example, idx, self.current_matched_word)
            
            # 所有例句添加完成后，一次性更新UI和滚动区域
            self.ui.examples_canvas.update_idletasks()
            self.ui.examples_canvas.configure(scrollregion=self.ui.examples_canvas.bbox("all"))

    def show_full_lyric(self, initial_index: int, title: str, album: str, lyric: str, target_paragraph: str) -> None:
        search_word = self.current_matched_word
        all_examples = self.current_examples
        song_stats = self.current_song_stats.copy()  # 避免线程数据冲突
        
        # 基础校验
        if not all_examples or not song_stats or initial_index >= len(all_examples):
            messagebox.showinfo("提示", "没有找到相关例句")
            return
        
        # 创建歌词浏览窗口
        lyric_window = tk.Toplevel(self.root)
        lyric_window.title(f"例句浏览 - {search_word}")
        lyric_window.geometry("800x600")
        lyric_window.minsize(600, 500)
        
        # 1. 例句来源统计区域
        sources_frame = ttk.LabelFrame(lyric_window, text="例句来源统计", padding="5")
        sources_frame.pack(fill=tk.X, padx=10, pady=5)
        sources_text = scrolledtext.ScrolledText(
            sources_frame, 
            wrap=tk.WORD, 
            height=Config.SOURCES_BOX_HEIGHT, 
            font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE)
        )
        sources_text.pack(fill=tk.X, expand=False, padx=5, pady=5)
        
        # 计算有效统计（过滤before=0的无效项）
        valid_stats = {k: v for k, v in song_stats.items() if v['before'] > 0}
        total_before = sum(v['before'] for v in valid_stats.values())
        total_after = len(all_examples)
        
        # 写入统计信息
        sources_text.insert(tk.END, f"单词 '{search_word}' 例句统计：\n")
        sources_text.insert(tk.END, f"• 总数量（查重前）：{total_before} 个\n")
        sources_text.insert(tk.END, f"• 总数量（查重后）：{total_after} 个\n")
        
        # 计算去重率（避免除以零）
        if total_before > 0:
            deduplication_rate = ((total_before - total_after) / total_before) * 100
            sources_text.insert(tk.END, f"• 去重率：{deduplication_rate:.1f}%\n\n")
        else:
            sources_text.insert(tk.END, "• 去重率：0.0%\n\n")
        
        # 写入各歌曲统计（仅显示有效项）
        sources_text.insert(tk.END, "各歌曲例句分布（查重前/后）：\n")
        if valid_stats:
            for (alb, tit), stats in sorted(valid_stats.items()):
                sources_text.insert(tk.END, f"• {alb} - {tit}：查重前 {stats['before']} 个，查重后 {stats['after']} 个\n")
        else:
            sources_text.insert(tk.END, "• 无有效例句来源\n")
        
        sources_text.config(state=tk.DISABLED)
        
        # 2. 歌曲信息区域
        info_frame = ttk.Frame(lyric_window, padding="5")
        info_frame.pack(fill=tk.X, padx=10)
        current_song_label = ttk.Label(
            info_frame, 
            text=f"当前歌曲：{album.strip()} - {title.strip()}", 
            font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "bold")
        )
        current_song_label.pack(anchor=tk.W)
        
        # 3. 导航按钮区域
        nav_frame = ttk.Frame(lyric_window, padding="5")
        nav_frame.pack(fill=tk.X, padx=10)
        
        status_var = tk.StringVar()
        status_var.set(f"当前例句 {initial_index + 1}/{len(all_examples)}（原始例句总数：{total_before}）")
        
        prev_btn = ttk.Button(nav_frame, text="上一句", state=tk.DISABLED if initial_index == 0 else tk.NORMAL)
        prev_btn.pack(side=tk.LEFT, padx=5)
        
        status_label = ttk.Label(nav_frame, textvariable=status_var)
        status_label.pack(side=tk.LEFT, padx=10)
        
        next_btn = ttk.Button(nav_frame, text="下一句", state=tk.DISABLED if initial_index == len(all_examples)-1 else tk.NORMAL)
        next_btn.pack(side=tk.LEFT, padx=5)
        
        # 4. 歌词显示区域
        lyric_text = scrolledtext.ScrolledText(
            lyric_window, 
            wrap=tk.WORD, 
            font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE), 
            state=tk.NORMAL
        )
        lyric_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        # 配置高亮标签
        lyric_text.tag_configure("current_highlight", background=Config.CURRENT_HIGHLIGHT_COLOR)
        lyric_text.tag_configure("word_highlight", background=Config.HIGHLIGHT_COLOR)
        
        current_index = initial_index

        def update_lyric_display(idx: int) -> None:
            nonlocal current_song_label
            if idx < 0 or idx >= len(all_examples):
                return
            
            current_example = all_examples[idx]
            curr_lyric = current_example['lyric']
            curr_para = current_example['paragraph']
            curr_alb = current_example['album']
            curr_tit = current_example['title']
            
            # 更新歌曲信息
            current_song_label.config(text=f"当前歌曲：{curr_alb} - {curr_tit}")
            
            # 清空旧内容和标签
            lyric_text.tag_remove("current_highlight", 1.0, tk.END)
            lyric_text.tag_remove("word_highlight", 1.0, tk.END)
            lyric_text.config(state=tk.NORMAL)
            lyric_text.delete(1.0, tk.END)
            lyric_text.insert(tk.END, curr_lyric)
            lyric_text.config(state=tk.DISABLED)
            
            # 高亮当前段落和目标单词
            start_pos, end_pos = TextProcessor.find_paragraph_positions(curr_lyric, curr_para)
            if start_pos >= 0 and end_pos > start_pos:
                # 高亮当前段落
                lyric_text.tag_add("current_highlight", f"1.0 + {start_pos} chars", f"1.0 + {end_pos} chars")
                # 高亮目标单词
                TextProcessor.highlight_text(lyric_text, curr_lyric, search_word)
                
                # 改进的文本跳转逻辑，使段落居中显示
                # 1. 先滚动到段落起始位置
                lyric_text.see(f"1.0 + {start_pos} chars")
                # 2. 计算段落高度并调整位置使其尽量居中
                lyric_text.tag_add("scroll_target", f"1.0 + {start_pos} chars")
                try:
                    # 获取可见行数
                    visible_lines = int(lyric_text.winfo_height() / lyric_text.dlineinfo(1.0)[3])
                    # 滚动到段落位置，使段落尽量居中
                    line_start = lyric_text.index(f"1.0 + {start_pos} chars").split(".")[0]
                    mid_line = max(1, int(line_start) - visible_lines // 3)
                    lyric_text.see(f"{mid_line}.0")
                except Exception:
                    # 如果出现错误，回退到简单滚动
                    pass
            
            # 更新导航状态
            status_var.set(f"当前例句 {idx + 1}/{len(all_examples)}（原始例句总数：{total_before}）")
            prev_btn.config(state=tk.NORMAL if idx > 0 else tk.DISABLED)
            next_btn.config(state=tk.NORMAL if idx < len(all_examples)-1 else tk.DISABLED)

        def navigate_next() -> None:
            nonlocal current_index
            if current_index < len(all_examples) - 1:
                current_index += 1
                update_lyric_display(current_index)

        def navigate_prev() -> None:
            nonlocal current_index
            if current_index > 0:
                current_index -= 1
                update_lyric_display(current_index)

        # 绑定导航事件
        prev_btn.config(command=navigate_prev)
        next_btn.config(command=navigate_next)
        lyric_window.bind('<Right>', lambda e: navigate_next())
        lyric_window.bind('<Left>', lambda e: navigate_prev())
        
        # 初始显示
        update_lyric_display(initial_index)

    def on_close(self) -> None:
        # 停止可能正在进行的搜索
        self.is_processing = False
        
        # 移除所有事件绑定
        self._remove_event_bindings()
        
        # 关闭数据库连接
        if self.db_handler:
            self.db_handler.close()
            self.db_handler = None
        
        # 清空数据结构以释放内存
        self.current_examples.clear()
        self.current_song_stats.clear()
        
        # 清空正则表达式缓存
        if hasattr(TextProcessor, '_compiled_patterns'):
            TextProcessor._compiled_patterns.clear()
        
        # 强制垃圾回收
        import gc
        gc.collect()
        
        # 关闭主窗口
        self.root.destroy()
    
    def _remove_event_bindings(self):
        """移除所有事件绑定，避免内存泄漏"""
        # 移除canvas上的鼠标滚轮事件绑定
        if hasattr(self.ui, '_mouse_wheel_bindings'):
            for widget, event, binding_id in self.ui._mouse_wheel_bindings:
                try:
                    widget.unbind(event, funcid=binding_id)
                except:
                    pass
            self.ui._mouse_wheel_bindings.clear()
        
        # 移除查询框的回车绑定
        if hasattr(self.ui, 'query_entry'):
            try:
                self.ui.query_entry.unbind('<Return>')
            except:
                pass
        
        # 移除主窗口的关闭协议
        try:
            self.root.protocol("WM_DELETE_WINDOW", None)
        except:
            pass


if __name__ == "__main__":
    # 新增：确保中文显示正常
    root = tk.Tk()
    app = AliceDictionaryApp(root)
    root.mainloop()
