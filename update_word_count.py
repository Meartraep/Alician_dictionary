# 原作者：Meartraep
# 项目仓库：https://github.com/Meartraep/Alician_dictionary
# 协议：CC BY-NC 4.0 | 禁止商用，改编需保留署名
import sqlite3
import os
from collections import defaultdict

def count_word_occurrences(lyric_lower, word_lower):
    """高效统计单词出现次数（基于字符串查找，比正则更快）"""
    count = 0
    start = 0
    word_len = len(word_lower)
    lyric_len = len(lyric_lower)
    while start <= lyric_len - word_len:
        # 查找单词位置
        pos = lyric_lower.find(word_lower, start)
        if pos == -1:
            break
        # 检查单词边界（避免部分匹配，如 "apple" 匹配 "applepie"）
        left_ok = pos == 0 or not lyric_lower[pos-1].isalnum()
        right_ok = (pos + word_len) == lyric_len or not lyric_lower[pos + word_len].isalnum()
        if left_ok and right_ok:
            count += 1
        # 跳过当前匹配位置，避免重叠匹配
        start = pos + 1
    return count

def main(verbose=False):
    # 数据库文件路径
    db_path = os.path.join(os.path.dirname(__file__), 'translated.db')
    
    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        print(f"错误：数据库文件 '{db_path}' 不存在！")
        return
    
    conn = None
    try:
        # 连接数据库并优化参数（针对低配电脑，减少磁盘IO）
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # 关闭磁盘同步（牺牲部分安全性，换取写入速度）
        cursor.execute("PRAGMA synchronous = OFF")
        # 日志模式改为内存（减少磁盘操作）
        cursor.execute("PRAGMA journal_mode = MEMORY")
        # 限制缓存大小（避免占用过多内存，单位：页，1页=4KB）
        cursor.execute("PRAGMA cache_size = -5000")  # 缓存20MB（可根据内存调整）
        
        print("成功连接到数据库")
        
        # 检查必要表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dictionary'")
        if not cursor.fetchone():
            print("错误：dictionary表不存在！")
            return
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='raw'")
        if not cursor.fetchone():
            print("错误：raw表不存在！")
            return
        
        # 检查dictionary表字段
        cursor.execute("PRAGMA table_info(dictionary)")
        dict_columns = [col[1] for col in cursor.fetchall()]
        required_cols = ['words', 'count']
        for col in required_cols:
            if col not in dict_columns:
                print(f"错误：dictionary表中没有'{col}'字段！")
                return
        
        # 新增/检查variety字段（INTEGER类型，更高效）
        if 'variety' not in dict_columns:
            try:
                cursor.execute("ALTER TABLE dictionary ADD COLUMN variety INTEGER DEFAULT 0")
                print("提示：已自动添加 variety 字段（INTEGER类型）")
            except sqlite3.Error as e:
                print(f"添加variety字段失败: {e}")
                return
        
        # 1. 加载所有有效单词（过滤空值，建立ID映射）
        cursor.execute("""
            SELECT id, words FROM dictionary 
            WHERE words IS NOT NULL AND words != ''
        """)
        words = cursor.fetchall()
        if not words:
            print("dictionary表中没有有效单词数据")
            return
        
        # 构建单词映射：word_id → (原始单词, 小写单词)
        word_map = {}
        for word_id, word in words:
            word_map[word_id] = (word, word.lower())
        print(f"找到 {len(word_map)} 个有效单词")
        
        # 2. 初始化统计容器（内存占用低）
        total_counts = defaultdict(int)  # 单词总出现次数
        variety_counts = defaultdict(int)  # 单词出现的歌词记录数
        
        # 3. 分批读取歌词（避免一次性加载大量数据）
        batch_size = 50  # 每批处理50条（低配电脑可再减小至20-30）
        cursor.execute("""
            SELECT id, lyric_raw FROM raw 
            WHERE lyric_raw IS NOT NULL AND lyric_raw != ''
        """)
        
        processed_lyrics = 0
        while True:
            # 分批获取歌词
            lyric_batch = cursor.fetchmany(batch_size)
            if not lyric_batch:
                break
            
            # 处理当前批次歌词
            for lyric_id, lyric in lyric_batch:
                processed_lyrics += 1
                lyric_lower = lyric.lower()  # 只转一次小写，避免重复计算
                
                # 遍历所有单词，统计当前歌词中的出现情况
                for word_id, (word, word_lower) in word_map.items():
                    count = count_word_occurrences(lyric_lower, word_lower)
                    if count > 0:
                        total_counts[word_id] += count
                        variety_counts[word_id] += 1  # 同一歌词只计数一次
                        
                        #  verbose模式才打印详细信息（默认关闭）
                        if verbose:
                            print(f"\n歌词{lyric_id}: {lyric[:100]}..."  # 截断长歌词，减少IO
                                  f"\n  包含 {count} 个 '{word}'")
            
            # 每处理100条打印一次进度（减少IO操作）
            if processed_lyrics % 100 == 0:
                print(f"已处理 {processed_lyrics} 条歌词...")
        
        print(f"\n歌词处理完成，共处理 {processed_lyrics} 条有效歌词")
        
        # 4. 批量更新数据库（减少磁盘IO）
        update_data = []
        for word_id, (word, _) in word_map.items():
            total = total_counts.get(word_id, 0)
            variety = variety_counts.get(word_id, 0)
            update_data.append((total, variety, word_id))
            # 简化输出，只打印关键统计
            print(f"单词 '{word}'：总计 {total} 次，出现于 {variety} 条记录")
        
        # 执行批量更新
        if update_data:
            cursor.executemany("""
                UPDATE dictionary 
                SET count = ?, variety = ? 
                WHERE id = ?
            """, update_data)
            conn.commit()
            print(f"\n批量更新 {len(update_data)} 个单词的统计结果")
        else:
            print("\n没有需要更新的统计数据")
        
    except sqlite3.Error as e:
        print(f"\n数据库错误: {e}")
        if conn:
            conn.rollback()
    except Exception as e:
        print(f"\n程序错误: {e}")
    finally:
        if conn:
            conn.close()
            print("\n数据库连接已关闭")

if __name__ == "__main__":
    # 默认关闭verbose模式（减少IO），需要详细输出可改为 main(verbose=True)
    main(verbose=False)
