import tkinter as tk
from tkinter import ttk, scrolledtext, font
import sys
from typing import Dict
from config import Config
from text_processor import TextProcessor


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
        
        # 新增：历史记录相关变量
        self.history_listbox = None
        self.history_frame = None
        self.is_history_visible = False

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
        self.query_entry.bind('<Double-Button-1>', lambda e: self.toggle_history())
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
        
        # 创建历史记录显示区域
        self.history_frame = ttk.Frame(self.left_frame)
        # 历史记录列表框
        self.history_listbox = tk.Listbox(
            self.history_frame, 
            font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE),
            height=5,  # 默认显示5条记录
            width=50,  # 宽度与搜索框匹配
            relief="solid",
            borderwidth=1
        )
        self.history_listbox.pack(fill=tk.X, expand=True)
        
        # 为历史记录列表框添加点击事件
        self.history_listbox.bind('<Button-1>', lambda e: self.on_history_item_click())
        
        # 初始化时隐藏历史记录
        self.history_frame.pack_forget()

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

    def add_result_entry(self, word: str, explanation: str, word_class: str, result_type: str, index: int, count: int = 0, variety: int = 0) -> None:
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
            # 单词名称，突出显示
            label1 = ttk.Label(word_frame, text=f"爱丽丝语: {word}", font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "bold"))
            label1.pack(anchor=tk.W, pady=(0, 1))
            
            # 统计信息行，包含词频和泛度
            stats_frame = ttk.Frame(word_frame)
            stats_frame.pack(anchor=tk.W, padx=(10, 0), pady=(0, 1))
            
            # 词频和泛度数据，使用斜体和灰色字体
            ttk.Label(stats_frame, text=f"词频: {count}", font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "italic"), foreground=Config.INFO_COLOR).pack(side=tk.LEFT, padx=(0, 15))
            ttk.Label(stats_frame, text=f"泛度: {variety}", font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "italic"), foreground=Config.INFO_COLOR).pack(side=tk.LEFT)
            
            # 词性信息，使用斜体和灰色字体
            if word_class and word_class.strip():
                ttk.Label(word_frame, text=f"词性: {word_class}", font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "italic"), foreground=Config.INFO_COLOR).pack(anchor=tk.W, padx=(10, 0), pady=(0, 1))
            
            # 翻译内容，使用常规字体
            ttk.Label(word_frame, text=f"中文翻译: {explanation}", wraplength=400).pack(anchor=tk.W, pady=(0, 1))
            
            # 为所有标签添加滚轮事件绑定
            for widget in stats_frame.winfo_children() + [label1, word_frame]:
                for evt in ["<MouseWheel>", "<Button-4>", "<Button-5>"]:
                    widget.bind(evt, self.app.on_mouse_wheel)
        else:
            # 中文单词，突出显示
            label1 = ttk.Label(word_frame, text=f"中文: {explanation}", font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "bold"))
            label1.pack(anchor=tk.W, pady=(0, 1))
            
            # 统计信息行，包含词频和泛度
            stats_frame = ttk.Frame(word_frame)
            stats_frame.pack(anchor=tk.W, padx=(10, 0), pady=(0, 1))
            
            # 词频和泛度数据，使用斜体和灰色字体
            ttk.Label(stats_frame, text=f"词频: {count}", font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "italic"), foreground=Config.INFO_COLOR).pack(side=tk.LEFT, padx=(0, 15))
            ttk.Label(stats_frame, text=f"泛度: {variety}", font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "italic"), foreground=Config.INFO_COLOR).pack(side=tk.LEFT)
            
            # 词性信息，使用斜体和灰色字体
            if word_class and word_class.strip():
                ttk.Label(word_frame, text=f"词性: {word_class}", font=(Config.FONT_FAMILY, Config.DEFAULT_FONT_SIZE, "italic"), foreground=Config.INFO_COLOR).pack(anchor=tk.W, padx=(10, 0), pady=(0, 1))
            
            # 爱丽丝语翻译，使用常规字体
            ttk.Label(word_frame, text=f"爱丽丝语: {word}", wraplength=400).pack(anchor=tk.W, pady=(0, 1))
            
            # 为所有标签添加滚轮事件绑定
            for widget in stats_frame.winfo_children() + [label1, word_frame]:
                for evt in ["<MouseWheel>", "<Button-4>", "<Button-5>"]:
                    widget.bind(evt, self.app.on_mouse_wheel)
        
        # 查询例句按钮
        button = ttk.Button(frame, text="查询例句", command=lambda w=word: self.app.start_show_examples(w))
        button.pack(side=tk.RIGHT, padx=5, pady=5)
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
    
    def toggle_history(self) -> None:
        """切换历史记录的显示/隐藏状态"""
        if self.is_history_visible:
            self.hide_history()
        else:
            self.show_history()
    
    def show_history(self) -> None:
        """显示历史记录"""
        # 清空历史记录列表
        self.history_listbox.delete(0, tk.END)
        
        # 获取历史记录
        history = self.app.history_manager.get_history()
        
        # 添加历史记录到列表框
        for record in history:
            self.history_listbox.insert(tk.END, record)
        
        # 显示历史记录框
        self.history_frame.pack(fill=tk.X, pady=(0, 10))
        self.is_history_visible = True
        
        # 绑定点击外部区域隐藏历史记录的事件
        self.root.bind('<Button-1>', self.on_click_outside_history)
    
    def hide_history(self) -> None:
        """隐藏历史记录"""
        self.history_frame.pack_forget()
        self.is_history_visible = False
        
        # 解绑点击外部区域的事件
        self.root.unbind('<Button-1>')
    
    def on_click_outside_history(self, event) -> None:
        """点击外部区域隐藏历史记录"""
        widget = event.widget
        
        # 检查点击的是否是历史记录框或搜索框
        if widget != self.history_listbox and widget != self.query_entry:
            # 检查父组件链中是否包含历史记录框
            current_widget = widget
            is_inside_history = False
            while current_widget:
                if current_widget == self.history_frame:
                    is_inside_history = True
                    break
                current_widget = current_widget.master
            
            if not is_inside_history:
                self.hide_history()
    
    def on_history_item_click(self) -> None:
        """处理历史记录项点击事件"""
        try:
            # 获取选中的历史记录
            index = self.history_listbox.curselection()[0]
            record = self.history_listbox.get(index)
            
            # 填充搜索框
            self.query_entry.delete(0, tk.END)
            self.query_entry.insert(0, record)
            
            # 执行搜索
            self.app.search_word()
            
            # 隐藏历史记录
            self.hide_history()
        except IndexError:
            pass
