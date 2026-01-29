import re
import tkinter as tk
from tkinter import Menu, messagebox, scrolledtext, ttk
from collections import defaultdict
from typing import List, Dict, Tuple
import threading
import gc
import sys
import os

# 添加上级目录到路径，以便导入 dictionary_app 中的模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 尝试导入python-Levenshtein库，如果失败则使用difflib替代
try:
    from Levenshtein import ratio
    print("已加载python-Levenshtein库，使用该库进行单词匹配")
except ImportError:
    from difflib import SequenceMatcher
    # 实现与Levenshtein.ratio等效的函数
    def ratio(s1, s2):
        """计算两个字符串的相似度，返回值范围[0, 1]"""
        return SequenceMatcher(None, s1, s2).ratio()
    print("未安装python-Levenshtein库，使用difflib进行单词匹配")

from dictionary_app.text_processor import TextProcessor
from dictionary_app.config import Config

class ExplanationManager:
    """释义管理器，负责单词释义的获取和显示"""
    def __init__(self, root, text_area, config_manager, db_manager):
        self.root = root
        self.text_area = text_area
        self.config_manager = config_manager
        self.db_manager = db_manager
        
        # 右键菜单
        self.right_click_menu = None
        self.setup_right_click_menu()
        
        # 例句相关属性
        self.current_word = ""
        self.current_matched_word = ""
        self.current_examples: List[Dict[str, str]] = []
        self.current_song_stats = defaultdict(lambda: {'before': 0, 'after': 0})
        self.is_processing = False
        self.examples_window = None
    
    def setup_right_click_menu(self):
        """设置右键菜单"""
        self.right_click_menu = Menu(self.root, tearoff=0)
        self.right_click_menu.add_command(label="查看释义", command=self.show_explanations)
        self.text_area.bind("<Button-3>", self.show_right_click_menu)
    
    def show_right_click_menu(self, event):
        """显示右键菜单"""
        try:
            selected_text = self.text_area.get("sel.first", "sel.last")
            if selected_text.strip():
                self.right_click_menu.post(event.x_root, event.y_root)
        except Exception:
            pass
    
    def show_explanations(self):
        """显示选中单词的释义"""
        try:
            selected_text = self.text_area.get("sel.first", "sel.last")
            if not selected_text.strip():
                messagebox.showinfo("提示", "未找到可查询的内容")
                return
            explanations, similar_words = self.get_word_explanations(selected_text)
            self.create_explanation_window(explanations, similar_words)
        except Exception as e:
            messagebox.showerror("错误", f"获取释义失败: {str(e)}")
    
    def get_word_explanations(self, selected_text):
        """从数据库获取单词或词组的释义，优先匹配词组"""
        explanations = {}
        similar_words = {}
        try:
            # 使用数据库连接管理器获取连接
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            # 1. 查询所有词组，按长度降序排列
            cursor.execute("SELECT PHRASE FROM phrase")
            all_phrases = [row[0] for row in cursor.fetchall()]
            # 按长度降序排序，优先匹配较长的词组
            all_phrases.sort(key=lambda x: len(x), reverse=True)
            
            # 2. 查询所有单词
            cursor.execute("SELECT words FROM dictionary")
            all_words = [row[0] for row in cursor.fetchall()]
            
            # 3. 处理词组匹配
            remaining_text = selected_text
            matched_phrases = []
            
            # 遍历所有词组，尝试匹配
            for phrase in all_phrases:
                if phrase in remaining_text:
                    # 记录匹配到的词组
                    matched_phrases.append(phrase)
                    # 从剩余文本中标记已匹配的词组
                    remaining_text = remaining_text.replace(phrase, " ")
            
            # 4. 查询匹配到的词组释义
            for phrase in matched_phrases:
                if self.config_manager.get("strict_case"):
                    cursor.execute("SELECT explanation FROM phrase WHERE PHRASE = ?", (phrase,))
                else:
                    cursor.execute("SELECT explanation FROM phrase WHERE LOWER(PHRASE) = LOWER(?)", (phrase,))
                result = cursor.fetchone()
                
                if result:
                    explanations[phrase] = result[0]
                else:
                    explanations[phrase] = "未找到释义"
            
            # 5. 处理剩余的独立单词
            remaining_words = re.findall(r"\b\w+\b", remaining_text)
            for word in remaining_words:
                if word.strip():
                    # 查询当前单词的释义
                    if self.config_manager.get("strict_case"):
                        cursor.execute("SELECT explanation FROM dictionary WHERE words = ?", (word,))
                    else:
                        cursor.execute("SELECT explanation FROM dictionary WHERE LOWER(words) = LOWER(?)", (word,))
                    result = cursor.fetchone()
                    
                    if result:
                        explanations[word] = result[0]
                    else:
                        explanations[word] = "未找到释义"
                        
                        # 进行模糊匹配，找到最相似的单词
                        best_match = None
                        best_score = 0.0
                        
                        for dict_word in all_words:
                            if self.config_manager.get("strict_case"):
                                score = ratio(word, dict_word)
                            else:
                                score = ratio(word.lower(), dict_word.lower())
                            
                            if score > best_score and score > 0.6:  # 设置相似度阈值为0.6
                                best_score = score
                                best_match = dict_word
                        
                        if best_match:
                            # 获取相似单词的释义
                            if self.config_manager.get("strict_case"):
                                cursor.execute("SELECT explanation FROM dictionary WHERE words = ?", (best_match,))
                            else:
                                cursor.execute("SELECT explanation FROM dictionary WHERE LOWER(words) = LOWER(?)", (best_match,))
                            similar_result = cursor.fetchone()
                            
                            if similar_result:
                                similar_words[word] = {
                                    "similar_word": best_match,
                                    "explanation": similar_result[0],
                                    "score": best_score
                                }
            
            # 如果没有匹配到任何词组或单词，尝试将整个选择文本作为单词查询
            if not explanations:
                full_text_word = selected_text.strip()
                if full_text_word:
                    if self.config_manager.get("strict_case"):
                        cursor.execute("SELECT explanation FROM dictionary WHERE words = ?", (full_text_word,))
                    else:
                        cursor.execute("SELECT explanation FROM dictionary WHERE LOWER(words) = LOWER(?)", (full_text_word,))
                    result = cursor.fetchone()
                    
                    if result:
                        explanations[full_text_word] = result[0]
                    else:
                        explanations[full_text_word] = "未找到释义"
            
            return explanations, similar_words
        except Exception as e:
            print(f"数据库查询错误: {e}")
            raise Exception(f"数据库错误: {str(e)}")
    
    def create_explanation_window(self, explanations, similar_words):
        """创建显示释义的窗口，包含相似单词建议"""
        # 创建顶层窗口
        window = tk.Toplevel(self.root)
        window.title("单词释义")
        window.geometry("800x600")
        window.transient(self.root)
        
        # 设置窗口关闭时的清理函数
        window.protocol("WM_DELETE_WINDOW", lambda: self._cleanup_window(window))
        
        # 创建滚动区域
        main_frame = ttk.Frame(window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(main_frame)
        scrollbar_y = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollbar_x = ttk.Scrollbar(main_frame, orient="horizontal", command=canvas.xview)
        content_frame = ttk.Frame(canvas)
        
        content_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 为每个单词创建带按钮的框架
        for word, explanation in explanations.items():
            word_frame = ttk.LabelFrame(content_frame, text=f"【{word}】", padding="10")
            word_frame.pack(fill=tk.X, padx=5, pady=5, expand=False)
            
            # 释义文本
            exp_text = scrolledtext.ScrolledText(
                word_frame, wrap=tk.WORD, font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE),
                height=3, state=tk.NORMAL
            )
            exp_text.pack(fill=tk.X, padx=5, pady=5)
            exp_text.insert(tk.END, explanation)
            exp_text.config(state=tk.DISABLED)
            
            # 例句按钮（只有找到释义时才显示）
            if explanation != "未找到释义":
                btn_frame = ttk.Frame(word_frame)
                btn_frame.pack(anchor=tk.E, padx=5, pady=5)
                
                example_btn = ttk.Button(
                    btn_frame, 
                    text="查看例句和上下文", 
                    command=lambda w=word: self.start_show_examples(w)
                )
                example_btn.pack(side=tk.RIGHT)
            
            # 显示相似单词建议（如果有的话）
            if word in similar_words:
                similar_info = similar_words[word]
                similar_word = similar_info["similar_word"]
                similar_exp = similar_info["explanation"]
                score = similar_info["score"]
                
                # 相似单词框架
                similar_frame = ttk.LabelFrame(word_frame, text=f"相似单词建议 (相似度: {score:.2f})")
                similar_frame.pack(fill=tk.X, padx=5, pady=10, expand=False)
                
                # 相似单词标签
                similar_word_label = ttk.Label(
                    similar_frame, 
                    text=f"建议单词: {similar_word}", 
                    font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "bold")
                )
                similar_word_label.pack(anchor=tk.W, padx=5, pady=2)
                
                # 相似单词释义
                similar_exp_text = scrolledtext.ScrolledText(
                    similar_frame, 
                    wrap=tk.WORD, 
                    font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE),
                    height=3, 
                    state=tk.NORMAL
                )
                similar_exp_text.pack(fill=tk.X, padx=5, pady=5)
                similar_exp_text.insert(tk.END, similar_exp)
                similar_exp_text.config(state=tk.DISABLED)
                
                # 相似单词的例句按钮
                similar_btn_frame = ttk.Frame(similar_frame)
                similar_btn_frame.pack(anchor=tk.E, padx=5, pady=5)
                
                similar_example_btn = ttk.Button(
                    similar_btn_frame, 
                    text="查看例句和上下文", 
                    command=lambda w=similar_word: self.start_show_examples(w)
                )
                similar_example_btn.pack(side=tk.RIGHT)
        
        # 添加关闭按钮
        close_btn = ttk.Button(window, text="关闭", command=window.destroy)
        close_btn.pack(pady=10)
    
    def _cleanup_window(self, window):
        """清理窗口资源"""
        try:
            window.destroy()
        except Exception:
            pass
    
    def start_show_examples(self, word: str) -> None:
        """启动例句搜索"""
        if self.is_processing or not word:
            return
        # 重置统计数据，避免残留旧数据
        self.current_matched_word = word
        self.current_song_stats = defaultdict(lambda: {'before': 0, 'after': 0})
        self.is_processing = True
        
        # 创建例句窗口
        self._create_examples_window()
        self.examples_window.update()
        self._update_progress_label("正在查找例句，请稍候...")
        
        self.current_examples = []
        self._clear_examples_content()
        
        # 在后台线程中处理例句
        threading.Thread(target=self.process_examples, args=(word,), daemon=True).start()
    
    def process_examples(self, word: str) -> None:
        """在后台线程中处理例句"""
        if not word:
            self.is_processing = False
            return
        
        try:
            # 使用数据库连接管理器获取连接
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            # 查找包含该单词的歌曲
            cursor.execute("SELECT title, lyric, album FROM songs WHERE lyric LIKE ?", (f"%{word}%",))
            songs = cursor.fetchall()
            
            # 处理例句并去重，过滤无效统计项
            self.current_examples, self.current_song_stats = self._process_and_deduplicate_examples(songs, word)
        except Exception as e:
            print(f"例句处理异常: {str(e)}")  # 调试用
            self.current_examples = []
            self.current_song_stats = defaultdict(lambda: {'before': 0, 'after': 0})
        finally:
            # 强制垃圾回收以释放内存
            gc.collect()
            
        # 回到主线程更新UI
        self.root.after(0, self.finish_show_examples)
    
    def finish_show_examples(self) -> None:
        """完成例句显示"""
        self.is_processing = False
        self._update_progress_label("")
        
        if not self.examples_window or not self.examples_window.winfo_exists():
            return
        
        if not self.current_examples:
            self._add_no_examples_message(self.current_matched_word)
            # 清空统计数据，避免后续显示无效信息
            self.current_song_stats = defaultdict(lambda: {'before': 0, 'after': 0})
            # 更新滚动区域
            self._update_examples_scrollregion()
        else:
            # 批量添加所有例句
            self._add_examples_header(len(self.current_examples))
            for idx, example in enumerate(self.current_examples):
                self._add_example_entry(example, idx, self.current_matched_word)
            
            # 所有例句添加完成后，一次性更新UI和滚动区域
            self._update_examples_scrollregion()
    
    def _process_and_deduplicate_examples(self, songs: List[Tuple[str, str, str]], word: str) -> Tuple[List[Dict[str, str]], Dict[Tuple[str, str], Dict[str, int]]]:
        """处理和去重例句"""
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
    
    def _create_examples_window(self):
        """创建例句显示窗口"""
        if self.examples_window and self.examples_window.winfo_exists():
            self.examples_window.destroy()
        
        # 创建顶层窗口
        self.examples_window = tk.Toplevel(self.root)
        self.examples_window.title(f"例句和上下文 - {self.current_matched_word}")
        self.examples_window.geometry("800x600")
        self.examples_window.minsize(600, 500)
        
        # 窗口布局
        self._create_examples_ui()
        
        # 设置关闭事件
        self.examples_window.protocol("WM_DELETE_WINDOW", self._close_examples_window)
    
    def _create_examples_ui(self):
        """创建例句窗口UI"""
        # 主框架
        main_frame = ttk.Frame(self.examples_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 顶部标签
        top_label = ttk.Label(
            main_frame, 
            text=f"' {self.current_matched_word} ' 的例句和上下文",
            font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "bold")
        )
        top_label.pack(anchor=tk.W, pady=(0, 10))
        
        # 进度标签
        self.progress_label = ttk.Label(main_frame, text="", font=(Config.FONT_FAMILY, Config.LABEL_FONT_SIZE))
        self.progress_label.pack(anchor=tk.CENTER, pady=(0, 10))
        
        # 例句显示区域
        examples_frame = ttk.LabelFrame(main_frame, text="例句列表", padding="5")
        examples_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建带滚动条的画布
        canvas_frame = ttk.Frame(examples_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.examples_canvas = tk.Canvas(canvas_frame)
        self.examples_scrollbar_y = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.examples_canvas.yview)
        self.examples_scrollbar_x = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.examples_canvas.xview)
        self.examples_content = ttk.Frame(self.examples_canvas)
        
        # 配置Canvas滚动区域和滚动条
        self.examples_content.bind("<Configure>", lambda e: self.examples_canvas.configure(scrollregion=self.examples_canvas.bbox("all")))
        self.examples_canvas.create_window((0, 0), window=self.examples_content, anchor="nw")
        self.examples_canvas.configure(yscrollcommand=self.examples_scrollbar_y.set, xscrollcommand=self.examples_scrollbar_x.set)
        
        # 布局组件
        self.examples_canvas.grid(row=0, column=0, sticky="nsew")
        self.examples_scrollbar_y.grid(row=0, column=1, sticky="ns")
        self.examples_scrollbar_x.grid(row=1, column=0, sticky="ew")
        
        # 配置grid权重，使Canvas能自动扩展
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
    
    def _update_progress_label(self, text: str):
        """更新进度标签"""
        if hasattr(self, 'progress_label') and self.progress_label:
            self.progress_label.config(text=text)
            self.progress_label.update_idletasks()
    
    def _clear_examples_content(self):
        """清空例句内容"""
        if hasattr(self, 'examples_content') and self.examples_content:
            for widget in list(self.examples_content.winfo_children()):
                widget.destroy()
    
    def _add_examples_header(self, count: int):
        """添加例句标题"""
        header_label = ttk.Label(
            self.examples_content, 
            text=f"找到 {count} 个例句:", 
            font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "bold")
        )
        header_label.pack(anchor=tk.W, pady=(5, 5))
    
    def _add_example_entry(self, example: Dict[str, str], index: int, search_word: str):
        """添加例句条目"""
        frame = ttk.LabelFrame(self.examples_content, text=f"例句 {index + 1}", padding="5")
        frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 查看完整歌词按钮
        button = ttk.Button(
            frame, 
            text="查看完整歌词", 
            command=lambda idx=index, t=example['title'], a=example['album'], l=example['lyric'], p=example['paragraph']: 
                self.show_full_lyric(idx, t, a, l, p)
        )
        button.pack(anchor=tk.W, pady=(0, 2))
        
        # 来源标签
        source_label = ttk.Label(
            frame, 
            text=f"来源: {example['album']} - {example['title']}", 
            font=(Config.FONT_FAMILY, Config.LABEL_FONT_SIZE), 
            foreground=Config.INFO_COLOR
        )
        source_label.pack(anchor=tk.W, pady=(0, 5))
        
        # 例句文本
        text_widget = scrolledtext.ScrolledText(
            frame, 
            wrap=tk.WORD, 
            font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE)
        )
        text_widget.pack(fill=tk.X, expand=True)
        text_widget.insert(tk.END, example['paragraph'])
        TextProcessor.highlight_text(text_widget, example['paragraph'], search_word)
        
        # 设置文本框高度
        line_count = example['paragraph'].count('\n') + 1
        text_widget.configure(height=max(line_count, Config.EXAMPLE_MIN_HEIGHT), state=tk.DISABLED)
    
    def _add_no_examples_message(self, word: str):
        """添加无例句消息"""
        no_examples_label = ttk.Label(
            self.examples_content, 
            text=f"未找到包含 '{word}' 的例句", 
            font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE)
        )
        no_examples_label.pack(anchor=tk.CENTER, pady=20)
    
    def _update_examples_scrollregion(self):
        """更新例句滚动区域"""
        if hasattr(self, 'examples_canvas') and self.examples_canvas and hasattr(self, 'examples_content') and self.examples_content:
            self.examples_canvas.update_idletasks()
            self.examples_canvas.configure(scrollregion=self.examples_canvas.bbox("all"))
    
    def show_full_lyric(self, initial_index: int, title: str, album: str, lyric: str, target_paragraph: str) -> None:
        """显示完整歌词"""
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
    
    def _close_examples_window(self):
        """关闭例句窗口"""
        if hasattr(self, 'examples_window') and self.examples_window:
            try:
                self.examples_window.destroy()
            except Exception:
                pass
            self.examples_window = None
        
        # 清理资源
        self.current_examples.clear()
        self.current_song_stats.clear()
        self.is_processing = False
