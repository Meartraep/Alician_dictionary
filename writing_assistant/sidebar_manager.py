# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
import tkinter as tk
from tkinter import ttk

class SidebarManager:
    """侧边栏管理器，负责侧边栏的更新、交互和展示"""
    def __init__(self, root, sidebar_tree, text_area, highlight_manager, explanation_manager):
        self.root = root
        self.sidebar_tree = sidebar_tree
        self.text_area = text_area
        self.highlight_manager = highlight_manager
        self.explanation_manager = explanation_manager
        
        # 侧边栏信息窗口引用
        self._sidebar_info_win = None
        
        # 绑定事件
        self._bind_events()
    
    def _bind_events(self):
        """绑定侧边栏事件"""
        # 绑定单击（选择）与双击事件
        self.sidebar_tree.bind("<<TreeviewSelect>>", self.on_sidebar_select)  # 单击选择触发（显示问题窗口）
        self.sidebar_tree.bind("<Double-1>", self.on_sidebar_double_click)  # 双击跳转
    
    def update_sidebar(self):
        """优化的侧边栏更新逻辑 - 减少不必要的重建"""
        # 收集当前树中的所有项
        current_items = set(self.sidebar_tree.get_children())
        
        # 分类整理侧边栏项
        unknowns, lowstats = self.highlight_manager.categorize_sidebar_items()
        
        # 排序侧边栏项
        ordered_items = self.highlight_manager.sort_sidebar_items(unknowns, lowstats)
        
        # 批量操作前禁用更新以提高性能
        self.sidebar_tree.update_idletasks()
        
        # 使用批量删除策略：只删除不再存在的项
        items_to_delete = current_items - {key for _, key, _ in ordered_items}
        self._batch_delete_sidebar_items(items_to_delete)
        
        # 跟踪已经存在的项，避免重复插入
        existing_items = current_items - items_to_delete
        
        # 按顺序插入或更新项
        last_item = ''  # 上一个插入的项ID，用于保持正确顺序
        for _, key, info in ordered_items:
            display = info['display']
            
            # 如果项已存在，只需更新标签和位置
            if key in existing_items:
                last_item = self._update_sidebar_item(key, info, display, last_item)
            else:
                # 插入新项
                last_item = self._insert_sidebar_item(key, info, display)
        
        # 恢复更新并刷新UI
        self.sidebar_tree.update_idletasks()
    
    def _batch_delete_sidebar_items(self, items_to_delete):
        """批量删除侧边栏项"""
        for item_id in items_to_delete:
            try:
                self.sidebar_tree.delete(item_id)
            except Exception:
                pass
    
    def _update_sidebar_item(self, key, info, display, last_item):
        """更新侧边栏项"""
        # 检查标签是否需要更新
        current_tags = set(self.sidebar_tree.item(key, 'tags'))
        new_tag = 'unknown' if info['type'] == 'unknown' else 'lowstat'
        
        if new_tag not in current_tags:
            self.sidebar_tree.item(key, tags=(new_tag,))
        
        # 检查文本是否需要更新
        current_text = self.sidebar_tree.item(key, 'text')
        if current_text != display:
            self.sidebar_tree.item(key, text=display)
        
        # 移动到正确位置
        if last_item:
            self._move_sidebar_item_if_needed(key, last_item)
        
        return key
    
    def _insert_sidebar_item(self, key, info, display):
        """插入新的侧边栏项"""
        tag = ('unknown',) if info['type'] == 'unknown' else ('lowstat',)
        self.sidebar_tree.insert('', 'end', iid=key, text=display, tags=tag)
        return key
    
    def _move_sidebar_item_if_needed(self, key, last_item):
        """如果需要，将侧边栏项移动到正确位置"""
        # 获取当前项的位置
        current_children = self.sidebar_tree.get_children()
        try:
            current_index = current_children.index(key)
            expected_index = current_children.index(last_item) + 1
            
            # 如果位置不正确，移动它
            if current_index != expected_index:
                self.sidebar_tree.move(key, '', expected_index)
        except (ValueError, IndexError):
            pass
    
    def on_sidebar_select(self, event):
        """单击侧边栏项目（选择）时弹出问题窗口，点击窗口外自动关闭"""
        sel = self.sidebar_tree.selection()
        if not sel:
            return
        key = sel[0]
        info = self.highlight_manager.get_highlight_info(key)
        if not info:
            return
        
        # 区分处理不同类型的单词
        if info['type'] == 'unknown':
            # 对于红色单词（未知单词），使用模糊搜索功能
            word = info['display']
            try:
                # 获取模糊匹配结果
                explanations, similar_words = self.explanation_manager.get_word_explanations(word)
                # 显示模糊匹配结果和例句按钮
                self.explanation_manager.create_explanation_window(explanations, similar_words)
            except Exception as e:
                print(f"模糊搜索出错: {e}")
                # 出错时显示简单的未知单词提示
                msgs = ["未知单词"]
                self._show_simple_window(info, msgs)
        else:
            # 对于蓝色单词（低词频/低泛度），显示具体的统计数值
            msgs = []
            reasons = info.get('reasons', set())
            word = info['display']
            
            # 根据大小写设置获取正确的键
            if self.explanation_manager.config_manager.get("strict_case"):
                stats_key = word
            else:
                stats_key = word.lower()
            
            # 获取统计信息
            stats = self.highlight_manager.word_stats.get(stats_key, (0, 0))
            count, variety = stats
            
            # 格式化显示信息
            if 'count' in reasons:
                msgs.append(f"低词频（{count}）")
            if 'variety' in reasons:
                msgs.append(f"低泛度（{variety}）")
            if not msgs:
                msgs.append("低统计（未知原因）")
            self._show_simple_window(info, msgs)
    
    def _show_simple_window(self, info, msgs):
        """显示简单的问题窗口"""
        # 若已有同名问题窗口先销毁（避免多个）
        if hasattr(self, "_sidebar_info_win") and self._sidebar_info_win:
            try:
                self._sidebar_info_win.destroy()
            except Exception:
                pass
            self._sidebar_info_win = None
        
        win = tk.Toplevel(self.root)
        self._sidebar_info_win = win
        win.title(f"问题 - {info['display']}")
        win.transient(self.root)
        # 不使用 grab_set（会阻止点击外部），而是监听 FocusOut 事件来自动关闭窗口
        # 获取鼠标位置
        x = self.root.winfo_pointerx()
        y = self.root.winfo_pointery() + 20  # 向下偏移20像素，确保弹窗出现在鼠标下方
        # 设置窗口位置为鼠标下方
        win.geometry(f"220x80+{x}+{y}")
        # 内容
        lbl = ttk.Label(win, text="\n".join(msgs), anchor="center", justify="center", font=("SimHei", 12))
        lbl.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        # 当窗口失去焦点（用户点击窗口外）时自动关闭
        def close_on_focus_out(event):
            # event.widget is window or child; when window loses focus, destroy
            try:
                win.destroy()
            except Exception:
                pass
            finally:
                self._sidebar_info_win = None
        
        # Bind focus out on the toplevel
        win.bind("<FocusOut>", close_on_focus_out)
        # Give focus to the new window so focus-out will be detected when clicking outside
        win.focus_force()
    
    def on_sidebar_double_click(self, event):
        """双击侧边栏项：跳转到该单词在文本中的位置"""
        # Identify item under cursor
        item_id = self.sidebar_tree.identify_row(event.y)
        if not item_id:
            return
        key = item_id
        info = self.highlight_manager.get_highlight_info(key)
        if not info:
            return
        pos = info.get('pos')
        if pos is None:
            return
        
        # Convert char position to text index and move cursor + scroll to it
        text = self.text_area.get("1.0", tk.END)
        index = self._get_text_index(text, pos)
        try:
            # 将插入点移动到单词开头并使其可见
            self.text_area.mark_set(tk.INSERT, index)
            self.text_area.see(index)
            self.text_area.focus_set()
            # 也可以高亮选择该单词（可选）
            # 将选择范围设置为该单词（若需要）
        except Exception:
            pass
    
    def _get_text_index(self, text, char_pos):
        """将字符位置转换为tkinter文本索引"""
        line = text.count('\n', 0, char_pos) + 1
        if line == 1:
            col = char_pos
        else:
            last_newline = text.rfind('\n', 0, char_pos)
            col = char_pos - last_newline - 1
        return f"{line}.{col}"
