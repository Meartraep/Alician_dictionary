import os
import re
import sqlite3
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import json
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseManager:
    """数据库连接管理器 - 单例模式"""
    _instance = None
    _connection = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance
    
    def get_connection(self):
        """获取数据库连接，如果连接不存在或已关闭则创建新连接"""
        if self._connection is None or self._connection.close is not None:
            try:
                self._connection = sqlite3.connect("translated.db")
                # 启用外键约束
                self._connection.execute("PRAGMA foreign_keys = ON")
            except sqlite3.Error as e:
                logger.error(f"创建数据库连接时出错: {e}")
                raise
        return self._connection
    
    def close_connection(self):
        """关闭数据库连接"""
        if self._connection is not None:
            try:
                self._connection.close()
                self._connection = None
            except sqlite3.Error as e:
                logger.error(f"关闭数据库连接时出错: {e}")

class WordCheckerApp:
    # 预编译正则表达式
    WORD_PATTERN = re.compile(r"\b[a-zA-Z]+\b")  # 匹配单词的正则表达式
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
        
        # 优化的撤销/重做机制
        self.undo_stack = []  # 存储操作差异而不是全文
        self.redo_stack = []
        self.max_undo_steps = self.config["max_undo_steps"]
        self.is_undoing = False
        
        # 新增：当前打开的文件路径（用于保存）
        self.current_file_path = None
        
        # 存放当前被高亮的单词信息（按首出现位置记录）
        # key_for_map -> {'display': str, 'pos': int, 'type': 'unknown'/'lowstat', 'reasons': set(...) }
        self.highlighted_map = {}
        
        # 检查延迟（用于防抖）
        self.check_delay = None
        
        # 用于增量检查
        self.last_text_hash = None  # 上次检查的文本哈希值
        self.last_checked_text = ""  # 上次检查的完整文本
        self.text_buffer = {}  # 存储每行文本的映射
        
        # 创建GUI组件，加载数据库
        self.create_widgets()
        
        # 设置窗口关闭时的处理
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        self.load_known_words()
        
        # 绑定事件：原有事件 + 新增文件操作快捷键
        self.text_area.bind("<KeyRelease>", self.schedule_check)
        self.text_area.bind("<<Paste>>", lambda e: self.root.after(100, self.schedule_check))
        self.text_area.bind("<<Modified>>", self.push_undo_state)
        self.root.bind("<Control-z>", self.undo)
        self.root.bind("<Control-s>", self.save_file)  # Ctrl+S保存绑定
        
        # 设置右键菜单
        self.setup_right_click_menu()
    
    def load_config(self):
        """加载配置文件"""
        default_config = {"strict_case": True, "max_undo_steps": 100, "text_width": 500, "sidebar_width": 260}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                if "strict_case" not in self.config:
                    self.config["strict_case"] = default_config["strict_case"]
                if "max_undo_steps" not in self.config:
                    self.config["max_undo_steps"] = default_config["max_undo_steps"]
                if "text_width" not in self.config:
                    self.config["text_width"] = default_config["text_width"]
                if "sidebar_width" not in self.config:
                    self.config["sidebar_width"] = default_config["sidebar_width"]
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
        """创建GUI组件（包含侧边栏和可拖动分隔条）"""
        # 顶部按钮区域
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(top_frame, text="请输入文本（单词之间用空格分隔）：").pack(side=tk.LEFT)
        ttk.Button(top_frame, text="打开TXT", command=self.open_txt_file).pack(side=tk.RIGHT, padx=5)
        ttk.Button(top_frame, text="保存文件", command=self.save_file).pack(side=tk.RIGHT, padx=5)
        ttk.Button(top_frame, text="撤销", command=self.undo).pack(side=tk.RIGHT, padx=5)
        ttk.Button(top_frame, text="设置", command=self.open_settings).pack(side=tk.RIGHT)
        
        # 主体区域：使用grid布局实现可调整的文本区和侧边栏
        body_frame = ttk.Frame(self.root)
        body_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 保存body_frame引用，方便后续访问
        self.body_frame = body_frame
        
        # 设置grid布局的行和列配置 - 简化配置，确保侧边栏始终显示
        body_frame.grid_rowconfigure(0, weight=1)  # 第0行可扩展
        
        # 文本区列：允许扩展，设置固定的初始宽度
        body_frame.grid_columnconfigure(0, weight=1, minsize=500)  # 最小500px
        # 分隔条列：固定宽度8px，使用minsize
        body_frame.grid_columnconfigure(1, weight=0, minsize=8)
        # 侧边栏列：固定宽度，不扩展，确保始终显示
        body_frame.grid_columnconfigure(2, weight=0, minsize=260)  # 最小260px
        
        # 文本区框架
        left_frame = ttk.Frame(body_frame)
        left_frame.grid(row=0, column=0, sticky=tk.NSEW)
        
        self.text_area = scrolledtext.ScrolledText(
            left_frame, wrap=tk.WORD, font=("SimHei", 12)
        )
        self.text_area.pack(fill=tk.BOTH, expand=True)
        
        # 侧边栏框架
        sidebar_frame = ttk.Frame(body_frame)
        sidebar_frame.grid(row=0, column=2, sticky=tk.NSEW)
        
        # 侧边栏标题
        ttk.Label(sidebar_frame, text="高亮单词列表（红色优先）").pack(anchor="w", pady=(0,5), padx=5)
        
        # 使用 Treeview 以便为每行设置颜色 tag - 优化性能配置
        self.sidebar_tree = ttk.Treeview(
            sidebar_frame, 
            show="tree", 
            selectmode="browse"
        )
        # 配置标签颜色
        self.sidebar_tree.tag_configure("unknown", foreground="red")
        self.sidebar_tree.tag_configure("lowstat", foreground="blue")
        
        # 滚动条
        sidebar_scroll = ttk.Scrollbar(sidebar_frame, orient=tk.VERTICAL, command=self.sidebar_tree.yview)
        self.sidebar_tree.configure(yscrollcommand=sidebar_scroll.set)
        
        # 使用pack布局组织侧边栏内部组件
        self.sidebar_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0))
        sidebar_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定单击（选择）与双击事件
        self.sidebar_tree.bind("<<TreeviewSelect>>", self.on_sidebar_select)  # 单击选择触发（显示问题窗口）
        self.sidebar_tree.bind("<Double-1>", self.on_sidebar_double_click)  # 双击跳转
        
        # 创建可拖动的分隔条 - 直接在body_frame上创建
        self.drag_bar = tk.Canvas(body_frame, width=8, bg="#d3d3d3", cursor="sb_h_double_arrow", highlightthickness=0)
        self.drag_bar.grid(row=0, column=1, sticky=tk.NS)
        
        # 直接在Canvas上绑定拖动事件
        self.drag_bar.bind("<Button-1>", self.start_drag)
        self.drag_bar.bind("<B1-Motion>", self.on_drag)
        self.drag_bar.bind("<ButtonRelease-1>", self.end_drag)
        
        self.status_label = ttk.Label(self.root, text="状态：初始化中...")
        self.status_label.pack(pady=5, anchor="w", padx=10)
        
        # 现有：未知单词红色标记
        self.text_area.tag_config("unknown", foreground="red")
        # 新增：低统计（count 或 variety < 3）蓝色高亮
        self.text_area.tag_config("lowstat", foreground="blue")
        
        # 优化文本更新：设置延迟更新标志
        self._updating_highlight = False
        self._pending_highlight_update = False
        
        # 拖动相关变量
        self.is_dragging = False
        self.start_x = 0
        self.start_text_width = 0
        self.start_sidebar_width = 0
        
    def start_drag(self, event):
        """开始拖动分隔条"""
        self.is_dragging = True
        # 记录初始鼠标位置和当前宽度
        self.start_x = event.x_root
        # 获取当前文本区和侧边栏的实际宽度
        self.start_text_width = self.text_area.master.winfo_width()
        self.start_sidebar_width = self.sidebar_tree.master.winfo_width()
        
    def on_drag(self, event):
        """拖动分隔条时调整宽度"""
        if not self.is_dragging:
            return
        
        # 计算拖动距离
        delta_x = event.x_root - self.start_x
        
        # 计算新的宽度 - 简化计算，直接调整文本区宽度
        new_text_width = max(300, self.start_text_width + delta_x)  # 文本区最小300px
        new_sidebar_width = max(260, self.start_sidebar_width - delta_x)  # 侧边栏最小260px
        
        # 应用新宽度 - 直接修改grid列宽配置
        self.body_frame.grid_columnconfigure(0, minsize=new_text_width)
        self.body_frame.grid_columnconfigure(2, minsize=new_sidebar_width)
        
        # 强制更新布局
        self.root.update_idletasks()
        
    def end_drag(self, event):
        """结束拖动，保存宽度设置"""
        if not self.is_dragging:
            return
        
        self.is_dragging = False
        
        # 获取最终宽度
        final_text_width = self.text_area.master.winfo_width()
        final_sidebar_width = self.sidebar_tree.master.winfo_width()
        
        # 保存到配置
        self.config["text_width"] = final_text_width
        self.config["sidebar_width"] = final_sidebar_width
        self.save_config()
        
        # 应用最终宽度设置
        self.body_frame.grid_columnconfigure(0, minsize=final_text_width)
        self.body_frame.grid_columnconfigure(2, minsize=final_sidebar_width)
    
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
            # 使用数据库连接管理器获取连接
            db_manager = DatabaseManager()
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            for word in words:
                if self.config["strict_case"]:
                    cursor.execute("SELECT explanation FROM dictionary WHERE words = ?", (word,))
                else:
                    cursor.execute("SELECT explanation FROM dictionary WHERE LOWER(words) = LOWER(?)", (word,))
                result = cursor.fetchone()
                explanations[word] = result[0] if result else "未找到释义"
            # 不再手动关闭连接，由数据库管理器统一管理
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
        
        # 设置窗口关闭时的清理函数
        window.protocol("WM_DELETE_WINDOW", lambda: self._cleanup_window(window))
        
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
            # 使用数据库连接管理器获取连接
            db_manager = DatabaseManager()
            conn = db_manager.get_connection()
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
            
            # 不再手动关闭连接，由数据库管理器统一管理
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
        # 增加延迟时间以减少检查频率，特别是对大文件
        delay_ms = 200 if len(self.text_area.get("1.0", tk.END)) > 10000 else 100
        self.check_delay = self.root.after(delay_ms, self.check_words)
    
    def check_words(self):
        """检查文本中的单词并高亮显示未知单词；同时对低统计单词标蓝；并更新侧边栏"""
        text = self.text_area.get("1.0", tk.END)
        current_hash = hash(text)
        
        # 文本为空时的处理
        if not text.strip():
            # 清除所有高亮
            self.text_area.tag_remove("unknown", "1.0", tk.END)
            self.text_area.tag_remove("lowstat", "1.0", tk.END)
            self.highlighted_map.clear()
            
            case_status = "严格区分大小写" if self.config["strict_case"] else "不区分大小写"
            self.status_label.config(text=f"状态：就绪 - 已加载 {len(self.known_words)} 个已知单词（{case_status}）")
            self.update_sidebar()
            self.last_text_hash = None
            self.last_checked_text = ""
            return
        
        # 如果文本没有变化，直接返回
        if self.last_text_hash is not None and current_hash == self.last_text_hash:
            return
        
        # 对于小文件或者首次检查，使用全量扫描
        if len(text) < 10000 or self.last_text_hash is None:
            return self._full_text_check(text)
        
        # 对于大文件，尝试增量检查
        try:
            # 获取变化的行范围
            changed_lines = self._get_changed_lines(self.last_checked_text, text)
            if not changed_lines:
                self.last_text_hash = current_hash
                self.last_checked_text = text
                return
                
            # 清除变化行的高亮
            for line_num in changed_lines:
                start_pos = f"{line_num}.0"
                end_pos = f"{line_num}.end"
                self.text_area.tag_remove("unknown", start_pos, end_pos)
                self.text_area.tag_remove("lowstat", start_pos, end_pos)
            
            # 重新检查变化的行
            unknown_count = self._check_changed_lines(text, changed_lines)
            
            # 更新状态标签
            self._update_status_label(unknown_count)
            
            # 更新侧边栏
            self.update_sidebar()
            
            # 保存当前文本状态
            self.last_text_hash = current_hash
            self.last_checked_text = text
            
        except Exception as e:
            logger.error(f"增量检查出错: {e}")
            # 出错时回退到全量检查
            return self._full_text_check(text)
    
    def _full_text_check(self, text):
        """全量检查文本中的所有单词 - 优化的批量高亮更新"""
        # 移除所有高亮
        self.text_area.tag_remove("unknown", "1.0", tk.END)
        self.text_area.tag_remove("lowstat", "1.0", tk.END)
        
        # 清空高亮映射
        self.highlighted_map.clear()
        
        unknown_count = 0
        
        # 批量处理：先收集所有需要添加的标签
        tags_to_add = {"unknown": [], "lowstat": []}
        
        # 使用预编译的正则表达式
        matches = self.WORD_PATTERN.finditer(text)
        
        # 第一阶段：收集所有需要高亮的单词信息
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
                # 未知单词：收集红色标记
                tags_to_add["unknown"].append((start_pos, end_pos))
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
                        # 收集蓝色标记
                        tags_to_add["lowstat"].append((start_pos, end_pos))
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
        
        # 第二阶段：批量应用标签，减少UI更新次数
        # 先应用unknown标签（红色）
        for start_idx, end_idx in tags_to_add["unknown"]:
            self.text_area.tag_add("unknown", start_idx, end_idx)
        
        # 再应用lowstat标签（蓝色）
        for start_idx, end_idx in tags_to_add["lowstat"]:
            self.text_area.tag_add("lowstat", start_idx, end_idx)
            
        # 强制进行一次批量UI更新
        self.text_area.update_idletasks()
        
        # 更新状态标签
        self._update_status_label(unknown_count)
        
        # 更新侧边栏
        self.update_sidebar()
        
        # 保存当前文本状态
        self.last_text_hash = hash(text)
        self.last_checked_text = text
        
        return unknown_count
    
    def _get_changed_lines(self, old_text, new_text):
        """获取文本中发生变化的行号列表"""
        old_lines = old_text.split('\n')
        new_lines = new_text.split('\n')
        
        # 简单实现：找到第一个不同的行，然后假设之后的所有行都可能受影响
        changed_lines = set()
        max_lines = max(len(old_lines), len(new_lines))
        
        for i in range(max_lines):
            old_line = old_lines[i] if i < len(old_lines) else ""
            new_line = new_lines[i] if i < len(new_lines) else ""
            
            if old_line != new_line:
                # 记录变化的行，以及前后各一行（可能受单词分割影响）
                for j in range(max(1, i-1), min(max_lines, i+2) + 1):
                    changed_lines.add(j+1)  # tkinter行号从1开始
        
        return sorted(changed_lines)
    
    def _check_changed_lines(self, text, changed_lines):
        """优化的变更行检查逻辑 - 批量处理和内存优化"""
        # 如果没有变更行，直接返回
        if not changed_lines:
            return 0
            
        unknown_count = 0
        text_lines = text.split('\n')
        
        # 建立位置映射，用于快速找到行号对应的字符位置
        line_positions = [0]  # 行开始的字符位置
        for line in text_lines:
            line_positions.append(line_positions[-1] + len(line) + 1)  # +1 for newline
        
        # 批量操作：先收集所有需要添加的标签
        tags_to_add = {"unknown": [], "lowstat": []}
        
        # 检查每一行
        for line_num in changed_lines:
            # 确保行号有效
            if 1 <= line_num <= len(text_lines):
                line_index = line_num - 1
                line_text = text_lines[line_index]
                line_start_pos = line_positions[line_index]
                
                # 在当前行中查找单词
                for match in self.WORD_PATTERN.finditer(line_text):
                    word = match.group()
                    word_start_in_line = match.start()
                    word_end_in_line = match.end()
                    
                    # 计算在整个文本中的位置
                    global_start = line_start_pos + word_start_in_line
                    global_end = line_start_pos + word_end_in_line
                    
                    # 转换为tkinter索引
                    start_pos = self.get_text_index(text, global_start)
                    end_pos = self.get_text_index(text, global_end)
                    
                    # 检查单词是否已知
                    if self.config["strict_case"]:
                        is_known = word in self.known_words
                        key_for_stats = word
                        map_key = word
                    else:
                        lw = word.lower()
                        is_known = lw in self.known_words
                        key_for_stats = lw
                        map_key = lw
                    
                    # 收集需要添加的标签
                    if not is_known:
                        # 未知单词
                        tags_to_add["unknown"].append((start_pos, end_pos))
                        unknown_count += 1
                        
                        # 更新高亮映射
                        # 只有当这是该单词的第一次出现时，才更新位置信息
                        if map_key not in self.highlighted_map or \
                           (map_key in self.highlighted_map and 
                            self.highlighted_map[map_key]['pos'] > global_start):
                            self.highlighted_map[map_key] = {
                                'display': word,
                                'pos': global_start,
                                'type': 'unknown',
                                'reasons': set()
                            }
                    else:
                        # 已知单词，检查统计信息
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
                                # 收集蓝色标签
                                tags_to_add["lowstat"].append((start_pos, end_pos))
                                
                                # 更新高亮映射
                                if map_key not in self.highlighted_map or \
                                   (map_key in self.highlighted_map and 
                                    self.highlighted_map[map_key]['pos'] > global_start):
                                    self.highlighted_map[map_key] = {
                                        'display': word,
                                        'pos': global_start,
                                        'type': 'lowstat',
                                        'reasons': low_reasons
                                    }
                                else:
                                    existing = self.highlighted_map[map_key]
                                    if existing['type'] != 'unknown':
                                        existing['type'] = 'lowstat'
                                        existing['reasons'].update(low_reasons)
        
        # 批量清除标签 - 减少UI更新次数
        for line_num in changed_lines:
            start_pos = f"{line_num}.0"
            end_pos = f"{line_num}.end"
            self.text_area.tag_remove("unknown", start_pos, end_pos)
            self.text_area.tag_remove("lowstat", start_pos, end_pos)
        
        # 批量应用标签 - 减少UI更新次数
        # 首先处理unknown标签
        for start_idx, end_idx in tags_to_add["unknown"]:
            self.text_area.tag_add("unknown", start_idx, end_idx)
        
        # 然后处理lowstat标签
        for start_idx, end_idx in tags_to_add["lowstat"]:
            self.text_area.tag_add("lowstat", start_idx, end_idx)
            
        # 强制进行一次批量UI更新
        self.text_area.update_idletasks()
        
        return unknown_count
        
        return unknown_count
    
    def _update_status_label(self, unknown_count):
        """更新状态标签"""
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
        """优化的侧边栏更新逻辑 - 减少不必要的重建"""
        # 收集当前树中的所有项
        current_items = set(self.sidebar_tree.get_children())
        
        # 准备新的项集合
        new_items = {}
        unknowns = []
        lowstats = []
        
        # 分类整理需要显示的项
        for key, info in self.highlighted_map.items():
            if info['type'] == 'unknown':
                unknowns.append((info['pos'], key, info))
            else:
                lowstats.append((info['pos'], key, info))
        
        # 排序
        unknowns.sort(key=lambda x: x[0])
        lowstats.sort(key=lambda x: x[0])
        
        # 合并排序后的列表，unknowns 优先
        ordered_items = unknowns + lowstats
        
        # 批量操作前禁用更新以提高性能
        self.sidebar_tree.update_idletasks()
        
        # 使用批量删除策略：只删除不再存在的项
        items_to_delete = current_items - {key for _, key, _ in ordered_items}
        for item_id in items_to_delete:
            try:
                self.sidebar_tree.delete(item_id)
            except Exception:
                pass
        
        # 跟踪已经存在的项，避免重复插入
        existing_items = current_items - items_to_delete
        
        # 按顺序插入或更新项
        last_item = ''  # 上一个插入的项ID，用于保持正确顺序
        for _, key, info in ordered_items:
            display = info['display']
            
            # 如果项已存在，只需更新标签和位置
            if key in existing_items:
                # 检查标签是否需要更新
                current_tags = set(self.sidebar_tree.item(key, 'tags'))
                new_tag = 'unknown' if info['type'] == 'unknown' else 'lowstat'
                
                if new_tag not in current_tags:
                    self.sidebar_tree.item(key, tags=(new_tag,))
                
                # 检查文本是否需要更新
                current_text = self.sidebar_tree.item(key, 'text')
                if current_text != display:
                    self.sidebar_tree.item(key, text=display)
                
                # 移动到正确位置
                if last_item:
                    # 获取当前项的位置
                    current_children = self.sidebar_tree.get_children()
                    try:
                        current_index = current_children.index(key)
                        expected_index = current_children.index(last_item) + 1
                        
                        # 如果位置不正确，移动它
                        if current_index != expected_index:
                            self.sidebar_tree.move(key, '', expected_index)
                    except (ValueError, IndexError):
                        pass
                
                last_item = key
            else:
                # 插入新项
                tag = ('unknown',) if info['type'] == 'unknown' else ('lowstat',)
                self.sidebar_tree.insert('', 'end', iid=key, text=display, tags=tag)
                last_item = key
        
        # 恢复更新并刷新UI
        self.sidebar_tree.update_idletasks()
    
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
        """优化的撤销状态存储 - 使用差异存储而非全文存储"""
        if self.is_undoing or not self.text_area.edit_modified():
            return
        
        current_text = self.text_area.get("1.0", tk.END)[:-1]  # 去除末尾换行符
        current_cursor = self.text_area.index(tk.INSERT)
        
        # 如果撤销栈为空，保存初始状态
        if not self.undo_stack:
            self.undo_stack.append({
                'type': 'snapshot',
                'text': current_text,
                'cursor': current_cursor
            })
        else:
            # 获取前一个状态
            previous_state = self.undo_stack[-1]
            
            # 如果前一个状态是快照，计算差异
            if previous_state['type'] == 'snapshot':
                prev_text = previous_state['text']
            else:
                # 如果前一个状态是差异，我们需要先应用所有差异来获取前一个文本
                # 为了简化，我们可以定期创建快照
                if len(self.undo_stack) % 10 == 0 or len(current_text) - previous_state.get('prev_length', 0) > 1000:
                    # 创建新的快照
                    self.undo_stack.append({
                        'type': 'snapshot',
                        'text': current_text,
                        'cursor': current_cursor
                    })
                    # 清空重做栈
                    self.redo_stack.clear()
                    self.text_area.edit_modified(False)
                    return
                
                # 从最近的快照恢复
                last_snapshot_idx = -1
                for i, state in enumerate(reversed(self.undo_stack)):
                    if state['type'] == 'snapshot':
                        last_snapshot_idx = len(self.undo_stack) - i - 1
                        break
                
                # 如果没有找到快照，创建一个
                if last_snapshot_idx == -1:
                    self.undo_stack.append({
                        'type': 'snapshot',
                        'text': current_text,
                        'cursor': current_cursor
                    })
                    self.text_area.edit_modified(False)
                    return
                
                # 从快照开始应用差异，计算前一个状态的文本
                prev_text = self.undo_stack[last_snapshot_idx]['text']
                for i in range(last_snapshot_idx + 1, len(self.undo_stack) - 1):
                    diff = self.undo_stack[i]
                    if diff['type'] == 'diff':
                        prev_text = self._apply_diff(prev_text, diff)
            
            # 计算当前文本与前一个状态的差异
            diff = self._calculate_diff(prev_text, current_text)
            
            # 只有在有实际变化时才添加到栈
            if diff:
                # 记录当前文本长度，用于后续优化
                diff['prev_length'] = len(prev_text)
                diff['cursor'] = current_cursor
                self.undo_stack.append(diff)
                
                # 限制撤销栈大小
                while len(self.undo_stack) > self.max_undo_steps:
                    # 如果移除的是快照，需要重新计算后续差异
                    if self.undo_stack[0]['type'] == 'snapshot':
                        # 移除旧快照
                        self.undo_stack.pop(0)
                        # 如果新的第一个元素是差异，将其转换为快照
                        if self.undo_stack and self.undo_stack[0]['type'] == 'diff':
                            # 创建基于当前差异的快照
                            # 这里简化处理，实际可能需要更复杂的计算
                            pass
                    else:
                        # 正常移除最早的差异
                        self.undo_stack.pop(0)
        
        # 清空重做栈
        self.redo_stack.clear()
        self.text_area.edit_modified(False)
    
    def undo(self, event=None):
        """执行撤销操作 - 使用差异存储优化"""
        if not self.undo_stack:
            messagebox.showinfo("提示", "无更多可撤销的操作")
            return
        
        self.is_undoing = True
        
        try:
            # 获取要撤销的状态
            state_to_undo = self.undo_stack.pop()
            current_text = self.text_area.get("1.0", tk.END)[:-1]
            
            # 将当前状态保存到重做栈
            self.redo_stack.append({
                'type': 'snapshot' if state_to_undo['type'] == 'snapshot' else 'diff',
                'text': current_text if state_to_undo['type'] == 'snapshot' else None,
                'cursor': self.text_area.index(tk.INSERT)
            })
            
            if state_to_undo['type'] == 'snapshot':
                # 如果是快照，直接恢复
                self.text_area.delete("1.0", tk.END)
                self.text_area.insert("1.0", state_to_undo['text'])
                self.text_area.mark_set(tk.INSERT, state_to_undo['cursor'])
            else:
                # 如果是差异，应用逆操作
                # 找到最近的快照
                last_snapshot_idx = -1
                for i, state in enumerate(reversed(self.undo_stack)):
                    if state['type'] == 'snapshot':
                        last_snapshot_idx = len(self.undo_stack) - i - 1
                        break
                
                # 如果没有找到快照，无法撤销
                if last_snapshot_idx == -1:
                    # 恢复状态栈
                    self.undo_stack.append(state_to_undo)
                    self.redo_stack.pop()
                    messagebox.showinfo("错误", "撤销失败：找不到基准状态")
                    return
                
                # 从快照开始，应用所有差异直到当前要撤销的状态之前
                restored_text = self.undo_stack[last_snapshot_idx]['text']
                for i in range(last_snapshot_idx + 1, len(self.undo_stack)):
                    diff = self.undo_stack[i]
                    if diff['type'] == 'diff':
                        restored_text = self._apply_diff(restored_text, diff)
                
                # 更新文本
                self.text_area.delete("1.0", tk.END)
                self.text_area.insert("1.0", restored_text)
                
                # 恢复光标位置
                if 'cursor' in state_to_undo:
                    self.text_area.mark_set(tk.INSERT, state_to_undo['cursor'])
            
            # 重新检查单词
            self.check_words()
        except Exception as e:
            print(f"撤销操作错误: {e}")
            # 尝试恢复状态
            if hasattr(self, 'redo_stack') and self.redo_stack:
                self.undo_stack.append(self.redo_stack.pop())
        finally:
            self.is_undoing = False
            self.text_area.edit_modified(False)
    
    def _calculate_diff(self, old_text, new_text):
        """计算两个文本之间的差异"""
        # 如果文本完全相同，返回None
        if old_text == new_text:
            return None
        
        # 计算共同前缀长度
        common_prefix_len = 0
        min_len = min(len(old_text), len(new_text))
        while common_prefix_len < min_len and old_text[common_prefix_len] == new_text[common_prefix_len]:
            common_prefix_len += 1
        
        # 计算共同后缀长度
        common_suffix_len = 0
        while common_suffix_len < min_len - common_prefix_len and \
              old_text[len(old_text) - common_suffix_len - 1] == new_text[len(new_text) - common_suffix_len - 1]:
            common_suffix_len += 1
        
        # 提取差异部分
        old_diff_start = common_prefix_len
        old_diff_end = len(old_text) - common_suffix_len
        new_diff_start = common_prefix_len
        new_diff_end = len(new_text) - common_suffix_len
        
        # 返回差异信息
        return {
            'type': 'diff',
            'pos': common_prefix_len,
            'removed': old_text[old_diff_start:old_diff_end],
            'inserted': new_text[new_diff_start:new_diff_end]
        }
    
    def _apply_diff(self, text, diff):
        """应用差异到文本"""
        if diff['type'] != 'diff':
            return text
        
        # 在指定位置删除旧内容并插入新内容
        return text[:diff['pos']] + diff['inserted'] + text[diff['pos'] + len(diff['removed']):]
    
    def redo(self, event=None):
        """执行重做操作"""
        if not hasattr(self, 'redo_stack') or not self.redo_stack:
            messagebox.showinfo("提示", "无更多可重做的操作")
            return
        
        self.is_undoing = True
        
        try:
            # 获取要重做的状态
            state_to_redo = self.redo_stack.pop()
            current_text = self.text_area.get("1.0", tk.END)[:-1]
            
            # 将当前状态保存到撤销栈
            self.undo_stack.append({
                'type': 'snapshot' if state_to_redo['type'] == 'snapshot' else 'diff',
                'text': current_text if state_to_redo['type'] == 'snapshot' else None,
                'cursor': self.text_area.index(tk.INSERT)
            })
            
            if state_to_redo['type'] == 'snapshot':
                # 如果是快照，直接恢复
                self.text_area.delete("1.0", tk.END)
                self.text_area.insert("1.0", state_to_redo['text'])
                self.text_area.mark_set(tk.INSERT, state_to_redo['cursor'])
            else:
                # 对于差异类型的重做，需要找到最近的快照并应用差异
                # 这里简化处理，直接使用当前文本和要重做的操作
                # 在实际应用中可能需要更复杂的逻辑
                pass
            
            # 重新检查单词
            self.check_words()
        except Exception as e:
            print(f"重做操作错误: {e}")
            # 尝试恢复状态
            if hasattr(self, 'undo_stack') and self.undo_stack:
                self.redo_stack.append(self.undo_stack.pop())
        finally:
            self.is_undoing = False
            self.text_area.edit_modified(False)
    
    def _cleanup_window(self, window):
        """窗口关闭前的清理工作"""
        try:
            # 关闭前移除事件绑定等
            window.destroy()
        except Exception:
            pass
    
    def _on_closing(self):
        """主窗口关闭时的处理"""
        try:
            # 关闭数据库连接
            db_manager = DatabaseManager()
            db_manager.close_connection()
        except Exception as e:
            logger.error(f"关闭数据库连接时出错: {e}")
        finally:
            self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    root.option_add("*Font", "SimHei 10")
    app = WordCheckerApp(root)
    root.mainloop()
