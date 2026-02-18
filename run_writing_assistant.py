# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
import sys
import os

# 添加当前目录到sys.path，确保能正确导入模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
import logging
from writing_assistant.database_manager import DatabaseManager

# 导入所有模块
from writing_assistant.config_manager import ConfigManager
from writing_assistant.gui_manager import GUIManager
from writing_assistant.file_manager import FileManager
from writing_assistant.highlight_manager import HighlightManager
from writing_assistant.word_checker import WordChecker
from writing_assistant.sidebar_manager import SidebarManager
from writing_assistant.explanation_manager import ExplanationManager
from writing_assistant.undo_manager import UndoManager

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WordCheckerApp:
    """单词检查器主应用类，负责协调各个模块"""
    def __init__(self, root):
        self.root = root
        self.root.title("单词检查器")
        # 初始屏幕更大，不让侧边栏挤压文本区
        self.root.geometry("1000x700")
        
        # 初始化数据库管理器
        self.db_manager = DatabaseManager()
        
        # 初始化配置管理器
        self.config_manager = ConfigManager()
        
        # 创建GUI管理器，传入回调函数
        self.gui_manager = GUIManager(
            root, 
            self.config_manager,
            on_save_callback=self.on_save_file,
            on_undo_callback=self.on_undo,
            on_check_callback=self.on_check_words,
            on_settings_callback=self.on_open_settings
        )
        
        # 获取GUI组件引用
        self.text_area = self.gui_manager.get_text_area()
        self.sidebar_tree = self.gui_manager.get_sidebar_tree()
        self.status_label = self.gui_manager.get_status_label()
        
        # 初始化文件管理器
        self.file_manager = FileManager(self.text_area, self.status_label)
        
        # 初始化高亮管理器
        self.highlight_manager = HighlightManager(self.config_manager)
        
        # 初始化单词检查器
        self.word_checker = WordChecker(
            root, 
            self.text_area, 
            self.highlight_manager, 
            self.config_manager
        )
        
        # 初始化撤销管理器
        self.undo_manager = UndoManager(self.text_area, self.config_manager)
        
        # 初始化释义管理器
        self.explanation_manager = ExplanationManager(
            root, 
            self.text_area, 
            self.config_manager, 
            self.db_manager
        )
        
        # 初始化侧边栏管理器
        self.sidebar_manager = SidebarManager(
            root, 
            self.sidebar_tree, 
            self.text_area, 
            self.highlight_manager,
            self.explanation_manager
        )
        
        # 设置GUI回调
        self.gui_manager.set_on_open_txt_callback(self.on_open_txt_file)
        self.gui_manager.set_on_closing_callback(self.on_closing)
        
        # 绑定撤销状态保存事件
        self.text_area.bind("<<Modified>>", self.undo_manager.push_undo_state)
        
        # 初始化数据
        self.load_known_words()
    
    # ---------------------- 回调函数 ----------------------
    def on_check_words(self, event=None):
        """检查单词回调"""
        unknown_count = self.word_checker.check_words()
        self.update_status_label(unknown_count)
        self.sidebar_manager.update_sidebar()
    
    def on_save_file(self, event=None):
        """保存文件回调"""
        self.file_manager.save_file(event)
    
    def on_undo(self, event=None):
        """撤销操作回调"""
        self.undo_manager.undo(event)
        self.on_check_words()  # 撤销后重新检查
    
    def on_open_txt_file(self):
        """打开文本文件回调"""
        content, file_path = self.file_manager.open_txt_file()
        if content is not None:
            self.undo_manager.push_undo_state()
            self.on_check_words()
    
    def on_open_settings(self):
        """打开设置窗口回调"""
        self.gui_manager.create_settings_window(self.on_save_settings)
    
    def on_save_settings(self, new_strict_case, new_undo_steps):
        """保存设置回调"""
        # 检查严格匹配大小写是否变化
        if new_strict_case != self.config_manager.get("strict_case"):
            self.config_manager.set("strict_case", new_strict_case)
            # 重新加载已知单词
            self.highlight_manager.clear()
            self.load_known_words()
            # 重置单词检查器状态，确保下次检查不会因为文本内容不变而跳过
            self.word_checker.reset_state()
            self.on_check_words()
        
        # 检查最大撤销步数是否变化
        if new_undo_steps != self.config_manager.get("max_undo_steps"):
            self.config_manager.set("max_undo_steps", new_undo_steps)
            # 更新撤销管理器的最大撤销步数
            self.undo_manager.update_max_undo_steps()
        
        # 保存配置
        if self.config_manager.save_config():
            tk.messagebox.showinfo("提示", "设置已保存")
        else:
            tk.messagebox.showerror("错误", "保存设置失败")
    
    def on_closing(self):
        """窗口关闭回调"""
        self.root.destroy()
    
    # ---------------------- 数据加载 ----------------------
    def load_known_words(self):
        """从数据库加载已知单词"""
        try:
            status_message = self.highlight_manager.load_known_words_from_db(self.db_manager)
            self.status_label.config(text=f"状态：就绪 - {status_message}")
        except Exception as e:
            print(f"数据库错误: {e}")
            error_window = tk.Toplevel(self.root)
            error_window.title("数据库错误")
            error_label = tk.Label(error_window, text=f"无法加载数据库: {e}")
            error_label.pack(padx=20, pady=20)
            ok_button = tk.Button(error_window, text="确定", command=error_window.destroy)
            ok_button.pack(pady=10)
            self.status_label.config(text="状态：数据库加载失败")
    
    # ---------------------- 状态更新 ----------------------
    def update_status_label(self, unknown_count):
        """更新状态标签"""
        case_status = "严格区分大小写" if self.config_manager.get("strict_case") else "不区分大小写"
        
        if self.file_manager.current_file_path:
            import os
            file_name = os.path.basename(self.file_manager.current_file_path)
            self.status_label.config(
                text=f"状态：已检查 - {file_name} - 未知单词: {unknown_count}个 - 已加载 {len(self.highlight_manager.known_words)} 个已知单词（{case_status}）"
            )
        else:
            self.status_label.config(
                text=f"状态：已检查 - 未知单词: {unknown_count}个 - 已加载 {len(self.highlight_manager.known_words)} 个已知单词（{case_status}）"
            )

# 主程序入口
if __name__ == "__main__":
    root = tk.Tk()
    app = WordCheckerApp(root)
    root.mainloop()