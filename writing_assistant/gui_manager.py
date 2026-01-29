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
        settings_window.geometry("350x200")
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
        
        # 按钮区域
        btn_frame = ttk.Frame(settings_window)
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Button(btn_frame, text="确定", command=lambda: self.save_settings(settings_window, on_save_settings_callback)).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=settings_window.destroy).pack(side=tk.RIGHT, padx=5)
        
        return settings_window
    
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
