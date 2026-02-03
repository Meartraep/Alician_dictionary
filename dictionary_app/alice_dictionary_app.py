# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
import tkinter as tk
from tkinter import messagebox, ttk, scrolledtext
from collections import defaultdict
from typing import List, Dict, Tuple
import sys
import os
import threading

# 添加当前文件所在目录到sys.path，确保能正确导入同目录下的模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from database_handler import DatabaseHandler
from text_processor import TextProcessor
from ui_builder import UIBuilder
from history_manager import HistoryManager


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
        
        # 初始化历史记录管理器
        self.history_manager = HistoryManager()
        
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
            
            found = False
            
            # 新增：检查是否为词组（被空格分隔的两个或多个单词）
            import re
            is_phrase = re.match(r'^\w+(\s+\w+)+$', query) is not None
            
            # 批量添加结果，减少UI更新次数
            if is_phrase:
                # 查询词组
                phrase_res = self.db_handler.search_phrases(query, is_exact_match)
                if phrase_res:
                    self.ui.add_result_section("爱丽丝语词组 -> 中文:")
                    for idx, (phrase, exp) in enumerate(phrase_res):
                        # 获取词组词频和泛度数据
                        stats = self.db_handler.get_phrase_stats(phrase, is_exact_match)
                        count, variety = stats if stats else (0, 0)
                        # 使用空字符串作为word_class，保持与单词查询结果的一致性
                        self.ui.add_result_entry(phrase, exp, "", "alice", idx, count, variety)
                    found = True
            else:
                # 新增：传递精确匹配状态到搜索方法
                alice_res, chinese_res = self.db_handler.search_words(query, is_exact_match)
                
                if alice_res:
                    self.ui.add_result_section("爱丽丝语 -> 中文:")
                    for idx, (word, exp, word_class) in enumerate(alice_res):
                        # 获取单词词频和泛度数据
                        stats = self.db_handler.get_word_stats(word, is_exact_match)
                        count, variety = stats if stats else (0, 0)
                        self.ui.add_result_entry(word, exp, word_class, "alice", idx, count, variety)
                    found = True
                
                if chinese_res:
                    self.ui.add_result_section("中文 -> 爱丽丝语:")
                    for idx, (word, exp, word_class) in enumerate(chinese_res):
                        # 获取单词词频和泛度数据
                        stats = self.db_handler.get_word_stats(word, is_exact_match)
                        count, variety = stats if stats else (0, 0)
                        self.ui.add_result_entry(word, exp, word_class, "chinese", idx, count, variety)
                    found = True
            
            if not found:
                self.ui.add_no_results_message(query)
                self.ui.add_no_result_example_button(query)
        
            # 所有结果添加完成后，一次性更新UI和滚动区域
            self.ui.results_canvas.update_idletasks()
            self.ui.results_canvas.configure(scrollregion=self.ui.results_canvas.bbox("all"))
        
            # 添加到搜索历史记录
            self.history_manager.add_record(query)
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
