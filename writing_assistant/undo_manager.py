# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
class UndoManager:
    """撤销/重做管理器，负责撤销和重做功能的实现"""
    def __init__(self, text_area, config_manager):
        self.text_area = text_area
        self.config_manager = config_manager
        
        # 优化的撤销/重做机制
        self.undo_stack = []  # 存储操作差异而不是全文
        self.redo_stack = []
        self.max_undo_steps = self.config_manager.get("max_undo_steps")
        self.is_undoing = False
    
    def push_undo_state(self, event=None):
        """优化的撤销状态存储 - 使用差异存储而非全文存储"""
        if self.is_undoing or not self.text_area.edit_modified():
            return
        
        current_text = self.text_area.get("1.0", "end")[:-1]  # 去除末尾换行符
        current_cursor = self.text_area.index("insert")
        
        # 如果撤销栈为空，保存初始状态
        if not self.undo_stack:
            self.undo_stack.append({
                'type': 'snapshot',
                'text': current_text,
                'cursor': current_cursor
            })
        else:
            # 获取前一个状态
            previous_state = self.undo_stack[-1]
            
            # 如果前一个状态是快照，计算差异
            if previous_state['type'] == 'snapshot':
                prev_text = previous_state['text']
            else:
                # 如果前一个状态是差异，我们需要先应用所有差异来获取前一个文本
                # 为了简化，我们可以定期创建快照
                if len(self.undo_stack) % 10 == 0 or len(current_text) - previous_state.get('prev_length', 0) > 1000:
                    # 创建新的快照
                    self.undo_stack.append({
                        'type': 'snapshot',
                        'text': current_text,
                        'cursor': current_cursor
                    })
                    # 清空重做栈
                    self.redo_stack.clear()
                    self.text_area.edit_modified(False)
                    return
                
                # 从最近的快照恢复
                last_snapshot_idx = -1
                for i, state in enumerate(reversed(self.undo_stack)):
                    if state['type'] == 'snapshot':
                        last_snapshot_idx = len(self.undo_stack) - i - 1
                        break
                
                # 如果没有找到快照，创建一个
                if last_snapshot_idx == -1:
                    self.undo_stack.append({
                        'type': 'snapshot',
                        'text': current_text,
                        'cursor': current_cursor
                    })
                    self.text_area.edit_modified(False)
                    return
                
                # 从快照开始应用差异，计算前一个状态的文本
                prev_text = self.undo_stack[last_snapshot_idx]['text']
                for i in range(last_snapshot_idx + 1, len(self.undo_stack) - 1):
                    diff = self.undo_stack[i]
                    if diff['type'] == 'diff':
                        prev_text = self._apply_diff(prev_text, diff)
            
            # 计算当前文本与前一个状态的差异
            diff = self._calculate_diff(prev_text, current_text)
            
            # 只有在有实际变化时才添加到栈
            if diff:
                # 记录当前文本长度，用于后续优化
                diff['prev_length'] = len(prev_text)
                diff['cursor'] = current_cursor
                self.undo_stack.append(diff)
                
                # 限制撤销栈大小
                while len(self.undo_stack) > self.max_undo_steps:
                    # 如果移除的是快照，需要重新计算后续差异
                    if self.undo_stack[0]['type'] == 'snapshot':
                        # 移除旧快照
                        self.undo_stack.pop(0)
                        # 如果新的第一个元素是差异，将其转换为快照
                        if self.undo_stack and self.undo_stack[0]['type'] == 'diff':
                            # 创建基于当前差异的快照
                            # 这里简化处理，实际可能需要更复杂的计算
                            pass
                    else:
                        # 正常移除最早的差异
                        self.undo_stack.pop(0)
        
        # 清空重做栈
        self.redo_stack.clear()
        self.text_area.edit_modified(False)
    
    def undo(self, event=None):
        """执行撤销操作"""
        if not self.undo_stack:
            return
        
        self.is_undoing = True
        
        # 弹出当前状态，保存到重做栈
        current_state = self.undo_stack.pop()
        self.redo_stack.append(current_state)
        
        # 恢复到上一个状态
        if self.undo_stack:
            prev_state = self.undo_stack[-1]
            if prev_state['type'] == 'snapshot':
                # 直接恢复快照
                self._restore_from_snapshot(prev_state)
            else:
                # 从最近的快照开始应用差异
                last_snapshot_idx = -1
                for i, state in enumerate(reversed(self.undo_stack)):
                    if state['type'] == 'snapshot':
                        last_snapshot_idx = len(self.undo_stack) - i - 1
                        break
                
                if last_snapshot_idx != -1:
                    # 从快照恢复
                    restored_text = self.undo_stack[last_snapshot_idx]['text']
                    # 应用快照之后的所有差异
                    for i in range(last_snapshot_idx + 1, len(self.undo_stack)):
                        diff = self.undo_stack[i]
                        if diff['type'] == 'diff':
                            restored_text = self._apply_diff(restored_text, diff)
                    
                    # 设置恢复后的文本
                    self.text_area.delete("1.0", "end")
                    self.text_area.insert("1.0", restored_text)
                    
                    # 恢复光标位置
                    cursor_pos = self.undo_stack[-1].get('cursor', "1.0")
                    self.text_area.mark_set("insert", cursor_pos)
                    self.text_area.see(cursor_pos)
        else:
            # 撤销栈为空，清空文本
            self.text_area.delete("1.0", "end")
        
        self.is_undoing = False
    
    def redo(self, event=None):
        """执行重做操作"""
        if not self.redo_stack:
            return
        
        self.is_undoing = True
        
        # 弹出当前状态，保存到撤销栈
        redo_state = self.redo_stack.pop()
        self.undo_stack.append(redo_state)
        
        # 应用重做状态
        if redo_state['type'] == 'snapshot':
            self._restore_from_snapshot(redo_state)
        else:
            # 获取当前文本
            current_text = self.text_area.get("1.0", "end")[:-1]
            # 应用差异
            new_text = self._apply_diff(current_text, redo_state)
            
            # 设置新文本
            self.text_area.delete("1.0", "end")
            self.text_area.insert("1.0", new_text)
            
            # 恢复光标位置
            cursor_pos = redo_state.get('cursor', "1.0")
            self.text_area.mark_set("insert", cursor_pos)
            self.text_area.see(cursor_pos)
        
        self.is_undoing = False
    
    def _restore_from_snapshot(self, snapshot):
        """从快照恢复文本"""
        self.text_area.delete("1.0", "end")
        self.text_area.insert("1.0", snapshot['text'])
        
        # 恢复光标位置
        cursor_pos = snapshot.get('cursor', "1.0")
        self.text_area.mark_set("insert", cursor_pos)
        self.text_area.see(cursor_pos)
    
    def _calculate_diff(self, old_text, new_text):
        """简化的差异计算：只记录完整文本替换"""
        # 这里使用简化的差异计算，实际应用中可以使用更复杂的算法
        # 如Levenshtein距离或diff算法来计算最小差异
        return {
            'type': 'diff',
            'old_text': old_text,
            'new_text': new_text
        }
    
    def _apply_diff(self, text, diff):
        """应用差异"""
        # 简化的差异应用：直接返回新文本
        # 实际应用中需要根据差异类型进行不同的处理
        return diff['new_text']
    
    def update_max_undo_steps(self):
        """更新最大撤销步数"""
        new_undo_steps = self.config_manager.get("max_undo_steps")
        if new_undo_steps != self.max_undo_steps:
            self.max_undo_steps = new_undo_steps
            if len(self.undo_stack) > new_undo_steps:
                self.undo_stack = self.undo_stack[-new_undo_steps:]
