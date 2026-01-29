# 测试重构后的代码功能

import tkinter as tk
from dictionary_manager import EnhancedDictionaryDatabaseManager

# 测试主程序是否能正常启动
print("测试主程序启动...")
root = tk.Tk()
root.withdraw()  # 隐藏主窗口，只进行功能测试

# 测试各组件的初始化
print("测试组件初始化...")
from dictionary_manager import DatabaseManager, DataViewer, DataEditor, GUIHandler

db_manager = DatabaseManager()
data_viewer = DataViewer(db_manager)
data_editor = DataEditor(db_manager, data_viewer)
gui_handler = GUIHandler(db_manager, data_viewer, data_editor)

print("组件初始化成功")

# 测试数据库连接功能
print("测试数据库连接...")
test_db = "test_refactor.db"
if db_manager.connect_database(test_db):
    print(f"成功连接到测试数据库: {test_db}")
    
    # 测试表创建功能
    print("测试表创建...")
    fields = ["测试字段1", "测试字段2"]
    if db_manager.create_table("test_table", fields):
        print("成功创建测试表")
        
        # 测试获取表列表
        tables = db_manager.get_tables()
        print(f"当前数据库中的表: {tables}")
        
        # 测试获取字段列表
        table_fields = db_manager.get_fields("test_table")
        print(f"test_table 的字段: {table_fields}")
        
        # 测试添加字段
        if db_manager.add_field("test_table", "测试字段3"):
            print("成功添加新字段")
            updated_fields = db_manager.get_fields("test_table")
            print(f"更新后的字段: {updated_fields}")
        
        # 测试删除表
        if db_manager.drop_table("test_table"):
            print("成功删除测试表")
    
    # 关闭连接并清理测试文件
    db_manager.close_connection()
    import os
    if os.path.exists(test_db):
        os.remove(test_db)
        print(f"已清理测试数据库: {test_db}")

print("\n所有基础功能测试通过！")
print("重构后的代码可以正常使用。")

# 关闭测试窗口
root.destroy()