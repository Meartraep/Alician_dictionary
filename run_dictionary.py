import sys
import os

# 添加当前目录到sys.path，确保能正确导入模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from dictionary_app.alice_dictionary_app import AliceDictionaryApp


if __name__ == "__main__":
    root = tk.Tk()
    # 解析命令行参数
    search_word = None
    exact_match = False
    
    if len(sys.argv) > 1:
        search_word = sys.argv[1]
    
    if len(sys.argv) > 2:
        exact_match = sys.argv[2].lower() == "true"
    
    app = AliceDictionaryApp(root, search_word, exact_match)
    root.mainloop()