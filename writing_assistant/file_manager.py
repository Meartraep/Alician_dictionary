# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
import os
from tkinter import filedialog, messagebox

class FileManager:
    """文件管理器，负责文件的打开、保存和编码处理"""
    def __init__(self, text_area, status_label):
        self.text_area = text_area
        self.status_label = status_label
        
        # 当前打开的文件路径（用于保存）
        self.current_file_path = None
    
    def open_txt_file(self):
        """打开选择的TXT文件，显示内容并自动检查"""
        file_path = filedialog.askopenfilename(
            title="选择TXT文件",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialdir=os.getcwd()
        )
        
        if not file_path:
            return None, None
        
        try:
            # 尝试以UTF-8编码打开
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                # 尝试以GBK编码打开
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except Exception as e:
                messagebox.showerror("错误", f"文件编码不支持：{str(e)}")
                return None, None
        except Exception as e:
            messagebox.showerror("错误", f"打开文件失败：{str(e)}")
            return None, None
        
        # 更新当前文件路径
        self.current_file_path = file_path
        
        # 更新文本区域
        self.text_area.delete("1.0", "end")
        self.text_area.insert("1.0", content)
        
        # 更新状态标签
        file_name = os.path.basename(file_path)
        self.status_label.config(text=f"状态：已打开文件 - {file_name}")
        
        return content, file_path
    
    def save_file(self, event=None):
        """保存当前文本到文件（优先保存到已打开路径，无路径则让用户选择）"""
        if not self.current_file_path:
            save_path = filedialog.asksaveasfilename(
                title="保存文件",
                defaultextension=".txt",
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
                initialdir=os.getcwd()
            )
            if not save_path:
                return False
            self.current_file_path = save_path
        
        try:
            content = self.text_area.get("1.0", "end")
            with open(self.current_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            file_name = os.path.basename(self.current_file_path)
            self.status_label.config(text=f"状态：已保存文件 - {file_name}")
            messagebox.showinfo("提示", f"文件已保存到：\n{self.current_file_path}")
            return True
        except Exception as e:
            messagebox.showerror("错误", f"保存文件失败：{str(e)}")
            return False
    
    def get_current_file_path(self):
        """获取当前打开的文件路径"""
        return self.current_file_path
    
    def set_current_file_path(self, file_path):
        """设置当前打开的文件路径"""
        self.current_file_path = file_path
    
    def reset_current_file_path(self):
        """重置当前打开的文件路径"""
        self.current_file_path = None
