import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import sqlite3
import re
import json
import os

class WordCheckerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("单词检查器")
        # 初始屏幕更大，不让侧边栏挤压文本区
        self.root.geometry("1000x700")
        
        # 配置相关
        self.config_file = "word_checker_config.json"
        self.load_config()
        
        # 数据库相关初始化
        self.known_words = set()
        # 缓存单词的 count 和 variety 字段（用于蓝色高亮判断）
        # key -> (count:int, variety:int)
        self.word_stats = {}
        
        # 撤销功能初始化
        self.undo_stack = []
        self.max_undo_steps = self.config["max_undo_steps"]
        self.is_undoing = False
        
        # 新增：当前打开的文件路径（用于保存）
        self.current_file_path = None
        
        # 存放当前被高亮的单词信息（按首出现位置记录）
        # key_for_map -> {'display': str, 'pos': int, 'type': 'unknown'/'lowstat', 'reasons': set(...) }
        self.highlighted_map = {}
        
        # 创建GUI组件，加载数据库
        self.create_widgets()
        self.load_known_words()
        
        # 绑定事件：原有事件 + 新增文件操作快捷键
        self.check_delay = None
        self.text_area.bind("<KeyRelease>", self.schedule_check)
        self.text_area.bind("<<Paste>>", lambda e: self.root.after(100, self.schedule_check))
        self.text_area.bind("<<Modified>>", self.push_undo_state)
        self.root.bind("<Control-z>", self.undo)
        self.root.bind("<Control-s>", self.save_file)  # Ctrl+S保存绑定
        
        # 设置右键菜单
        self.setup_right_click_menu()
    
    def load_config(self):
        """加载配置文件"""
        default_config = {"strict_case": True, "max_undo_steps": 100}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                if "strict_case" not in self.config:
                    self.config["strict_case"] = default_config["strict_case"]
                if "max_undo_steps" not in self.config:
                    self.config["max_undo_steps"] = default_config["max_undo_steps"]
            except (json.JSONDecodeError, Exception) as e:
                print(f"加载配置失败: {e}，使用默认配置")
                self.config = default_config
        else:
            self.config = default_config
    
    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False
    
    def create_widgets(self):
        """创建GUI组件（包含侧边栏）"""
        # 顶部按钮区域
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(top_frame, text="请输入文本（单词之间用空格分隔）：").pack(side=tk.LEFT)
        ttk.Button(top_frame, text="打开TXT", command=self.open_txt_file).pack(side=tk.RIGHT, padx=5)
        ttk.Button(top_frame, text="保存文件", command=self.save_file).pack(side=tk.RIGHT, padx=5)
        ttk.Button(top_frame, text="撤销", command=self.undo).pack(side=tk.RIGHT, padx=5)
        ttk.Button(top_frame, text="设置", command=self.open_settings).pack(side=tk.RIGHT)
        
        # 主体区域：左为文本，右为侧边栏（固定宽度，不压缩主文本区）
        body_frame = ttk.Frame(self.root)
        body_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 文本区放在 left_frame 中，允许 expand
        left_frame = ttk.Frame(body_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.text_area = scrolledtext.ScrolledText(
            left_frame, wrap=tk.WORD, width=80, height=30, font=("SimHei", 12)
        )
        self.text_area.pack(fill=tk.BOTH, expand=True)
        
        # 侧边栏（固定宽度）
        sidebar_frame = ttk.Frame(body_frame, width=260)
        sidebar_frame.pack(side=tk.RIGHT, fill=tk.Y)
        sidebar_frame.pack_propagate(False)  # 不让内部控件改变外框宽度
        
        ttk.Label(sidebar_frame, text="高亮单词列表（红色优先）").pack(anchor="w", pady=(0,5), padx=5)
        
        # 使用 Treeview 以便为每行设置颜色 tag
        self.sidebar_tree = ttk.Treeview(sidebar_frame, show="tree", selectmode="browse")
        # 配置标签颜色
        self.sidebar_tree.tag_configure("unknown", foreground="red")
        self.sidebar_tree.tag_configure("lowstat", foreground="blue")
        
        # 滚动条
        sidebar_scroll = ttk.Scrollbar(sidebar_frame, orient=tk.VERTICAL, command=self.sidebar_tree.yview)
        self.sidebar_tree.configure(yscrollcommand=sidebar_scroll.set)
        sidebar_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.sidebar_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0))
        
        # 绑定单击（选择）与双击事件
        self.sidebar_tree.bind("<<TreeviewSelect>>", self.on_sidebar_select)  # 单击选择触发（显示问题窗口）
        self.sidebar_tree.bind("<Double-1>", self.on_sidebar_double_click)  # 双击跳转
        
        self.status_label = ttk.Label(self.root, text="状态：初始化中...")
        self.status_label.pack(pady=5, anchor="w", padx=10)
        
        # 现有：未知单词红色标记
        self.text_area.tag_config("unknown", foreground="red")
        # 新增：低统计（count 或 variety < 3）蓝色高亮
        self.text_area.tag_config("lowstat", foreground="blue")
    
    # ---------------------- 打开/保存/设置 ----------------------
    def open_txt_file(self):
        """打开选择的TXT文件，显示内容并自动检查"""
        file_path = filedialog.askopenfilename(
            title="选择TXT文件",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialdir=os.getcwd()
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except Exception as e:
                messagebox.showerror("错误", f"文件编码不支持：{str(e)}")
                return
        except Exception as e:
            messagebox.showerror("错误", f"打开文件失败：{str(e)}")
            return
        
        self.current_file_path = file_path
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", content)
        self.push_undo_state()
        self.check_words()
        file_name = os.path.basename(file_path)
        self.status_label.config(text=f"状态：已打开文件 - {file_name}")
    
    def save_file(self, event=None):
        """保存当前文本到文件（优先保存到已打开路径，无路径则让用户选择）"""
        if not self.current_file_path:
            save_path = filedialog.asksaveasfilename(
                title="保存文件",
                defaultextension=".txt",
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
                initialdir=os.getcwd()
            )
            if not save_path:
                return
            self.current_file_path = save_path
        
        try:
            content = self.text_area.get("1.0", tk.END)
            with open(self.current_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            file_name = os.path.basename(self.current_file_path)
            self.status_label.config(text=f"状态：已保存文件 - {file_name}")
            messagebox.showinfo("提示", f"文件已保存到：\n{self.current_file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"保存文件失败：{str(e)}")
    
    def open_settings(self):
        """打开设置窗口"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("设置")
        settings_window.geometry("350x200")
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        case_frame = ttk.Frame(settings_window)
        case_frame.pack(fill=tk.X, padx=20, pady=15)
        
        self.case_var = tk.BooleanVar(value=self.config["strict_case"])
        case_check = ttk.Checkbutton(
            case_frame, 
            text="严格匹配大小写", 
            variable=self.case_var
        )
        case_check.pack(anchor=tk.W)
        
        undo_frame = ttk.Frame(settings_window)
        undo_frame.pack(fill=tk.X, padx=20, pady=5)
        
        ttk.Label(undo_frame, text="最大撤销步数（1-1000）：").pack(side=tk.LEFT)
        self.undo_steps_var = tk.IntVar(value=self.config["max_undo_steps"])
        undo_spin = ttk.Spinbox(
            undo_frame,
            from_=1,
            to=1000,
            textvariable=self.undo_steps_var,
            width=6
        )
        undo_spin.pack(side=tk.LEFT, padx=10)
        
        btn_frame = ttk.Frame(settings_window)
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Button(btn_frame, text="确定", command=lambda: self.save_settings(settings_window)).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=settings_window.destroy).pack(side=tk.RIGHT, padx=5)
    
    def save_settings(self, window):
        """保存设置并关闭窗口"""
        new_strict_case = self.case_var.get()
        if new_strict_case != self.config["strict_case"]:
            self.config["strict_case"] = new_strict_case
            self.known_words.clear()
            self.word_stats.clear()
            self.load_known_words()
            self.check_words()
        
        new_undo_steps = self.undo_steps_var.get()
        if new_undo_steps != self.config["max_undo_steps"]:
            self.config["max_undo_steps"] = new_undo_steps
            self.max_undo_steps = new_undo_steps
            if len(self.undo_stack) > new_undo_steps:
                self.undo_stack = self.undo_stack[-new_undo_steps:]
        
        if self.save_config():
            messagebox.showinfo("提示", "设置已保存")
        else:
            messagebox.showerror("错误", "保存设置失败")
        
        window.destroy()
    
    # ---------------------- 右键菜单与释义 ----------------------
    def setup_right_click_menu(self):
        """设置右键菜单"""
        self.right_click_menu = tk.Menu(self.root, tearoff=0)
        self.right_click_menu.add_command(label="查看释义", command=self.show_explanations)
        self.text_area.bind("<Button-3>", self.show_right_click_menu)
    
    def show_right_click_menu(self, event):
        """显示右键菜单"""
        try:
            selected_text = self.text_area.get("sel.first", "sel.last")
            if selected_text.strip():
                self.right_click_menu.post(event.x_root, event.y_root)
        except tk.TclError:
            pass
    
    def show_explanations(self):
        """显示选中单词的释义"""
        try:
            selected_text = self.text_area.get("sel.first", "sel.last")
            words = re.findall(r"\b\w+\b", selected_text)
            if not words:
                messagebox.showinfo("提示", "未找到可查询的单词")
                return
            explanations = self.get_word_explanations(words)
            self.create_explanation_window(explanations)
        except tk.TclError:
            messagebox.showinfo("提示", "请先选中单词")
        except Exception as e:
            messagebox.showerror("错误", f"获取释义失败: {str(e)}")
    
    def get_word_explanations(self, words):
        """从数据库获取单词的释义"""
        explanations = {}
        try:
            conn = sqlite3.connect("translated.db")
            cursor = conn.cursor()
            for word in words:
                if self.config["strict_case"]:
                    cursor.execute("SELECT explanation FROM dictionary WHERE words = ?", (word,))
                else:
                    cursor.execute("SELECT explanation FROM dictionary WHERE LOWER(words) = LOWER(?)", (word,))
                result = cursor.fetchone()
                explanations[word] = result[0] if result else "未找到释义"
            conn.close()
            return explanations
        except sqlite3.Error as e:
            print(f"数据库查询错误: {e}")
            raise Exception(f"数据库错误: {str(e)}")
    
    def create_explanation_window(self, explanations):
        """创建显示释义的窗口（与侧边栏问题窗口不同）"""
        window = tk.Toplevel(self.root)
        window.title("单词释义")
        window.geometry("600x400")
        window.transient(self.root)
        window.grab_set()
        
        text_frame = ttk.Frame(window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        explanation_text = scrolledtext.ScrolledText(
            text_frame, wrap=tk.WORD, font=("SimHei", 12),
            yscrollcommand=scrollbar.set
        )
        explanation_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=explanation_text.yview)
        
        for word, explanation in explanations.items():
            explanation_text.insert(tk.END, f"【{word}】\n", "word")
            explanation_text.insert(tk.END, f"{explanation}\n\n", "explanation")
        
        explanation_text.tag_config("word", font=("SimHei", 12, "bold"), foreground="#0066CC")
        explanation_text.tag_config("explanation", font=("SimHei", 12))
        explanation_text.config(state=tk.DISABLED)
        
        close_btn = ttk.Button(window, text="关闭", command=window.destroy)
        close_btn.pack(pady=10)
    
    # ---------------------- 读取已知单词与统计 ----------------------
    def load_known_words(self):
        """从数据库加载已知单词，并缓存 count/variety 字段"""
        try:
            conn = sqlite3.connect("translated.db")
            cursor = conn.cursor()
            cursor.execute("SELECT words, count, variety FROM dictionary")
            rows = cursor.fetchall()
            
            for row in rows:
                w = row[0]
                try:
                    c = int(row[1]) if row[1] is not None else 0
                except Exception:
                    c = 0
                try:
                    v = int(row[2]) if row[2] is not None else 0
                except Exception:
                    v = 0
                
                if self.config["strict_case"]:
                    self.known_words.add(w)
                    self.word_stats[w] = (c, v)
                else:
                    lw = w.lower()
                    self.known_words.add(lw)
                    self.word_stats[lw] = (c, v)
            
            conn.close()
            case_status = "严格区分大小写" if self.config["strict_case"] else "不区分大小写"
            self.status_label.config(text=f"状态：就绪 - 已加载 {len(self.known_words)} 个已知单词（{case_status}）")
        except sqlite3.Error as e:
            print(f"数据库错误: {e}")
            error_window = tk.Toplevel(self.root)
            error_window.title("数据库错误")
            error_label = tk.Label(error_window, text=f"无法加载数据库: {e}")
            error_label.pack(padx=20, pady=20)
            ok_button = tk.Button(error_window, text="确定", command=error_window.destroy)
            ok_button.pack(pady=10)
            self.status_label.config(text="状态：数据库加载失败")
    
    # ---------------------- 检查与高亮 ----------------------
    def schedule_check(self, event=None):
        """触发单词检查"""
        if self.check_delay:
            self.root.after_cancel(self.check_delay)
        self.check_delay = self.root.after(100, self.check_words)
    
    def check_words(self):
        """检查文本中的单词并高亮显示未知单词；同时对低统计单词标蓝；并更新侧边栏"""
        # 先移除已有高亮
        self.text_area.tag_remove("unknown", "1.0", tk.END)
        self.text_area.tag_remove("lowstat", "1.0", tk.END)
        
        # 清空当前高亮映射
        self.highlighted_map.clear()
        
        text = self.text_area.get("1.0", tk.END)
        
        if not text.strip():
            case_status = "严格区分大小写" if self.config["strict_case"] else "不区分大小写"
            self.status_label.config(text=f"状态：就绪 - 已加载 {len(self.known_words)} 个已知单词（{case_status}）")
            # 更新侧边栏为空
            self.update_sidebar()
            return
        
        pattern = r"\b[a-zA-Z]+\b"
        matches = re.finditer(pattern, text)
        unknown_count = 0
        
        for match in matches:
            word = match.group()
            start = match.start()
            end = match.end()
            
            start_pos = self.get_text_index(text, start)
            end_pos = self.get_text_index(text, end)
            
            # 根据大小写设置判断是否为已知单词
            if self.config["strict_case"]:
                is_known = word in self.known_words
                key_for_stats = word
                map_key = word  # 用于唯一标识侧栏项（与大小写设置一致）
            else:
                lw = word.lower()
                is_known = lw in self.known_words
                key_for_stats = lw
                map_key = lw
            
            if not is_known:
                # 未知单词：红色
                self.text_area.tag_add("unknown", start_pos, end_pos)
                unknown_count += 1
                # 若尚未记录该词，记录其首出现位置与显示文本
                if map_key not in self.highlighted_map:
                    self.highlighted_map[map_key] = {
                        'display': word,
                        'pos': start,
                        'type': 'unknown',
                        'reasons': set()
                    }
            else:
                # 已知但需检查统计信息
                stats = self.word_stats.get(key_for_stats)
                if stats:
                    c, v = stats
                    low_reasons = set()
                    try:
                        if c < 3:
                            low_reasons.add('count')
                        if v < 3:
                            low_reasons.add('variety')
                    except Exception:
                        pass
                    if low_reasons:
                        # 蓝色标记
                        self.text_area.tag_add("lowstat", start_pos, end_pos)
                        # 若尚未记录该词，记录首出现位置与显示文本
                        if map_key not in self.highlighted_map:
                            self.highlighted_map[map_key] = {
                                'display': word,
                                'pos': start,
                                'type': 'lowstat',
                                'reasons': low_reasons
                            }
                        else:
                            # 如果已经记录（应为已知或其它），确保类型与原因合并
                            existing = self.highlighted_map[map_key]
                            # 若之前是 unknown，保持 unknown（红优先）
                            if existing['type'] != 'unknown':
                                existing['type'] = 'lowstat'
                                existing['reasons'].update(low_reasons)
        
        case_status = "严格区分大小写" if self.config["strict_case"] else "不区分大小写"
        if self.current_file_path:
            file_name = os.path.basename(self.current_file_path)
            self.status_label.config(
                text=f"状态：已检查 - {file_name} - 未知单词: {unknown_count}个 - 已加载 {len(self.known_words)} 个已知单词（{case_status}）"
            )
        else:
            self.status_label.config(
                text=f"状态：已检查 - 未知单词: {unknown_count}个 - 已加载 {len(self.known_words)} 个已知单词（{case_status}）"
            )
        
        # 更新侧边栏内容
        self.update_sidebar()
    
    def update_sidebar(self):
        """根据 self.highlighted_map 更新侧边栏显示（红色优先，按出现顺序）"""
        # 清空现有 tree 项
        for item in self.sidebar_tree.get_children():
            self.sidebar_tree.delete(item)
        
        # Build two lists: unknowns and lowstats, ordered by pos
        unknowns = []
        lowstats = []
        for key, info in self.highlighted_map.items():
            if info['type'] == 'unknown':
                unknowns.append((info['pos'], key, info))
            else:
                lowstats.append((info['pos'], key, info))
        
        unknowns.sort(key=lambda x: x[0])
        lowstats.sort(key=lambda x: x[0])
        
        # Insert unknowns first, then lowstats
        for _, key, info in unknowns:
            display = info['display']
            self.sidebar_tree.insert('', 'end', iid=key, text=display, tags=('unknown',))
        for _, key, info in lowstats:
            display = info['display']
            # Ensure iid unique; key already unique per normalization
            self.sidebar_tree.insert('', 'end', iid=key, text=display, tags=('lowstat',))
    
    def on_sidebar_select(self, event):
        """单击侧边栏项目（选择）时弹出问题窗口，点击窗口外自动关闭"""
        sel = self.sidebar_tree.selection()
        if not sel:
            return
        key = sel[0]
        info = self.highlighted_map.get(key)
        if not info:
            return
        
        # 生成显示内容
        msgs = []
        if info['type'] == 'unknown':
            msgs.append("未知单词")
        else:
            # lowstat -> check reasons
            reasons = info.get('reasons', set())
            if 'count' in reasons:
                msgs.append("低词频")
            if 'variety' in reasons:
                msgs.append("低泛度")
            if not msgs:
                msgs.append("低统计（未知原因）")
        
        # 创建一个临时窗口显示问题
        # 若已有同名问题窗口先销毁（避免多个）
        if hasattr(self, "_sidebar_info_win") and self._sidebar_info_win:
            try:
                self._sidebar_info_win.destroy()
            except Exception:
                pass
            self._sidebar_info_win = None
        
        win = tk.Toplevel(self.root)
        self._sidebar_info_win = win
        win.title(f"问题 - {info['display']}")
        win.transient(self.root)
        # 不使用 grab_set（会阻止点击外部），而是监听 FocusOut 事件来自动关闭窗口
        win.geometry("220x80")
        # 内容
        lbl = ttk.Label(win, text="\n".join(msgs), anchor="center", justify="center", font=("SimHei", 12))
        lbl.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        # 当窗口失去焦点（用户点击窗口外）时自动关闭
        def close_on_focus_out(event):
            # event.widget is window or child; when window loses focus, destroy
            try:
                win.destroy()
            except Exception:
                pass
            finally:
                self._sidebar_info_win = None
        
        # Bind focus out on the toplevel
        win.bind("<FocusOut>", close_on_focus_out)
        # Give focus to the new window so focus-out will be detected when clicking outside
        win.focus_force()
    
    def on_sidebar_double_click(self, event):
        """双击侧边栏项：跳转到该单词在文本中的位置"""
        # Identify item under cursor
        item_id = self.sidebar_tree.identify_row(event.y)
        if not item_id:
            return
        key = item_id
        info = self.highlighted_map.get(key)
        if not info:
            return
        pos = info.get('pos')
        if pos is None:
            return
        # Convert char position to text index and move cursor + scroll to it
        text = self.text_area.get("1.0", tk.END)
        index = self.get_text_index(text, pos)
        try:
            # 将插入点移动到单词开头并使其可见
            self.text_area.mark_set(tk.INSERT, index)
            self.text_area.see(index)
            self.text_area.focus_set()
            # 也可以高亮选择该单词所在行（可选）
            # 将选择范围设置为该单词（若需要）
        except Exception:
            pass
    
    # ---------------------- 辅助功能 ----------------------
    def get_text_index(self, text, char_pos):
        """将字符位置转换为tkinter文本索引"""
        line = text.count('\n', 0, char_pos) + 1
        if line == 1:
            col = char_pos
        else:
            last_newline = text.rfind('\n', 0, char_pos)
            col = char_pos - last_newline - 1
        return f"{line}.{col}"
    
    def push_undo_state(self, event=None):
        """将当前文本状态压入撤销栈"""
        if self.is_undoing or not self.text_area.edit_modified():
            return
        
        current_text = self.text_area.get("1.0", tk.END)
        current_cursor = self.text_area.index(tk.INSERT)
        
        self.undo_stack.append((current_text, current_cursor))
        if len(self.undo_stack) > self.max_undo_steps:
            self.undo_stack.pop(0)
        
        self.text_area.edit_modified(False)
    
    def undo(self, event=None):
        """执行撤销操作"""
        if not self.undo_stack:
            messagebox.showinfo("提示", "无更多可撤销的操作")
            return
        
        self.is_undoing = True
        
        last_text, last_cursor = self.undo_stack.pop()
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", last_text)
        self.text_area.mark_set(tk.INSERT, last_cursor)
        
        self.check_words()
        
        self.is_undoing = False
        self.text_area.edit_modified(False)

if __name__ == "__main__":
    root = tk.Tk()
    root.option_add("*Font", "SimHei 10")
    app = WordCheckerApp(root)
    root.mainloop()
