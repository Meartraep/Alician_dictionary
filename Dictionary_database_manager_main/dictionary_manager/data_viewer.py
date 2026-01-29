import tkinter as tk
from tkinter import ttk
from sqlite3 import Error

class DataViewer:
    def __init__(self, database_manager):
        self.db_manager = database_manager
        self.tree = None
        self.scrollbar_y = None
        self.scrollbar_x = None
        self.fields = []
        self.current_table = None
        self.search_var = tk.StringVar()
        
    def create_treeview(self, parent, fields, table_name):
        """创建表格视图，支持批量选择"""
        # 先销毁任何已存在的表格和滚动条
        if self.tree:
            self.tree.destroy()
        if self.scrollbar_y:
            self.scrollbar_y.destroy()
        if self.scrollbar_x:
            self.scrollbar_x.destroy()
        
        self.fields = fields
        self.current_table = table_name
        
        if not fields:
            columns = ["id"]
        else:
            columns = ["id"] + fields
            
        # 设置选择模式为EXTENDED，允许选择多条记录
        self.tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="extended")
        
        # 设置列宽和标题
        self.tree.column("id", width=60, anchor=tk.CENTER)
        self.tree.heading("id", text="ID")
        
        for i, field in enumerate(fields):
            width = 180 if i == 0 else 400 if i == 1 else 150
            self.tree.column(field, width=width, anchor=tk.W)
            self.tree.heading(field, text=field)
        
        # 添加滚动条
        self.scrollbar_y = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.tree.yview)
        self.scrollbar_x = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=self.scrollbar_y.set, xscrollcommand=self.scrollbar_x.set)
        
        self.scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        return self.tree
    
    def load_data(self, data=None):
        """加载表格数据，按ID排序"""
        if not self.db_manager.conn or not self.tree or not self.current_table:
            return
            
        # 清空现有数据
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        try:
            # 如果没有提供数据，则查询所有，按ID排序
            if data is None:
                cursor = self.db_manager.execute_query(f"SELECT * FROM {self.current_table} ORDER BY id")
                if cursor:
                    data = cursor.fetchall()
                else:
                    data = []
            
            # 填充数据
            for row in data:
                self.tree.insert("", tk.END, values=row)
                
        except Error as e:
            print(f"查询数据失败: {e}")
    
    def refresh_data(self):
        """刷新表格数据"""
        self.load_data()
    
    def search_records(self, keyword):
        """搜索所有字段，支持模糊查找，结果按ID排序"""
        if not self.db_manager.conn or not self.tree or not self.current_table or not self.fields:
            return []
            
        if not keyword.strip():
            self.refresh_data()
            return []
            
        try:
            # 构建搜索条件，搜索所有字段
            where_clause = " OR ".join([f'"{field}" LIKE ?' for field in self.fields])
            query = f"""
                SELECT * FROM {self.current_table}
                WHERE {where_clause}
                ORDER BY id
            """
            
            # 为每个字段准备参数
            params = [f'%{keyword}%'] * len(self.fields)
            
            cursor = self.db_manager.execute_query(query, params)
            if cursor:
                results = cursor.fetchall()
                self.load_data(results)
                return results
            else:
                return []
                
        except Error as e:
            print(f"搜索失败: {e}")
            return []
    
    def select_all(self):
        """选中所有记录"""
        if not self.tree:
            return
            
        # 先取消所有选择
        for item in self.tree.selection():
            self.tree.selection_remove(item)
        
        # 再选中所有项
        for item in self.tree.get_children():
            self.tree.selection_add(item)
    
    def deselect_all(self):
        """取消所有选中的记录"""
        if not self.tree:
            return
            
        # 取消所有选择
        for item in self.tree.selection():
            self.tree.selection_remove(item)
    
    def get_selected_records(self):
        """获取选中的记录"""
        if not self.tree:
            return []
            
        selected_items = self.tree.selection()
        selected_records = []
        
        for item in selected_items:
            row_data = self.tree.item(item, "values")
            selected_records.append(row_data)
        
        return selected_records
    
    def get_selected_ids(self):
        """获取选中记录的ID列表"""
        if not self.tree:
            return []
            
        selected_items = self.tree.selection()
        return [self.tree.item(item, "values")[0] for item in selected_items]
    
    def get_record_count(self):
        """获取记录总数"""
        if not self.tree:
            return 0
        return len(self.tree.get_children())
    
    def rebuild_treeview(self, parent, fields, table_name):
        """重建表格视图（用于字段修改后）"""
        # 保存当前表格的位置
        yview = None
        if self.tree:
            try:
                yview = self.tree.yview()
            except tk.TclError:
                pass  # 表格可能已经被销毁
        
        # 创建新表格
        self.create_treeview(parent, fields, table_name)
        
        # 恢复位置（如果之前有有效的位置信息）
        if yview:
            try:
                self.tree.yview_moveto(yview[0])
            except tk.TclError:
                pass  # 忽略恢复位置时的错误
        
        # 重新加载数据
        self.refresh_data()
    
    def clear_tree(self):
        """清空表格数据"""
        if self.tree:
            for item in self.tree.get_children():
                self.tree.delete(item)