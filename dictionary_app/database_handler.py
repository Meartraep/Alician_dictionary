# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
import sqlite3
import os
from typing import List, Tuple, Optional
from tkinter import messagebox
from config import Config


class DatabaseHandler:
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None

    def connect(self) -> bool:
        try:
            # 检查连接是否已经存在且有效
            if self.conn is not None:
                try:
                    # 测试连接是否有效
                    self.conn.execute("SELECT 1")
                    return True
                except sqlite3.Error:
                    # 连接无效，需要重新连接
                    self.close()
            
            # 新增：检查数据库文件是否存在
            if not self.db_name.startswith(':memory:') and not os.path.exists(self.db_name):
                messagebox.showerror("数据库错误", f"数据库文件不存在: {self.db_name}")
                return False
            
            # 确保之前的连接已关闭
            self.close()
            
            self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
            self.conn.execute("PRAGMA cache_size = -1000")
            self.conn.execute("PRAGMA synchronous = OFF")
            self.cursor = self.conn.cursor()
            return self._verify_database_structure()
        except sqlite3.Error as e:
            messagebox.showerror("数据库错误", f"连接数据库失败: {str(e)}")
            self.close()  # 确保连接已关闭
            return False
            
    def __del__(self):
        """析构函数确保连接关闭"""
        self.close()

    def _is_table_exists(self, table: str) -> bool:
        """检查表是否存在"""
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        return bool(self.cursor.fetchone())
    
    def _get_table_fields(self, table: str) -> List[str]:
        """获取表的所有字段名"""
        self.cursor.execute(f"PRAGMA table_info({table})")
        return [row[1] for row in self.cursor.fetchall()]
    
    def _verify_table_fields(self, table: str, required_fields: List[str]) -> bool:
        """验证单个表的字段是否完整"""
        actual_fields = self._get_table_fields(table)
        missing_fields = [field for field in required_fields if field not in actual_fields]
        if missing_fields:
            raise Exception(f"{table}表缺少字段: {', '.join(missing_fields)}")
        return True
    
    def _verify_database_structure(self) -> bool:
        try:
            for table, required_fields in Config.REQUIRED_TABLES.items():
                if not self._is_table_exists(table):
                    raise Exception(f"缺少{table}表")
                self._verify_table_fields(table, required_fields)
            return True
        except Exception as e:
            messagebox.showerror("数据库错误", f"数据库结构验证失败: {str(e)}")
            return False

    # 新增：is_exact参数控制精确/模糊匹配，True为精确匹配（区分大小写+完全匹配）
    def search_words(self, query: str, is_exact: bool) -> Tuple[List[Tuple[str, str, str]], List[Tuple[str, str, str]]]:
        if not self.cursor:
            return [], []
        
        # 精确匹配逻辑：不转小写+完全匹配（=）
        if is_exact:
            self.cursor.execute("SELECT words, explanation, class FROM dictionary WHERE words = ? LIMIT 20", (query,))
            alice_res = self.cursor.fetchall()
            self.cursor.execute("SELECT words, explanation, class FROM dictionary WHERE explanation = ? LIMIT 20", (query,))
            chinese_res = self.cursor.fetchall()
        # 模糊匹配逻辑：转小写+包含匹配（LIKE %query%）
        else:
            self.cursor.execute("SELECT words, explanation, class FROM dictionary WHERE LOWER(words) LIKE LOWER(?) LIMIT 20", (f'%{query}%',))
            alice_res = self.cursor.fetchall()
            self.cursor.execute("SELECT words, explanation, class FROM dictionary WHERE LOWER(explanation) LIKE LOWER(?) LIMIT 20", (f'%{query}%',))
            chinese_res = self.cursor.fetchall()
        
        return alice_res, chinese_res
    
    def search_phrases(self, query: str, is_exact: bool) -> List[Tuple[str, str]]:
        if not self.cursor:
            return []
        
        # 精确匹配逻辑：不转小写+完全匹配（=）
        if is_exact:
            self.cursor.execute("SELECT PHRASE, explanation FROM phrase WHERE PHRASE = ? LIMIT 20", (query,))
        # 模糊匹配逻辑：转小写+包含匹配（LIKE %query%）
        else:
            self.cursor.execute("SELECT PHRASE, explanation FROM phrase WHERE LOWER(PHRASE) LIKE LOWER(?) LIMIT 20", (f'%{query}%',))
        
        return self.cursor.fetchall()

    def get_all_words(self) -> List[Tuple[str, str]]:
        return self.cursor.fetchall() if (self.cursor and self.cursor.execute("SELECT words, explanation FROM dictionary")) else []

    def find_songs_with_word(self, word: str) -> List[Tuple[str, str, str]]:
        if not self.cursor or not word:
            return []
        
        self.cursor.execute("SELECT title, lyric, Album FROM songs WHERE lyric LIKE ? OR title LIKE ? OR Album LIKE ?", (f'%{word.lower()}%',)*3)
        return self.cursor.fetchall()
    
    def get_word_stats(self, word: str, is_exact: bool = True) -> Optional[Tuple[int, int]]:
        """
        获取单词的词频和泛度数据
        :param word: 要查询的单词
        :param is_exact: 是否精确匹配
        :return: (count, variety) 或 None（未找到）
        """
        if not self.cursor or not word:
            return None
        
        if is_exact:
            self.cursor.execute("SELECT count, variety FROM dictionary WHERE words = ?", (word,))
        else:
            self.cursor.execute("SELECT count, variety FROM dictionary WHERE LOWER(words) = LOWER(?)", (word,))
        
        result = self.cursor.fetchone()
        return result if result else None
    
    def get_phrase_stats(self, phrase: str, is_exact: bool = True) -> Optional[Tuple[int, int]]:
        """
        获取词组的词频和泛度数据
        :param phrase: 要查询的词组
        :param is_exact: 是否精确匹配
        :return: (count, variety) 或 None（未找到）
        """
        if not self.cursor or not phrase:
            return None
        
        if is_exact:
            self.cursor.execute("SELECT count, variety FROM phrase WHERE PHRASE = ?", (phrase,))
        else:
            self.cursor.execute("SELECT count, variety FROM phrase WHERE LOWER(PHRASE) = LOWER(?)", (phrase,))
        
        result = self.cursor.fetchone()
        return result if result else None

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None
