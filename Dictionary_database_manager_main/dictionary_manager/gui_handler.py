import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

class GUIHandler:
    def __init__(self, database_manager, data_viewer, data_editor):
        self.db_manager = database_manager
        self.data_viewer = data_viewer
        self.data_editor = data_editor
        self.root = None
        self.status_var = None
        self.tables_listbox = None
        self.table_frame = None
        self.current_table = None
        self.fields = []
        
    def set_root(self, root):
        """设置根窗口"""
        self.root = root
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        
    def setup_fonts(self):
        """设置支持中文的字体"""
        style = ttk.Style()
        style.configure("Treeview", font=("SimHei", 10))
        style.configure("Treeview.Heading", font=("SimHei", 10, "bold"))
        style.configure("TButton", font=("SimHei", 10))
        style.configure("TLabel", font=("SimHei", 10))
    
    def create_widgets(self):
        """创建界面组件"""
        if not self.root:
            return
        
        # 设置中文字体
        self.setup_fonts()
        
        # 主框架分为左右两部分：左侧表列表，右侧数据管理
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左侧表列表区域
        left_frame = ttk.Frame(main_frame, width=200)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        left_frame.pack_propagate(False)
        
        ttk.Label(left_frame, text="数据库表列表", font=("SimHei", 10, "bold")).pack(pady=5)
        
        # 表列表框
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5)
        
        self.tables_listbox = tk.Listbox(list_frame, font=("SimHei", 10), selectmode=tk.SINGLE)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tables_listbox.yview)
        self.tables_listbox.config(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tables_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 绑定表选择事件
        self.tables_listbox.bind('<<ListboxSelect>>', self.on_table_select)
        
        # 表操作按钮
        table_btn_frame = ttk.Frame(left_frame)
        table_btn_frame.pack(fill=tk.X, padx=5, pady=10)
        
        ttk.Button(table_btn_frame, text="新建表", command=self.create_new_table_dialog).pack(fill=tk.X, pady=2)
        ttk.Button(table_btn_frame, text="删除当前表", command=self.drop_current_table).pack(fill=tk.X, pady=2)
        ttk.Button(table_btn_frame, text="重命名表", command=self.rename_current_table).pack(fill=tk.X, pady=2)
        
        # 字段操作按钮
        field_btn_frame = ttk.Frame(left_frame)
        field_btn_frame.pack(fill=tk.X, padx=5, pady=10)
        
        ttk.Label(field_btn_frame, text="字段操作", font=("SimHei", 10, "bold")).pack(pady=5)
        ttk.Button(field_btn_frame, text="添加字段", command=self.add_new_field).pack(fill=tk.X, pady=2)
        ttk.Button(field_btn_frame, text="删除字段", command=self.delete_field).pack(fill=tk.X, pady=2)
        ttk.Button(field_btn_frame, text="修改字段名", command=self.rename_field).pack(fill=tk.X, pady=2)
        
        # 右侧数据管理区域
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 顶部按钮区域 - 第一行：数据库相关操作
        top_frame1 = ttk.Frame(right_frame, padding=10)
        top_frame1.pack(fill=tk.X)
        
        # 数据库切换按钮
        ttk.Button(top_frame1, text="切换数据库", command=self.switch_database).pack(side=tk.LEFT, padx=5)
        
        # 批量操作按钮
        ttk.Button(top_frame1, text="全选", command=self.data_viewer.select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame1, text="取消全选", command=self.data_viewer.deselect_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame1, text="批量编辑", command=lambda: self.data_editor.batch_edit(self.fields, self.current_table)).pack(side=tk.LEFT, padx=5)
        
        # 顶部按钮区域 - 第二行：单条记录操作
        top_frame2 = ttk.Frame(right_frame, padding=(10, 0))
        top_frame2.pack(fill=tk.X)
        
        # 功能按钮
        ttk.Button(top_frame2, text="新增记录", command=lambda: self.data_editor.add_record(self.fields, self.current_table)).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame2, text="修改记录", command=lambda: self.data_editor.update_record(self.fields, self.current_table)).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame2, text="删除记录", command=lambda: self.data_editor.delete_record(self.fields, self.current_table)).pack(side=tk.LEFT, padx=5)
        
        # 搜索区域 - 支持所有字段搜索
        search_frame = ttk.Frame(right_frame, padding=10)
        search_frame.pack(fill=tk.X)
        
        ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT)
        self.data_viewer.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.data_viewer.search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind('<Return>', lambda event: self.data_viewer.search_records(self.data_viewer.search_var.get()))  # 支持回车搜索
        
        ttk.Button(search_frame, text="搜索", command=lambda: self.data_viewer.search_records(self.data_viewer.search_var.get())).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="查找与替换", command=self.show_find_replace_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="显示全部", command=self.data_viewer.refresh_data).pack(side=tk.LEFT, padx=5)
        
        # 数据表格区域
        self.table_frame = ttk.Frame(right_frame)
        self.table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 状态栏
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def show_database_selector(self, db_files):
        """显示数据库选择对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("选择数据库")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="请选择要连接的数据库:").pack(pady=10)
        
        # 创建列表框显示数据库文件
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10)
        
        listbox = tk.Listbox(frame, font=("SimHei", 10), selectmode=tk.SINGLE)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.config(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 添加数据库文件到列表
        for db in db_files:
            listbox.insert(tk.END, db)
        
        # 默认选中第一个
        if db_files:
            listbox.selection_set(0)
        
        # 选择结果变量
        result = [None]  # 使用列表来允许内部函数修改
        
        def on_select():
            if listbox.curselection():
                index = listbox.curselection()[0]
                result[0] = listbox.get(index)
                dialog.destroy()
        
        def create_new():
            # 让用户输入新数据库名称
            db_name = simpledialog.askstring("新数据库", "请输入新数据库名称:", parent=dialog)
            if db_name:
                if not db_name.endswith(".db"):
                    db_name += ".db"
                result[0] = db_name
                dialog.destroy()
        
        # 按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="连接选中", command=on_select).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="创建新数据库", command=create_new).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=10)
        
        # 居中显示
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (self.root.winfo_width() // 2) - (width // 2) + self.root.winfo_x()
        y = (self.root.winfo_height() // 2) - (height // 2) + self.root.winfo_y()
        dialog.geometry(f"+{x}+{y}")
        
        self.root.wait_window(dialog)  # 等待对话框关闭
        return result[0]
    
    def load_tables(self):
        """加载数据库中所有表"""
        if not self.tables_listbox:
            return
            
        try:
            # 清空列表
            self.tables_listbox.delete(0, tk.END)
            
            tables = self.db_manager.get_tables()
            
            # 添加到列表
            for table in tables:
                self.tables_listbox.insert(tk.END, table)
            
            # 如果有表，默认选中第一个
            if tables:
                self.tables_listbox.selection_set(0)
                self.on_table_select(None)
                
        except Exception as e:
            messagebox.showerror("错误", f"加载表失败: {e}")
    
    def on_table_select(self, event):
        """当选择不同表时触发"""
        if not self.tables_listbox.curselection():
            return
            
        # 获取选中的表名
        index = self.tables_listbox.curselection()[0]
        self.current_table = self.tables_listbox.get(index)
        
        # 加载该表的字段
        self.fields = self.db_manager.get_fields(self.current_table)
        
        # 重建表格并加载数据
        self.data_viewer.create_treeview(self.table_frame, self.fields, self.current_table)
        self.data_viewer.refresh_data()
        
        self.status_var.set(f"已选择表: {self.current_table} - 已连接到 {self.db_manager.db_file}")
    
    def switch_database(self):
        """切换到其他数据库"""
        # 先关闭当前连接
        self.db_manager.close_connection()
        
        # 清空表格
        if self.data_viewer.tree:
            self.data_viewer.clear_tree()
        
        # 清空表列表
        if self.tables_listbox:
            self.tables_listbox.delete(0, tk.END)
        
        # 重置变量
        self.current_table = None
        self.fields = []
        
        # 重新选择数据库
        db_file = self.choose_database()
        if db_file:
            # 加载表列表
            self.load_tables()
        else:
            self.status_var.set("未连接到数据库")
    
    def choose_database(self):
        """选择要连接的数据库文件"""
        # 获取当前目录下所有的.db文件
        db_files = self.db_manager.get_all_db_files()
        
        if not db_files:
            # 如果没有找到数据库文件，询问是否创建新的
            if messagebox.askyesno("数据库不存在", "未找到任何数据库文件，是否创建新的数据库？"):
                db_file = "my_dictionary.db"
                if self.db_manager.connect_database(db_file):
                    # 创建默认表
                    fields = ["单词", "释义", "来源文件"]
                    self.db_manager.create_table("words", fields)
                    return db_file
            return None
        elif len(db_files) == 1:
            # 只有一个数据库文件，直接使用
            db_file = db_files[0]
            if self.db_manager.connect_database(db_file):
                return db_file
            return None
        else:
            # 多个数据库文件，让用户选择
            db_file = self.show_database_selector(db_files)
            if db_file and self.db_manager.connect_database(db_file):
                return db_file
            return None
    
    def create_new_table_dialog(self):
        """创建新表对话框"""
        if not self.db_manager.conn:
            messagebox.showwarning("连接错误", "未连接到数据库")
            return
            
        # 获取表名
        table_name = simpledialog.askstring("新建表", "请输入新表名称:", parent=self.root)
        if not table_name:
            return
            
        # 检查表名是否已存在
        if self.db_manager.table_exists(table_name):
            messagebox.showerror("错误", f"表 '{table_name}' 已存在")
            return
        
        # 获取字段信息
        dialog = tk.Toplevel(self.root)
        dialog.title("设置表字段")
        dialog.geometry("400x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text=f"为表 '{table_name}' 设置字段:").pack(pady=10)
        
        fields_frame = ttk.Frame(dialog)
        fields_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 字段列表
        field_entries = []
        
        # 添加默认字段输入
        default_fields = ["名称", "描述"]
        for i, field in enumerate(default_fields):
            frame = ttk.Frame(fields_frame)
            frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(frame, text=f"字段 {i+1}:").pack(side=tk.LEFT, padx=5)
            entry = ttk.Entry(frame, width=30)
            entry.insert(0, field)
            entry.pack(side=tk.LEFT, padx=5)
            field_entries.append(entry)
        
        # 添加更多字段按钮
        def add_more_field():
            i = len(field_entries) + 1
            frame = ttk.Frame(fields_frame)
            frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(frame, text=f"字段 {i}:").pack(side=tk.LEFT, padx=5)
            entry = ttk.Entry(frame, width=30)
            entry.pack(side=tk.LEFT, padx=5)
            field_entries.append(entry)
        
        ttk.Button(dialog, text="添加更多字段", command=add_more_field).pack(pady=5)
        
        def create_table():
            new_fields = []
            for entry in field_entries:
                field_name = entry.get().strip()
                if not field_name:
                    messagebox.showwarning("输入错误", "字段名称不能为空")
                    return
                new_fields.append(field_name)
            
            # 检查重复
            if len(set(new_fields)) != len(new_fields):
                messagebox.showwarning("输入错误", "字段名称不能重复")
                return
                
            if not new_fields:
                messagebox.showwarning("输入错误", "至少需要一个字段")
                return
                
            if self.db_manager.create_table(table_name, new_fields):
                messagebox.showinfo("成功", f"表 '{table_name}' 已创建")
                dialog.destroy()
                self.load_tables()
                
                # 选中新创建的表
                for i in range(self.tables_listbox.size()):
                    if self.tables_listbox.get(i) == table_name:
                        self.tables_listbox.selection_set(i)
                        self.tables_listbox.see(i)
                        self.on_table_select(None)
                        break
            else:
                messagebox.showerror("错误", f"创建表失败")
        
        # 按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="创建表", command=create_table).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=10)
        
        # 居中显示
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (self.root.winfo_width() // 2) - (width // 2) + self.root.winfo_x()
        y = (self.root.winfo_height() // 2) - (height // 2) + self.root.winfo_y()
        dialog.geometry(f"+{x}+{y}")
    
    def drop_current_table(self):
        """删除当前选中的表"""
        if not self.db_manager.conn or not self.current_table:
            messagebox.showwarning("选择错误", "请先选择要删除的表")
            return
            
        if messagebox.askyesno("确认删除", f"确定要删除表 '{self.current_table}' 吗？此操作不可恢复！"):
            if self.db_manager.drop_table(self.current_table):
                messagebox.showinfo("成功", f"表 '{self.current_table}' 已删除")
                
                # 重置当前表和字段
                self.current_table = None
                self.fields = []
                
                # 重建表格
                self.data_viewer.create_treeview(self.table_frame, self.fields, None)
                
                # 重新加载表列表
                self.load_tables()
            else:
                messagebox.showerror("错误", f"删除表失败")
    
    def rename_current_table(self):
        """重命名当前表"""
        if not self.db_manager.conn or not self.current_table:
            messagebox.showwarning("选择错误", "请先选择要重命名的表")
            return
            
        new_name = simpledialog.askstring("重命名表", f"请输入 '{self.current_table}' 的新名称:", 
                                        initialvalue=self.current_table, parent=self.root)
                                        
        if not new_name or new_name == self.current_table:
            return
            
        # 检查新表名是否已存在
        if self.db_manager.table_exists(new_name):
            messagebox.showerror("错误", f"表 '{new_name}' 已存在")
            return
        
        if self.db_manager.rename_table(self.current_table, new_name):
            messagebox.showinfo("成功", f"表已重命名为 '{new_name}'")
            
            # 更新当前表名
            self.current_table = new_name
            
            # 重新加载表列表
            self.load_tables()
            
            # 选中重命名后的表
            for i in range(self.tables_listbox.size()):
                if self.tables_listbox.get(i) == new_name:
                    self.tables_listbox.selection_set(i)
                    self.tables_listbox.see(i)
                    break
        else:
            messagebox.showerror("错误", f"重命名表失败")
    
    def add_new_field(self):
        """添加新字段"""
        if not self.db_manager.conn or not self.current_table:
            messagebox.showwarning("选择错误", "请先选择一个表")
            return
            
        field_name = simpledialog.askstring("添加字段", "请输入新字段名称:", parent=self.root)
        if not field_name:
            return
            
        # 检查字段名是否已存在
        if field_name in self.fields:
            messagebox.showerror("错误", f"字段 '{field_name}' 已存在")
            return
            
        if self.db_manager.add_field(self.current_table, field_name):
            messagebox.showinfo("成功", f"已添加字段 '{field_name}'")
            
            # 重新加载字段并刷新表格
            self.fields = self.db_manager.get_fields(self.current_table)
            self.data_viewer.rebuild_treeview(self.table_frame, self.fields, self.current_table)
        else:
            messagebox.showerror("错误", f"添加字段失败")
    
    def delete_field(self):
        """删除字段"""
        if not self.db_manager.conn or not self.current_table or len(self.fields) <= 1:
            messagebox.showwarning("操作错误", "未选择表或至少保留一个字段")
            return
            
        # 让用户选择要删除的字段
        dialog = tk.Toplevel(self.root)
        dialog.title("删除字段")
        dialog.geometry("300x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="请选择要删除的字段:").pack(pady=10)
        
        field_var = tk.StringVar(value=self.fields[1] if len(self.fields) > 1 else self.fields[0])
        field_combo = ttk.Combobox(dialog, textvariable=field_var, values=self.fields, state="readonly", width=30)
        field_combo.pack(pady=10)
        
        def confirm_delete():
            field_name = field_var.get()
            
            if field_name == self.fields[0]:
                messagebox.showwarning("操作错误", "不能删除第一个字段（唯一键）")
                return
                
            if messagebox.askyesno("确认删除", f"确定要删除字段 '{field_name}' 吗？此操作将丢失该字段的所有数据！"):
                if self.db_manager.delete_field(self.current_table, field_name):
                    messagebox.showinfo("成功", f"已删除字段 '{field_name}'")
                    
                    # 重新加载字段并刷新表格
                    self.fields = self.db_manager.get_fields(self.current_table)
                    self.data_viewer.rebuild_treeview(self.table_frame, self.fields, self.current_table)
                    
                    dialog.destroy()
                else:
                    messagebox.showerror("错误", f"删除字段失败")
        
        # 按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="删除", command=confirm_delete).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=10)
    
    def rename_field(self):
        """重命名字段"""
        if not self.db_manager.conn or not self.current_table or not self.fields:
            messagebox.showwarning("选择错误", "请先选择一个表")
            return
            
        # 让用户选择要重命名的字段和新名称
        dialog = tk.Toplevel(self.root)
        dialog.title("修改字段名")
        dialog.geometry("350x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="请选择要修改的字段:").pack(pady=5)
        
        field_var = tk.StringVar(value=self.fields[0])
        field_combo = ttk.Combobox(dialog, textvariable=field_var, values=self.fields, state="readonly", width=30)
        field_combo.pack(pady=5)
        
        ttk.Label(dialog, text="请输入新字段名:").pack(pady=5)
        new_name_var = tk.StringVar()
        new_name_entry = ttk.Entry(dialog, textvariable=new_name_var, width=30)
        new_name_entry.pack(pady=5)
        
        def confirm_rename():
            old_name = field_var.get()
            new_name = new_name_var.get().strip()
            
            if not new_name:
                messagebox.showwarning("输入错误", "字段名称不能为空")
                return
                
            if old_name == new_name:
                dialog.destroy()
                return
                
            if new_name in self.fields:
                messagebox.showwarning("输入错误", f"字段 '{new_name}' 已存在")
                return
                
            if self.db_manager.rename_field(self.current_table, old_name, new_name):
                messagebox.showinfo("成功", f"字段 '{old_name}' 已重命名为 '{new_name}'")
                
                # 重新加载字段并刷新表格
                self.fields = self.db_manager.get_fields(self.current_table)
                self.data_viewer.rebuild_treeview(self.table_frame, self.fields, self.current_table)
                
                dialog.destroy()
            else:
                messagebox.showerror("错误", f"重命名字段失败")
        
        # 按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="确认", command=confirm_rename).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=10)
    
    def show_find_replace_dialog(self):
        """显示查找替换对话框"""
        FindReplaceDialog(self.root, self.db_manager, self.status_var, self.data_viewer)

class FindReplaceDialog:
    """查找替换对话框类"""
    def __init__(self, parent, db_manager, status_var, data_viewer):
        self.parent = parent
        self.db_manager = db_manager
        self.status_var = status_var
        self.data_viewer = data_viewer
        self.search_results = []
        
        # 创建对话框
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("查找与替换")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # 配置样式
        style = ttk.Style()
        style.configure("Treeview", font=("SimHei", 10))
        style.configure("Treeview.Heading", font=("SimHei", 10, "bold"))
        style.configure("TButton", font=("SimHei", 10))
        style.configure("TLabel", font=("SimHei", 10))
        
        # 创建主框架
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 查找替换输入区域
        input_frame = ttk.LabelFrame(main_frame, text="查找与替换", padding=10)
        input_frame.pack(fill=tk.X, pady=5)
        
        # 查找内容
        find_frame = ttk.Frame(input_frame)
        find_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(find_frame, text="查找内容:").pack(side=tk.LEFT, padx=5)
        self.find_var = tk.StringVar()
        find_entry = ttk.Entry(find_frame, textvariable=self.find_var, width=60)
        find_entry.pack(side=tk.LEFT, padx=5)
        find_entry.bind('<Return>', lambda event: self.search())
        
        ttk.Button(find_frame, text="查找", command=self.search).pack(side=tk.LEFT, padx=5)
        
        # 替换内容
        replace_frame = ttk.Frame(input_frame)
        replace_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(replace_frame, text="替换为:").pack(side=tk.LEFT, padx=5)
        self.replace_var = tk.StringVar()
        replace_entry = ttk.Entry(replace_frame, textvariable=self.replace_var, width=60)
        replace_entry.pack(side=tk.LEFT, padx=5)
        
        # 按钮区域
        btn_frame = ttk.Frame(input_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        self.replace_btn = ttk.Button(btn_frame, text="确定替换", command=self.replace, state=tk.DISABLED)
        self.replace_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="取消", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # 搜索结果区域
        result_frame = ttk.LabelFrame(main_frame, text="搜索结果", padding=10)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 结果表格
        columns = ["table", "id", "field", "value"]
        self.tree = ttk.Treeview(result_frame, columns=columns, show="headings", selectmode="extended")
        
        # 设置列宽和标题
        self.tree.column("table", width=150, anchor=tk.CENTER)
        self.tree.heading("table", text="表名")
        
        self.tree.column("id", width=80, anchor=tk.CENTER)
        self.tree.heading("id", text="记录ID")
        
        self.tree.column("field", width=150, anchor=tk.CENTER)
        self.tree.heading("field", text="字段名")
        
        self.tree.column("value", width=400, anchor=tk.W)
        self.tree.heading("value", text="匹配内容")
        
        # 添加滚动条
        scrollbar_y = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(result_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # 状态标签
        self.status_label = ttk.Label(main_frame, text="就绪", font=("SimHei", 10))
        self.status_label.pack(fill=tk.X, pady=5)
        
        # 自动聚焦到查找输入框
        find_entry.focus_set()
    
    def search(self):
        """执行全局搜索"""
        keyword = self.find_var.get().strip()
        if not keyword:
            self.status_label.config(text="请输入查找内容")
            return
        
        self.status_label.config(text="正在搜索...")
        self.dialog.update()
        
        # 执行全局搜索
        self.search_results = self.db_manager.global_search(keyword)
        
        # 清空现有结果
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 填充搜索结果
        for result in self.search_results:
            self.tree.insert("", tk.END, values=(result['table'], result['id'], result['field'], result['value']))
        
        # 更新状态
        count = len(self.search_results)
        self.status_label.config(text=f"搜索完成，找到 {count} 个匹配项")
        
        # 启用/禁用替换按钮
        if count > 0:
            self.replace_btn.config(state=tk.NORMAL)
        else:
            self.replace_btn.config(state=tk.DISABLED)
        
        self.status_var.set(f"全局搜索完成，找到 {count} 个匹配项")
    
    def replace(self):
        """执行替换操作"""
        keyword = self.find_var.get().strip()
        replacement = self.replace_var.get()
        
        if not keyword:
            self.status_label.config(text="请输入查找内容")
            return
        
        if not self.search_results:
            self.status_label.config(text="没有找到匹配项")
            return
        
        # 确认替换
        count = len(self.search_results)
        if not tk.messagebox.askyesno("确认替换", f"确定要替换 {count} 个匹配项吗？\n此操作不可撤销！"):
            return
        
        self.status_label.config(text="正在替换...")
        self.dialog.update()
        
        # 执行替换
        replaced_count, replaced_records = self.db_manager.global_replace(keyword, replacement, self.search_results)
        
        # 更新状态
        self.status_label.config(text=f"替换完成，共替换 {replaced_count} 个匹配项")
        self.status_var.set(f"全局替换完成，替换了 {replaced_count} 个匹配项")
        
        # 更新搜索结果
        self.search()
        
        # 刷新主界面数据
        if self.data_viewer:
            self.data_viewer.refresh_data()
        
        # 显示替换结果报告
        tk.messagebox.showinfo("替换完成", f"共找到 {count} 个匹配项，成功替换 {replaced_count} 个匹配项")