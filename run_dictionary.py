import sys
import os

# 添加当前目录到sys.path，确保能正确导入模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from update_checker import UpdateChecker
from dictionary_app.alice_dictionary_app import AliceDictionaryApp


def on_closing(root, update_checker):
    """窗口关闭回调，执行更新操作"""
    print("窗口关闭中，检查是否需要更新...")
    # 执行更新
    update_checker.perform_update(root)
    # 关闭窗口
    root.destroy()

if __name__ == "__main__":
    # 检查更新
    local_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translated.db")
    update_checker = UpdateChecker(local_db_path)
    
    # 创建根窗口
    root = tk.Tk()
    
    # 启动后台检查
    update_checker.start_background_check()
    
    # 解析命令行参数
    search_word = None
    exact_match = False
    
    if len(sys.argv) > 1:
        search_word = sys.argv[1]
    
    if len(sys.argv) > 2:
        exact_match = sys.argv[2].lower() == "true"
    
    # 绑定关闭事件
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root, update_checker))
    
    app = AliceDictionaryApp(root, search_word, exact_match)
    root.mainloop()