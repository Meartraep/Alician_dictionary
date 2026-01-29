import tkinter as tk
from dictionary_manager.main import EnhancedDictionaryDatabaseManager

if __name__ == "__main__":
    root = tk.Tk()
    app = EnhancedDictionaryDatabaseManager(root)
    root.mainloop()