# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
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
        
        # 检查是否有id字段
        has_id = "id" in fields
        
        if not fields:
            columns = []
        else:
            if has_id:
                columns = fields
            else:
                # 如果没有id字段，添加一个虚拟的序号列
                columns = ["序号"] + fields
            
        # 设置选择模式为EXTENDED，允许选择多条记录
        self.tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="extended")
        
        # 设置列宽和标题
        if not has_id and columns:
            self.tree.column("序号", width=60, anchor=tk.CENTER)
            self.tree.heading("序号", text="序号")
        
        for i, field in enumerate(fields):
            if field == "id":
                width = 60
                anchor = tk.CENTER
            else:
                width = 180 if i == 0 else 400 if i == 1 else 150
                anchor = tk.W
            self.tree.column(field, width=width, anchor=anchor)
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
        """加载表格数据"""
        if not self.db_manager.conn or not self.tree or not self.current_table:
            return
            
        # 清空现有数据
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        try:
            # 检查是否有id字段
            cursor = self.db_manager.execute_query(f"PRAGMA table_info({self.current_table})")
            if cursor:
                columns = cursor.fetchall()
                column_names = [col[1] for col in columns]
                has_id = "id" in column_names
            else:
                # 如果查询失败，默认没有id字段
                has_id = False
                column_names = []
            
            # 如果没有提供数据，则查询所有
            if data is None:
                if has_id:
                    cursor = self.db_manager.execute_query(f"SELECT * FROM \"{self.current_table}\" ORDER BY id")
                else:
                    cursor = self.db_manager.execute_query(f"SELECT * FROM \"{self.current_table}\"")
                if cursor:
                    data = cursor.fetchall()
                else:
                    data = []
            
            # 填充数据
            for i, row in enumerate(data):
                if "序号" in self.tree["columns"]:
                    # 如果有虚拟序号列，添加序号
                    self.tree.insert("", tk.END, values=(i+1,) + row)
                else:
                    self.tree.insert("", tk.END, values=row)
                
        except Error as e:
            print(f"查询数据失败: {e}")
    
    def refresh_data(self):
        """刷新表格数据"""
        self.load_data()
    
    def search_records(self, keyword):
        """搜索所有字段，支持模糊查找"""
        if not self.db_manager.conn or not self.tree or not self.current_table or not self.fields:
            return []
            
        if not keyword.strip():
            self.refresh_data()
            return []
            
        try:
            # 检查是否有id字段
            cursor = self.db_manager.execute_query(f"PRAGMA table_info({self.current_table})")
            if cursor:
                columns = cursor.fetchall()
                column_names = [col[1] for col in columns]
                has_id = "id" in column_names
            else:
                # 如果查询失败，默认没有id字段
                has_id = False
                column_names = []
            
            # 构建搜索条件，搜索所有字段
            where_clause = " OR ".join([f'"{field}" LIKE ?' for field in self.fields])
            
            # 构建查询语句
            if has_id:
                query = f"""
                    SELECT * FROM "{self.current_table}"
                    WHERE {where_clause}
                    ORDER BY id
                """
            else:
                query = f"""
                    SELECT * FROM "{self.current_table}"
                    WHERE {where_clause}
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
        """获取选中记录的标识列表"""
        if not self.tree:
            return []
            
        selected_items = self.tree.selection()
        selected_ids = []
        
        for item in selected_items:
            values = self.tree.item(item, "values")
            # 检查是否有虚拟序号列
            if "序号" in self.tree["columns"]:
                # 如果有虚拟序号列，返回实际数据的第一个字段
                if len(values) > 1:
                    selected_ids.append(values[1])
                else:
                    selected_ids.append(None)
            else:
                # 如果没有虚拟序号列，返回第一个字段（可能是id）
                if values:
                    selected_ids.append(values[0])
                else:
                    selected_ids.append(None)
        
        return selected_ids
    
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