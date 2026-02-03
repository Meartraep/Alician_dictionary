import sys
import os

# 添加当前目录到sys.path，确保能正确导入模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from dictionary_app.alice_dictionary_app import AliceDictionaryApp


if __name__ == "__main__":
    root = tk.Tk()
    app = AliceDictionaryApp(root)
    root.mainloop()