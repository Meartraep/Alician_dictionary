# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
import tkinter as tk
from .database_manager import DatabaseManager
from .data_viewer import DataViewer
from .data_editor import DataEditor
from .gui_handler import GUIHandler

class EnhancedDictionaryDatabaseManager:
    def __init__(self, root):
        self.root = root
        self.root.title("增强版字典数据库管理器")
        self.root.geometry("1000x600")
        self.root.minsize(900, 600)
        
        # 初始化各子组件
        self.db_manager = DatabaseManager()
        self.data_viewer = DataViewer(self.db_manager)
        self.data_editor = DataEditor(self.db_manager, self.data_viewer)
        self.gui_handler = GUIHandler(self.db_manager, self.data_viewer, self.data_editor)
        
        # 设置根窗口引用
        self.data_editor.set_root(self.root)
        self.gui_handler.set_root(self.root)
        
        # 选择要连接的数据库
        if not self.choose_database():
            self.root.destroy()
            return
        
        # 创建界面组件
        self.gui_handler.create_widgets()
        
        # 加载表列表
        self.gui_handler.load_tables()
    
    def choose_database(self):
        """选择要连接的数据库文件"""
        return self.gui_handler.choose_database()

if __name__ == "__main__":
    root = tk.Tk()
    app = EnhancedDictionaryDatabaseManager(root)
    root.mainloop()