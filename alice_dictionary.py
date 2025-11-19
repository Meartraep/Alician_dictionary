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


# 新增：获取资源文件路径的函数，用于支持打包
def get_resource_path(relative_path):
    """获取资源文件的绝对路径，支持开发环境和打包后的环境"""
    try:
        # PyInstaller 创建临时文件夹，并将路径存储在 _MEIPASS 中
        base_path = sys._MEIPASS
    except Exception:
        # 开发环境中使用当前文件所在目录
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)


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
    # 新增：使用资源路径函数获取数据库路径
    CURRENT_DB = get_resource_path(DB_NAME)


class DatabaseHandler:
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None

    def connect(self) -> bool:
        try:
            self.close()
            # 新增：检查数据库文件是否存在
            if not self.db_name.startswith(':memory:') and not os.path.exists(self.db_name):
                messagebox.showerror("数据库错误", f"数据库文件不存在: {self.db_name}")
                return False
            
            self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
            self.conn.execute("PRAGMA cache_size = -1000")
            self.conn.execute("PRAGMA synchronous = OFF")
            self.cursor = self.conn.cursor()
            return self._verify_database_structure()
        except sqlite3.Error as e:
            messagebox.showerror("数据库错误", f"连接数据库失败: {str(e)}")
            return False

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
    @staticmethod
    def normalize_text(text: str) -> str:
        if not text:
            return ""
        
        text = text.replace('\r\n', '\n').replace('\r', '\n').replace('\u3000', ' ').replace('\t', ' ').replace('\u00A0', ' ')
        lines = []
        for line in text.split('\n'):
            stripped = line.strip()
            lines.append(re.sub(r'\s+', ' ', stripped))
        
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        return '\n'.join(lines)

    @staticmethod
    def extract_valid_examples(lyric: str, search_word: str) -> List[str]:
        return TextProcessor.extract_all_valid_paragraphs(lyric, search_word)

    @staticmethod
    def extract_all_valid_paragraphs(lyric: str, search_word: Optional[str] = None) -> List[str]:
        lines = [line.rstrip('\r\n') for line in lyric.splitlines()]
        valid = []
        used = set()
        pattern = re.compile(r'\b' + re.escape(search_word) + r'\b', re.IGNORECASE) if search_word else None

        for i in range(len(lines)):
            if i in used:
                continue
            
            is_first = (i == 0)
            has_empty_above = is_first or (lines[i-1].strip() == "")
            has_empty_below = (i == len(lines)-1) or (lines[i+1].strip() == "")
            
            if is_first or (has_empty_above and has_empty_below):
                para_lines = []
                empty_cnt = 0
                j = i
                while j < len(lines) and empty_cnt < 2:
                    para_lines.append(lines[j])
                    used.add(j)
                    if lines[j].strip() == "":
                        empty_cnt += 1
                    j += 1
                
                raw = '\n'.join(para_lines)
                norm = raw.strip()
                if norm and (not pattern or pattern.search(norm)):
                    valid.append(raw)
        return valid

    @staticmethod
    def find_paragraph_positions(lyric: str, paragraph: str) -> Tuple[int, int]:
        if not lyric or not paragraph:
            return (0, 0)
        
        norm_lyric = [TextProcessor.normalize_text(line) for line in lyric.split('\n')]
        norm_para = [TextProcessor.normalize_text(line) for line in paragraph.split('\n')]
        para_len = len(norm_para)
        start_idx = -1

        for i in range(len(norm_lyric) - para_len + 1):
            match = True
            for j in range(para_len):
                if norm_lyric[i+j] != norm_para[j]:
                    match = False
                    break
            if match:
                start_idx = i
                break
        
        if start_idx == -1:
            return (0, min(len(paragraph), len(lyric)))
        
        start_pos = 0
        for i in range(start_idx):
            start_pos += len(lyric.split('\n')[i]) + 1
        
        end_pos = start_pos
        raw_lyric = lyric.split('\n')
        for j in range(para_len):
            end_pos += len(raw_lyric[start_idx + j]) + 1
        end_pos -= 1
        return (start_pos, end_pos)

    @staticmethod
    def highlight_text(text_widget: scrolledtext.ScrolledText, text: str, word: str) -> None:
        if not word:
            return
        
        text_widget.tag_remove("highlight", 1.0, tk.END)
        pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
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
        self.left_frame = ttk.Frame(self.main_frame, padding="5")
        self.right_frame = ttk.Frame(self.main_frame, padding="5")
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

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
        self.results_canvas = tk.Canvas(result_frame)
        self.results_scrollbar = ttk.Scrollbar(result_frame, orient="vertical", command=self.results_canvas.yview)
        self.results_container = ttk.Frame(self.results_canvas)
        
        self.results_container.bind("<Configure>", lambda e: self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all")))
        self.results_canvas.create_window((0, 0), window=self.results_container, anchor="nw")
        self.results_canvas.configure(yscrollcommand=self.results_scrollbar.set)
        
        for evt in ["<MouseWheel>", "<Button-4>", "<Button-5>"]:
            self.results_canvas.bind(evt, self.app.on_mouse_wheel)
        
        self.results_canvas.pack(side="left", fill="both", expand=True)
        self.results_scrollbar.pack(side="right", fill="y")

    def _create_examples_area(self) -> None:
        example_title_frame = ttk.Frame(self.right_frame)
        example_title_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(example_title_frame, text="例句:").pack(side=tk.LEFT)
        
        self.examples_frame = ttk.Frame(self.right_frame)
        self.examples_frame.pack(fill=tk.BOTH, expand=True)
        self.examples_canvas = tk.Canvas(self.examples_frame)
        self.examples_scrollbar = ttk.Scrollbar(self.examples_frame, orient="vertical", command=self.examples_canvas.yview)
        self.examples_content = ttk.Frame(self.examples_canvas)
        
        self.examples_content.bind("<Configure>", lambda e: self.examples_canvas.configure(scrollregion=self.examples_canvas.bbox("all")))
        self.examples_canvas.create_window((0, 0), window=self.examples_content, anchor="nw")
        self.examples_canvas.configure(yscrollcommand=self.examples_scrollbar.set)
        
        for evt in ["<MouseWheel>", "<Button-4>", "<Button-5>"]:
            self.examples_canvas.bind(evt, self.app.on_mouse_wheel)
            self.examples_frame.bind(evt, self.app.on_mouse_wheel)
        
        self.examples_canvas.pack(side="left", fill="both", expand=True)
        self.examples_scrollbar.pack(side="right", fill="y")
        
        self.progress_label = ttk.Label(self.right_frame, text="", font=(Config.FONT_FAMILY, Config.LABEL_FONT_SIZE))
        self.progress_label.pack(anchor=tk.CENTER, pady=(5, 0))

    def clear_results(self) -> None:
        for widget in self.results_container.winfo_children():
            widget.destroy()
        self.root.update_idletasks()

    def clear_examples(self) -> None:
        for widget in self.examples_content.winfo_children():
            widget.destroy()
        self.root.update_idletasks()

    def add_result_section(self, title: str) -> None:
        ttk.Label(self.results_container, text=title, font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "bold")).pack(anchor=tk.W, pady=(5, 2))
        self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all"))

    def add_result_entry(self, word: str, explanation: str, result_type: str, index: int) -> None:
        frame = ttk.Frame(self.results_container)
        frame.pack(fill=tk.X, padx=5, pady=3)
        
        word_frame = ttk.Frame(frame)
        word_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        if result_type == "alice":
            ttk.Label(word_frame, text=f"爱丽丝语: {word}", font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "bold")).pack(anchor=tk.W)
            ttk.Label(word_frame, text=f"中文翻译: {explanation}", wraplength=400).pack(anchor=tk.W)
        else:
            ttk.Label(word_frame, text=f"中文: {explanation}", font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "bold")).pack(anchor=tk.W)
            ttk.Label(word_frame, text=f"爱丽丝语: {word}", wraplength=400).pack(anchor=tk.W)
        
        ttk.Button(frame, text="查询例句", command=lambda w=word: self.app.start_show_examples(w)).pack(side=tk.RIGHT, padx=5)
        self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all"))
        self.root.update_idletasks()

    def add_no_results_message(self, query: str) -> None:
        ttk.Label(self.results_container, text=f"未找到 '{query}' 的翻译", font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE)).pack(anchor=tk.W, pady=5)
        self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all"))

    def add_no_result_example_button(self, query: str) -> None:
        btn_frame = ttk.Frame(self.results_container)
        btn_frame.pack(fill=tk.X, pady=(5, 10))
        ttk.Button(btn_frame, text=f"查询包含 '{query}' 的例句", command=lambda w=query: self.app.start_show_examples(w)).pack(anchor=tk.CENTER)
        self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all"))
        self.root.update_idletasks()

    def add_examples_header(self, count: int) -> None:
        ttk.Label(self.examples_content, text=f"找到 {count} 个例句:", font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "bold")).pack(anchor=tk.W, pady=(5, 5))
        self.examples_canvas.configure(scrollregion=self.examples_canvas.bbox("all"))

    def add_example_entry(self, example: Dict[str, str], index: int, search_word: str) -> None:
        frame = ttk.LabelFrame(self.examples_content, text=f"例句 {index + 1}", padding="5")
        frame.pack(fill=tk.X, padx=5, pady=5)
        for evt in ["<MouseWheel>", "<Button-4>", "<Button-5>"]:
            frame.bind(evt, self.app.on_mouse_wheel)
        
        ttk.Button(frame, text="查看完整歌词", command=lambda idx=index, t=example['title'], a=example['album'], l=example['lyric'], p=example['paragraph']: self.app.show_full_lyric(idx, t, a, l, p)).pack(anchor=tk.W, pady=(0, 2))
        ttk.Label(frame, text=f"来源: {example['album']} - {example['title']}", font=(Config.FONT_FAMILY, Config.LABEL_FONT_SIZE), foreground=Config.INFO_COLOR).pack(anchor=tk.W, pady=(0, 5))
        
        text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE))
        text_widget.pack(fill=tk.X, expand=True)
        text_widget.insert(tk.END, example['paragraph'])
        TextProcessor.highlight_text(text_widget, example['paragraph'], search_word)
        
        line_count = example['paragraph'].count('\n') + 1
        text_widget.configure(height=max(line_count, Config.EXAMPLE_MIN_HEIGHT), state=tk.DISABLED)
        
        def on_scroll(evt):
            self.app.on_mouse_wheel(evt)
            return "break"
        
        for evt in ["<MouseWheel>", "<Button-4>", "<Button-5>"]:
            text_widget.bind(evt, on_scroll)
        
        self.examples_canvas.configure(scrollregion=self.examples_canvas.bbox("all"))

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

    def on_mouse_wheel(self, event: tk.Event) -> None:
        x, y = event.x_root, event.y_root
        
        examples_widget = self.ui.examples_canvas.winfo_containing(x, y)
        in_examples = self._is_widget_inside(examples_widget, self.ui.examples_canvas) if examples_widget else False
        
        results_widget = self.ui.results_canvas.winfo_containing(x, y)
        in_results = self._is_widget_inside(results_widget, self.ui.results_canvas) if results_widget else False
        
        if in_examples:
            self._handle_scroll(event, self.ui.examples_canvas)
        elif in_results:
            self._handle_scroll(event, self.ui.results_canvas)

    def _is_widget_inside(self, widget: tk.Widget, container: tk.Canvas) -> bool:
        if widget == container:
            return True
        try:
            geom = widget.winfo_geometry().split('+')
            if len(geom) < 3:
                return False
            wx, wy = int(geom[1]), int(geom[2])
            cx1, cy1 = container.winfo_rootx(), container.winfo_rooty()
            cx2, cy2 = cx1 + container.winfo_width(), cy1 + container.winfo_height()
            return cx1 <= wx <= cx2 and cy1 <= wy <= cy2
        except Exception:
            return False

    def _handle_scroll(self, event: tk.Event, canvas: tk.Canvas) -> None:
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
            
            if not self.db_handler or not self.db_handler.conn:
                self.db_handler = DatabaseHandler(Config.CURRENT_DB)
                self.db_handler.connect()
            
            # 新增：传递精确匹配状态到搜索方法
            alice_res, chinese_res = self.db_handler.search_words(query, is_exact_match)
            found = False
            
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
            
            self.root.update_idletasks()
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
            thread_db = DatabaseHandler(Config.CURRENT_DB)
            if not thread_db.connect():
                return
            songs = thread_db.find_songs_with_word(word)
            thread_db.close()
            # 处理例句并去重，过滤无效统计项
            self.current_examples, self.current_song_stats = self._process_and_deduplicate_examples(songs, word)
        except Exception as e:
            print(f"例句处理异常: {str(e)}")  # 调试用
            self.current_examples = []
            self.current_song_stats = defaultdict(lambda: {'before': 0, 'after': 0})
        
        self.root.after(0, self.finish_show_examples)

    def _process_and_deduplicate_examples(self, songs: List[Tuple[str, str, str]], word: str) -> Tuple[List[Dict[str, str]], Dict[Tuple[str, str], Dict[str, int]]]:
        unique_examples = []
        seen_examples = set()
        song_stats = defaultdict(lambda: {'before': 0, 'after': 0})

        for title, lyric, album in songs:
            # 跳过空标题/专辑的无效歌曲
            if not title or not album:
                continue
            
            song_key = (album.strip(), title.strip())
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
                example_id = (normalized_para, album.strip(), title.strip())
                if example_id not in seen_examples:
                    seen_examples.add(example_id)
                    unique_examples.append({
                        'paragraph': para,
                        'title': title.strip(),
                        'album': album.strip(),
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
        else:
            self.ui.add_examples_header(len(self.current_examples))
            for idx, example in enumerate(self.current_examples):
                self.ui.add_example_entry(example, idx, self.current_matched_word)

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
        if self.db_handler:
            self.db_handler.close()
        self.root.destroy()


if __name__ == "__main__":
    # 新增：确保中文显示正常
    root = tk.Tk()
    app = AliceDictionaryApp(root)
    root.mainloop()
