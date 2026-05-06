# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

class GUIManager:
    """GUI管理器，负责创建和管理所有GUI组件"""
    def __init__(self, root, config_manager, on_save_callback, on_undo_callback, on_check_callback, on_settings_callback):
        self.root = root
        self.config_manager = config_manager
        self.on_save_callback = on_save_callback
        self.on_undo_callback = on_undo_callback
        self.on_check_callback = on_check_callback
        self.on_settings_callback = on_settings_callback
        # 排除项变化回调
        self.on_exclude_change_callback = None
        
        # 拖动相关变量
        self.is_dragging = False
        self.start_x = 0
        self.start_text_width = 0
        self.start_sidebar_width = 0
        
        # 状态标签引用
        self.status_label = None
        
        # 文本区域引用
        self.text_area = None
        
        # 侧边栏引用
        self.sidebar_tree = None
        
        # 主体框架引用
        self.body_frame = None
        
        # 创建所有GUI组件
        self.create_widgets()
    
    def create_widgets(self):
        """创建GUI组件（包含侧边栏和可拖动分隔条）"""
        # 顶部搜索区域
        search_frame = ttk.Frame(self.root)
        search_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(search_frame, text="搜索单词：").pack(side=tk.LEFT)
        
        # 搜索输入框
        self.search_entry = ttk.Entry(search_frame, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.search_entry.bind('<Return>', self.on_search)
        
        # 精确查找复选框
        self.exact_match_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(search_frame, text="精确查找", variable=self.exact_match_var).pack(side=tk.LEFT, padx=5)
        
        # 搜索按钮
        ttk.Button(search_frame, text="搜索", command=self.on_search).pack(side=tk.LEFT, padx=5)
        
        # 顶部按钮区域
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(top_frame, text="请输入文本（单词之间用空格分隔）：").pack(side=tk.LEFT)
        ttk.Button(top_frame, text="打开TXT", command=self.on_open_txt).pack(side=tk.RIGHT, padx=5)
        ttk.Button(top_frame, text="保存文件", command=self.on_save_file).pack(side=tk.RIGHT, padx=5)
        ttk.Button(top_frame, text="撤销", command=self.on_undo).pack(side=tk.RIGHT, padx=5)
        ttk.Button(top_frame, text="设置", command=self.on_settings).pack(side=tk.RIGHT)
        
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
        
        # 绑定事件
        self.text_area.bind("<KeyRelease>", self.on_text_change)
        self.text_area.bind("<<Paste>>", lambda e: self.root.after(100, self.on_text_change))
        self.root.bind("<Control-z>", self.on_undo)
        self.root.bind("<Control-s>", self.on_save_file)  # Ctrl+S保存绑定
        
        # 设置窗口关闭时的处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    # ---------------------- 事件处理 ----------------------
    def on_text_change(self, event=None):
        """文本变化事件处理"""
        if self.on_check_callback:
            self.on_check_callback(event)
    
    def on_open_txt(self):
        """打开文本文件"""
        if hasattr(self, 'on_open_txt_callback') and self.on_open_txt_callback:
            self.on_open_txt_callback()
    
    def on_save_file(self, event=None):
        """保存文件"""
        if self.on_save_callback:
            self.on_save_callback(event)
    
    def on_undo(self, event=None):
        """撤销操作"""
        if self.on_undo_callback:
            self.on_undo_callback(event)
    
    def on_settings(self):
        """打开设置窗口"""
        if self.on_settings_callback:
            self.on_settings_callback()
    
    def on_closing(self):
        """窗口关闭事件处理"""
        if hasattr(self, 'on_closing_callback') and self.on_closing_callback:
            self.on_closing_callback()
        else:
            self.root.destroy()
    
    def on_search(self, event=None):
        """搜索单词并启动 Dictionary_app"""
        query = self.search_entry.get().strip()
        if not query:
            return
        
        # 获取精确查找状态
        exact_match = self.exact_match_var.get()
        
        # 启动 Dictionary_app 进行搜索
        import subprocess
        import sys
        import os
        
        # 检查是否在打包环境中运行
        if getattr(sys, 'frozen', False):
            # 在打包环境中，直接启动查词器的可执行文件
            try:
                # 获取当前可执行文件的目录
                current_exe_dir = os.path.dirname(os.path.abspath(sys.executable))
                
                # 查词器可执行文件路径（假设与写作助手在同一目录）
                dictionary_exe = os.path.join(current_exe_dir, 'dictionary_app_new.exe')
                
                # 检查可执行文件是否存在
                if os.path.exists(dictionary_exe):
                    # 启动查词器，传递搜索词和精确匹配参数
                    subprocess.Popen([dictionary_exe, query, str(exact_match)])
                else:
                    # 如果可执行文件不存在，显示错误信息
                    messagebox.showerror("错误", f"查词器可执行文件不存在: {dictionary_exe}")
            except Exception as e:
                messagebox.showerror("错误", f"启动查词器失败: {str(e)}")
        else:
            # 在开发环境中，使用Python解释器运行脚本
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            dictionary_script = os.path.join(project_root, 'run_dictionary.py')
            subprocess.Popen([sys.executable, dictionary_script, query, str(exact_match)], cwd=project_root)
    
    # ---------------------- 拖动分隔条功能 ----------------------
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
        self.body_frame.grid_columnconfigure(0, weight=1, minsize=new_text_width)
        self.body_frame.grid_columnconfigure(2, weight=0, minsize=new_sidebar_width)
        
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
        self.config_manager.set("text_width", final_text_width)
        self.config_manager.set("sidebar_width", final_sidebar_width)
        self.config_manager.save_config()
        
        # 应用最终宽度设置
        self.body_frame.grid_columnconfigure(0, weight=1, minsize=final_text_width)
        self.body_frame.grid_columnconfigure(2, weight=0, minsize=final_sidebar_width)
    
    # ---------------------- 设置窗口 ----------------------
    def create_settings_window(self, on_save_settings_callback):
        """创建设置窗口"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("设置")
        settings_window.geometry("450x400")
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        # 严格匹配大小写设置
        case_frame = ttk.Frame(settings_window)
        case_frame.pack(fill=tk.X, padx=20, pady=15)
        
        self.case_var = tk.BooleanVar(value=self.config_manager.get("strict_case"))
        case_check = ttk.Checkbutton(
            case_frame, 
            text="严格匹配大小写", 
            variable=self.case_var
        )
        case_check.pack(anchor=tk.W)
        
        # 最大撤销步数设置
        undo_frame = ttk.Frame(settings_window)
        undo_frame.pack(fill=tk.X, padx=20, pady=5)
        
        ttk.Label(undo_frame, text="最大撤销步数（1-1000）：").pack(side=tk.LEFT)
        self.undo_steps_var = tk.IntVar(value=self.config_manager.get("max_undo_steps"))
        undo_spin = ttk.Spinbox(
            undo_frame,
            from_=1,
            to=1000,
            textvariable=self.undo_steps_var,
            width=6
        )
        undo_spin.pack(side=tk.LEFT, padx=10)
        
        # 排除项管理
        exclude_frame = ttk.LabelFrame(settings_window, text="排除项管理")
        exclude_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)
        
        # 输入框和添加按钮
        input_frame = ttk.Frame(exclude_frame)
        input_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(input_frame, text="添加排除词：").pack(side=tk.LEFT)
        self.exclude_word_var = tk.StringVar()
        exclude_entry = ttk.Entry(input_frame, textvariable=self.exclude_word_var, width=30)
        exclude_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(input_frame, text="添加", command=self.add_excluded_word).pack(side=tk.LEFT, padx=5)
        
        # 排除项列表
        list_frame = ttk.Frame(exclude_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        ttk.Label(list_frame, text="当前排除项：").pack(anchor=tk.W)
        
        # 列表框
        self.excluded_words_list = tk.Listbox(list_frame, height=8)
        self.excluded_words_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.excluded_words_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.excluded_words_list.config(yscrollcommand=scrollbar.set)
        
        # 删除按钮
        ttk.Button(exclude_frame, text="删除选中项", command=self.remove_excluded_word).pack(anchor=tk.W, pady=5)
        
        # 加载当前排除项
        self.load_excluded_words()
        
        # 按钮区域
        btn_frame = ttk.Frame(settings_window)
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Button(btn_frame, text="确定", command=lambda: self.save_settings(settings_window, on_save_settings_callback)).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=settings_window.destroy).pack(side=tk.RIGHT, padx=5)
        
        return settings_window
    
    def load_excluded_words(self):
        """加载当前排除项到列表框"""
        # 清空列表
        self.excluded_words_list.delete(0, tk.END)
        
        # 添加当前排除项
        excluded_words = self.config_manager.get("excluded_words", [])
        for word in excluded_words:
            self.excluded_words_list.insert(tk.END, word)
    
    def add_excluded_word(self):
        """添加排除词"""
        word = self.exclude_word_var.get().strip()
        if word:
            # 检查是否已存在
            excluded_words = self.config_manager.get("excluded_words", [])
            if word not in excluded_words:
                # 添加到配置
                excluded_words.append(word)
                self.config_manager.set("excluded_words", excluded_words)
                
                # 保存配置到文件
                self.config_manager.save_config()
                
                # 添加到列表框
                self.excluded_words_list.insert(tk.END, word)
                
                # 清空输入框
                self.exclude_word_var.set("")
                
                # 触发排除项变化回调
                if self.on_exclude_change_callback:
                    self.on_exclude_change_callback()
    
    def remove_excluded_word(self):
        """删除选中的排除词"""
        selected_indices = self.excluded_words_list.curselection()
        if selected_indices:
            # 获取选中的单词
            selected_words = [self.excluded_words_list.get(idx) for idx in selected_indices]
            
            # 从配置中移除
            excluded_words = self.config_manager.get("excluded_words", [])
            for word in selected_words:
                if word in excluded_words:
                    excluded_words.remove(word)
            self.config_manager.set("excluded_words", excluded_words)
            
            # 保存配置到文件
            self.config_manager.save_config()
            
            # 从列表框中移除
            for idx in reversed(selected_indices):  # 倒序删除避免索引变化
                self.excluded_words_list.delete(idx)
                
            # 触发排除项变化回调
            if self.on_exclude_change_callback:
                self.on_exclude_change_callback()
    
    def save_settings(self, window, on_save_settings_callback):
        """保存设置并关闭窗口"""
        new_strict_case = self.case_var.get()
        new_undo_steps = self.undo_steps_var.get()
        
        if on_save_settings_callback:
            on_save_settings_callback(new_strict_case, new_undo_steps)
        
        window.destroy()
    
    # ---------------------- 设置回调函数 ----------------------
    def set_on_open_txt_callback(self, callback):
        """设置打开文本文件回调"""
        self.on_open_txt_callback = callback
    
    def set_on_closing_callback(self, callback):
        """设置窗口关闭回调"""
        self.on_closing_callback = callback
    
    def set_on_exclude_change_callback(self, callback):
        """设置排除项变化回调"""
        self.on_exclude_change_callback = callback
    
    # ---------------------- 获取组件引用 ----------------------
    def get_text_area(self):
        """获取文本区域引用"""
        return self.text_area
    
    def get_sidebar_tree(self):
        """获取侧边栏树引用"""
        return self.sidebar_tree
    
    def get_status_label(self):
        """获取状态栏标签引用"""
        return self.status_label
