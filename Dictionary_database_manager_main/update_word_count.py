import sqlite3
import os
import re
import logging
from collections import defaultdict

# 配置日志
logging.basicConfig(
    filename='update_word_count.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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

def validate_data(conn):
    """验证数据并输出异常记录"""
    cursor = conn.cursor()
    exceptions = []
    
    try:
        # 1. 检查count=0且variety=0的记录
        cursor.execute("""
            SELECT id, words, explanation, count, variety, class
            FROM dictionary
            WHERE count = 0 AND variety = 0
        """)
        zero_records = cursor.fetchall()
        for record in zero_records:
            exceptions.append({
                'id': record[0],
                'words': record[1],
                'explanation': record[2],
                'count': record[3],
                'variety': record[4],
                'class': record[5],
                'reason': 'count和variety字段值都为0'
            })
        
        # 2. 检查words字段包含非英文字符的记录
        cursor.execute("SELECT id, words, explanation, count, variety, class FROM dictionary")
        all_records = cursor.fetchall()
        for record in all_records:
            word = record[1]
            if not re.match(r'^[a-zA-Z]+$', word):
                exceptions.append({
                    'id': record[0],
                    'words': record[1],
                    'explanation': record[2],
                    'count': record[3],
                    'variety': record[4],
                    'class': record[5],
                    'reason': 'words字段包含非英文字符'
                })
        
        # 3. 检查class字段包含除句号外其他字符的记录
        for record in all_records:
            class_val = record[5]
            if class_val:
                # 检查是否包含除句号外的其他字符
                if re.search(r'[^.]', class_val):
                    exceptions.append({
                        'id': record[0],
                        'words': record[1],
                        'explanation': record[2],
                        'count': record[3],
                        'variety': record[4],
                        'class': record[5],
                        'reason': 'class字段包含除句号外的其他字符'
                    })
        
        # 输出异常记录
        if exceptions:
            print("=== 数据异常记录 ===")
            for exception in exceptions:
                print(f"ID: {exception['id']}")
                print(f"单词: {exception['words']}")
                print(f"解释: {exception['explanation']}")
                print(f"计数: {exception['count']}")
                print(f"出现记录数: {exception['variety']}")
                print(f"类别: {exception['class']}")
                print(f"异常原因: {exception['reason']}")
                print("-" * 50)
        logging.info(f"数据验证完成，共发现 {len(exceptions)} 条异常记录")
    except sqlite3.Error as e:
        logging.error(f"数据验证过程中发生数据库错误: {e}")
    except Exception as e:
        logging.error(f"数据验证过程中发生错误: {e}")

def main(verbose=False):
    # 询问用户选择运行模式
    print("请选择运行模式：")
    print("1. 运行全部功能（包括单词计数更新、ID重新排序、class字段规范化等）")
    print("2. 仅处理数据库并输出异常记录")
    
    choice = input("请输入您的选择（1或2）：").strip()
    
    # 数据库文件路径
    db_path = os.path.join(os.path.dirname(__file__), 'translated.db')
    
    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        logging.error(f"数据库文件 '{db_path}' 不存在")
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
        
        logging.info("成功连接到数据库")
        
        # 检查必要表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dictionary'")
        if not cursor.fetchone():
            logging.error("dictionary表不存在")
            return
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='raw'")
        if not cursor.fetchone():
            logging.error("raw表不存在")
            return
        
        # 检查dictionary表字段
        cursor.execute("PRAGMA table_info(dictionary)")
        dict_columns = [col[1] for col in cursor.fetchall()]
        required_cols = ['words', 'count']
        for col in required_cols:
            if col not in dict_columns:
                logging.error(f"dictionary表中没有'{col}'字段")
                return
        
        # 新增/检查variety字段（INTEGER类型，更高效）
        if 'variety' not in dict_columns:
            try:
                cursor.execute("ALTER TABLE dictionary ADD COLUMN variety INTEGER DEFAULT 0")
                logging.info("已自动添加 variety 字段（INTEGER类型）")
            except sqlite3.Error as e:
                logging.error(f"添加variety字段失败: {e}")
                return
        else:
            # 检查并修复variety字段类型（从TEXT改为INTEGER）
            cursor.execute("PRAGMA table_info(dictionary)")
            for col in cursor.fetchall():
                if col[1] == 'variety' and col[2] != 'INTEGER':
                    # 创建临时表
                    cursor.execute("""
                        CREATE TABLE dictionary_temp (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            words TEXT NOT NULL,
                            explanation TEXT,
                            count INTEGER DEFAULT 0,
                            variety INTEGER DEFAULT 0,
                            class TEXT
                        )
                    """)
                    # 复制数据到临时表
                    cursor.execute("""
                        INSERT INTO dictionary_temp (words, explanation, count, variety, class)
                        SELECT words, explanation, count, CAST(variety AS INTEGER), class
                        FROM dictionary
                    """)
                    # 删除原表
                    cursor.execute("DROP TABLE dictionary")
                    # 重命名临时表
                    cursor.execute("ALTER TABLE dictionary_temp RENAME TO dictionary")
                    logging.info("已将variety字段类型从TEXT改为INTEGER")
                    break
        
        # 如果选择仅处理数据库并输出异常记录（选项2）
        if choice == '2':
            # 数据验证与异常记录输出
            validate_data(conn)
            logging.info("仅处理数据库并输出异常记录完成")
            return
        
        # 以下是全部功能（选项1）的处理逻辑
        # 1. 加载所有有效单词（过滤空值，建立ID映射）
        cursor.execute("""
            SELECT id, words FROM dictionary 
            WHERE words IS NOT NULL AND words != ''
        """)
        words = cursor.fetchall()
        if not words:
            logging.info("dictionary表中没有有效单词数据")
            return
        
        # 构建单词映射：word_id → (原始单词, 小写单词)
        word_map = {}
        for word_id, word in words:
            word_map[word_id] = (word, word.lower())
        logging.info(f"找到 {len(word_map)} 个有效单词")
        
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
        
        logging.info(f"歌词处理完成，共处理 {processed_lyrics} 条有效歌词")
        
        # 4. 批量更新数据库（减少磁盘IO）
        update_data = []
        for word_id, (word, _) in word_map.items():
            total = total_counts.get(word_id, 0)
            variety = variety_counts.get(word_id, 0)
            update_data.append((total, variety, word_id))
        
        # 执行批量更新
        if update_data:
            cursor.executemany("""
                UPDATE dictionary 
                SET count = ?, variety = ? 
                WHERE id = ?
            """, update_data)
            conn.commit()
            logging.info(f"批量更新 {len(update_data)} 个单词的统计结果")
        else:
            logging.info("没有需要更新的统计数据")
        
        # 5. 数据验证与异常记录输出
        validate_data(conn)
        
        # 6. ID字段重新排序
        cursor.execute("""
            CREATE TABLE dictionary_temp (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                words TEXT NOT NULL,
                explanation TEXT,
                count INTEGER DEFAULT 0,
                variety INTEGER DEFAULT 0,
                class TEXT
            )
        """)
        cursor.execute("""
            INSERT INTO dictionary_temp (words, explanation, count, variety, class)
            SELECT words, explanation, count, variety, class
            FROM dictionary
            ORDER BY id
        """)
        cursor.execute("DROP TABLE dictionary")
        cursor.execute("ALTER TABLE dictionary_temp RENAME TO dictionary")
        logging.info("ID字段重新排序完成")
        
        # 7. class字段规范化处理
        cursor.execute("""
            UPDATE dictionary
            SET class = class || '.'
            WHERE class IS NOT NULL AND class != '' AND SUBSTR(class, -1) != '.'
        """)
        conn.commit()
        logging.info("class字段规范化处理完成")
        
    except sqlite3.Error as e:
        logging.error(f"数据库错误: {e}")
        if conn:
            conn.rollback()
    except Exception as e:
        logging.error(f"程序错误: {e}")
    finally:
        if conn:
            conn.close()
            logging.info("数据库连接已关闭")

if __name__ == "__main__":
    # 默认关闭verbose模式（减少IO），需要详细输出可改为 main(verbose=True)
    main(verbose=False)
