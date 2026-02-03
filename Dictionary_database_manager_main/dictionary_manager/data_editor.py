# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from sqlite3 import Error

class DataEditor:
    def __init__(self, database_manager, data_viewer):
        self.db_manager = database_manager
        self.data_viewer = data_viewer
        self.root = None
        
    def set_root(self, root):
        """设置根窗口"""
        self.root = root
    
    def add_record(self, fields, table_name):
        """新增记录"""
        if not self.db_manager.conn or not table_name or not fields:
            messagebox.showwarning("连接错误", "未连接到数据库或未选择表")
            return
            
        # 创建对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("新增记录")
        dialog.geometry("400x400")
        dialog.resizable(False, False)
        dialog.transient(self.root)  # 设置为主窗口的子窗口
        dialog.grab_set()  # 模态窗口
        
        # 字段输入框列表
        field_vars = []
        
        # 添加字段输入
        for i, field in enumerate(fields):
            ttk.Label(dialog, text=f"{field}:").grid(row=i, column=0, padx=10, pady=5, sticky=tk.NW)
            
            if i == 1:  # 第二个字段使用多行文本框
                text_widget = tk.Text(dialog, width=30, height=6)
                text_widget.grid(row=i, column=1, padx=10, pady=5)
                field_vars.append(("text", text_widget))
            else:  # 其他字段使用单行输入框
                var = tk.StringVar()
                entry = ttk.Entry(dialog, textvariable=var, width=30)
                entry.grid(row=i, column=1, padx=10, pady=5)
                field_vars.append(("entry", var))
        
        def save_new_record():
            # 收集所有字段值
            values = []
            for i, (type_, var) in enumerate(field_vars):
                if type_ == "entry":
                    value = var.get().strip()
                else:  # text
                    value = var.get("1.0", tk.END).strip()
                
                # 第一个字段不能为空
                if i == 0 and not value:
                    messagebox.showwarning("输入错误", f"{fields[i]}不能为空")
                    return
                    
                values.append(value)
            
            try:
                # 构建插入语句
                fields_str = ", ".join([f'"{f}"' for f in fields])
                placeholders = ", ".join(["?"] * len(fields))
                
                cursor = self.db_manager.execute_query(f'''
                    INSERT INTO {table_name} ({fields_str})
                    VALUES ({placeholders})
                ''', tuple(values))
                
                if cursor:
                    self.db_manager.commit()
                    messagebox.showinfo("成功", f"{fields[0]} '{values[0]}' 已添加")
                    dialog.destroy()
                    self.data_viewer.refresh_data()
            except sqlite3.IntegrityError:
                messagebox.showerror("错误", f"{fields[0]} '{values[0]}' 已存在")
            except Error as e:
                messagebox.showerror("错误", f"添加失败: {e}")
        
        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=len(fields), column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="保存", command=save_new_record).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=10)
        
        # 居中显示
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (self.root.winfo_width() // 2) - (width // 2) + self.root.winfo_x()
        y = (self.root.winfo_height() // 2) - (height // 2) + self.root.winfo_y()
        dialog.geometry(f"+{x}+{y}")
    
    def update_record(self, fields, table_name):
        """修改选中的记录"""
        if not self.db_manager.conn or not table_name or not fields:
            messagebox.showwarning("连接错误", "未连接到数据库或未选择表")
            return
            
        # 获取选中的行
        selected_items = self.data_viewer.tree.selection()
        if not selected_items:
            messagebox.showwarning("选择错误", f"请先选择要修改的记录")
            return
            
        # 如果选中多条，只取第一条进行编辑
        selected_item = selected_items[0]
        row_data = self.data_viewer.tree.item(selected_item, "values")
        record_id = row_data[0]
        field_values = row_data[1:]  # 排除id
        
        # 创建对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("修改记录")
        dialog.geometry("400x400")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 字段输入框列表
        field_vars = []
        
        # 添加字段输入
        for i, (field, value) in enumerate(zip(fields, field_values)):
            ttk.Label(dialog, text=f"{field}:").grid(row=i, column=0, padx=10, pady=5, sticky=tk.NW)
            
            if i == 1:  # 第二个字段使用多行文本框
                text_widget = tk.Text(dialog, width=30, height=6)
                text_widget.grid(row=i, column=1, padx=10, pady=5)
                text_widget.insert(tk.END, value)
                field_vars.append(("text", text_widget))
            else:  # 其他字段使用单行输入框
                var = tk.StringVar(value=value)
                entry = ttk.Entry(dialog, textvariable=var, width=30)
                # 第一个字段设为只读，避免唯一键冲突
                if i == 0:
                    entry.config(state="readonly")
                entry.grid(row=i, column=1, padx=10, pady=5)
                field_vars.append(("entry", var))
        
        def save_changes():
            # 收集所有字段值
            values = []
            for i, (type_, var) in enumerate(field_vars):
                if type_ == "entry":
                    value = var.get().strip()
                else:  # text
                    value = var.get("1.0", tk.END).strip()
                
                # 第一个字段不能为空
                if i == 0 and not value:
                    messagebox.showwarning("输入错误", f"{fields[i]}不能为空")
                    return
                    
                values.append(value)
            
            try:
                # 构建更新语句（排除第一个字段，因为它是唯一键）
                set_clause = ", ".join([f'"{f}" = ?' for f in fields[1:]])
                # 准备参数：字段值（从第二个开始）+ id
                params = values[1:] + [record_id]
                
                cursor = self.db_manager.execute_query(f'''
                    UPDATE {table_name}
                    SET {set_clause}
                    WHERE id = ?
                ''', tuple(params))
                
                if cursor:
                    self.db_manager.commit()
                    messagebox.showinfo("成功", f"{fields[0]} '{values[0]}' 已更新")
                    dialog.destroy()
                    self.data_viewer.refresh_data()
            except Error as e:
                messagebox.showerror("错误", f"更新失败: {e}")
        
        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=len(fields), column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="保存", command=save_changes).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=10)
        
        # 居中显示
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (self.root.winfo_width() // 2) - (width // 2) + self.root.winfo_x()
        y = (self.root.winfo_height() // 2) - (height // 2) + self.root.winfo_y()
        dialog.geometry(f"+{x}+{y}")
    
    def delete_record(self, fields, table_name):
        """删除选中的记录（支持批量删除）"""
        if not self.db_manager.conn or not table_name:
            messagebox.showwarning("连接错误", "未连接到数据库或未选择表")
            return
        
        # 获取选中的行
        selected_items = self.data_viewer.tree.selection()
        if not selected_items:
            messagebox.showwarning("选择错误", f"请先选择要删除的记录")
            return
        
        # 获取选中记录的信息，用于确认对话框
        if len(selected_items) == 1:
            row_data = self.data_viewer.tree.item(selected_items[0], "values")
            first_field_value = row_data[1] if len(row_data) > 1 else "记录"
            confirm_msg = f"确定要删除 {first_field_value} 吗？"
        else:
            confirm_msg = f"确定要删除选中的 {len(selected_items)} 条记录吗？"
            
        if messagebox.askyesno("确认删除", confirm_msg):
            try:
                # 获取所有选中记录的ID
                selected_ids = self.data_viewer.get_selected_ids()
                
                # 批量删除
                cursor = self.db_manager.execute_query(f"DELETE FROM {table_name} WHERE id IN ({', '.join('?' * len(selected_ids))})", 
                              tuple(selected_ids))
                
                if cursor:
                    self.db_manager.commit()
                    
                    # 从界面上删除选中的行
                    for item in selected_items:
                        self.data_viewer.tree.delete(item)
                    
                    messagebox.showinfo("成功", f"已成功删除 {len(selected_items)} 条记录")
            except Error as e:
                messagebox.showerror("错误", f"删除失败: {e}")
    
    def batch_edit(self, fields, table_name):
        """批量编辑选中的记录"""
        if not self.db_manager.conn or not table_name or not fields:
            messagebox.showwarning("连接错误", "未连接到数据库或未选择表")
            return
            
        # 获取选中的行
        selected_items = self.data_viewer.tree.selection()
        if not selected_items:
            messagebox.showwarning("选择错误", f"请先选择要批量编辑的记录")
            return
        
        # 创建对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("批量编辑")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text=f"将对 {len(selected_items)} 条记录进行批量编辑:").pack(pady=10)
        ttk.Label(dialog, text="请选择要修改的字段和新值:").pack(pady=5)
        
        # 选择要修改的字段
        field_frame = ttk.Frame(dialog)
        field_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(field_frame, text="选择字段:").pack(side=tk.LEFT, padx=5)
        field_var = tk.StringVar(value=fields[0] if fields else "")
        field_combo = ttk.Combobox(field_frame, textvariable=field_var, values=fields, state="readonly")
        field_combo.pack(side=tk.LEFT, padx=5)
        
        # 输入新值
        value_frame = ttk.Frame(dialog)
        value_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        ttk.Label(value_frame, text="新值:").pack(anchor=tk.W, padx=5)
        
        # 使用多行文本框，方便输入较长内容
        text_widget = tk.Text(value_frame, width=50, height=10)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        def apply_changes():
            selected_field = field_var.get()
            if not selected_field:
                messagebox.showwarning("选择错误", "请选择要修改的字段")
                return
                
            new_value = text_widget.get("1.0", tk.END).strip()
            
            if not new_value:
                if not messagebox.askyesno("确认", "新值为空，确定要将所选字段设置为空吗？"):
                    return
            
            # 确认修改
            if messagebox.askyesno("确认批量修改", 
                                 f"确定要将所选 {len(selected_items)} 条记录的 '{selected_field}' 字段修改为新值吗？"):
                try:
                    # 获取选中记录的ID
                    selected_ids = self.data_viewer.get_selected_ids()
                    
                    cursor = self.db_manager.execute_query(f'''
                        UPDATE {table_name}
                        SET "{selected_field}" = ?
                        WHERE id IN ({', '.join('?' * len(selected_ids))})
                    ''', [new_value] + selected_ids)
                    
                    if cursor:
                        self.db_manager.commit()
                        messagebox.showinfo("成功", f"已成功修改 {len(selected_items)} 条记录")
                        dialog.destroy()
                        self.data_viewer.refresh_data()
                except Error as e:
                    messagebox.showerror("错误", f"批量修改失败: {e}")
        
        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="应用修改", command=apply_changes).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=10)
        
        # 居中显示
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (self.root.winfo_width() // 2) - (width // 2) + self.root.winfo_x()
        y = (self.root.winfo_height() // 2) - (height // 2) + self.root.winfo_y()
        dialog.geometry(f"+{x}+{y}")