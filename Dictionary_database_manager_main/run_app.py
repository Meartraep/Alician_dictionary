# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
import tkinter as tk
from dictionary_manager.main import EnhancedDictionaryDatabaseManager

if __name__ == "__main__":
    root = tk.Tk()
    app = EnhancedDictionaryDatabaseManager(root)
    root.mainloop()