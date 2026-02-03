# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
import json
import os
from typing import List


class HistoryManager:
    def __init__(self, file_path: str = "search_history.json", max_records: int = 10):
        self.file_path = file_path
        self.max_records = max_records
        self.history = self._load_history()
    
    def _load_history(self) -> List[str]:
        """从文件加载历史记录"""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    return history if isinstance(history, list) else []
            except (json.JSONDecodeError, IOError):
                return []
        return []
    
    def _save_history(self) -> None:
        """将历史记录保存到文件"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except IOError:
            pass
    
    def add_record(self, record: str) -> None:
        """添加历史记录，自动处理重复和数量限制"""
        if not record.strip():
            return
        
        # 移除可能存在的重复记录
        if record in self.history:
            self.history.remove(record)
        
        # 添加到历史记录开头
        self.history.insert(0, record)
        
        # 限制历史记录数量
        if len(self.history) > self.max_records:
            self.history = self.history[:self.max_records]
        
        # 保存到文件
        self._save_history()
    
    def get_history(self) -> List[str]:
        """获取当前历史记录列表"""
        return self.history.copy()
    
    def clear_history(self) -> None:
        """清空历史记录"""
        self.history.clear()
        self._save_history()
    
    def delete_record(self, record: str) -> None:
        """删除指定历史记录"""
        if record in self.history:
            self.history.remove(record)
            self._save_history()
    
    def delete_index(self, index: int) -> None:
        """根据索引删除历史记录"""
        if 0 <= index < len(self.history):
            self.history.pop(index)
            self._save_history()