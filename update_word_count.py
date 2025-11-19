import sqlite3
import os
import re

def main():
    # 数据库文件路径
    db_path = os.path.join(os.path.dirname(__file__), 'translated.db')
    
    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        print(f"错误：数据库文件 '{db_path}' 不存在！")
        return
    
    conn = None
    try:
        # 连接到数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("成功连接到数据库")
        
        # 检查dictionary表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dictionary'")
        if not cursor.fetchone():
            print("错误：dictionary表不存在！")
            conn.close()
            return
        
        # 检查raw表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='raw'")
        if not cursor.fetchone():
            print("错误：raw表不存在！")
            conn.close()
            return
        
        # 检查dictionary表的字段
        cursor.execute("PRAGMA table_info(dictionary)")
        dict_columns = [col[1] for col in cursor.fetchall()]
        if 'words' not in dict_columns:
            print("错误：dictionary表中没有words字段！")
            conn.close()
            return
        if 'count' not in dict_columns:
            print("错误：dictionary表中没有count字段！")
            conn.close()
            return

        # 如果 variety 字段不存在，就添加（类型为 TEXT）
        if 'variety' not in dict_columns:
            try:
                cursor.execute("ALTER TABLE dictionary ADD COLUMN variety TEXT")
                # 立即刷新列信息（可选）
                cursor.execute("PRAGMA table_info(dictionary)")
                dict_columns = [col[1] for col in cursor.fetchall()]
                print("提示：dictionary 表中缺少 variety 字段，已自动添加 variety (TEXT)。")
            except sqlite3.Error as e:
                print(f"尝试添加 variety 字段时出错: {e}")
                conn.close()
                return
        
        # 检查raw表的字段
        cursor.execute("PRAGMA table_info(raw)")
        raw_columns = [col[1] for col in cursor.fetchall()]
        if 'lyric_raw' not in raw_columns:
            print("错误：raw表中没有lyric_raw字段！")
            conn.close()
            return
        
        # 获取dictionary表中的所有单词
        cursor.execute("SELECT id, words FROM dictionary")
        words = cursor.fetchall()
        
        if not words:
            print("dictionary表中没有数据")
            conn.close()
            return
        
        print(f"找到 {len(words)} 个单词需要统计")
        
        # 获取所有歌词
        cursor.execute("SELECT id, lyric_raw FROM raw")
        all_lyrics = cursor.fetchall()
        print(f"从数据库中获取了 {len(all_lyrics)} 条歌词")
        
        # 逐个单词进行统计
        for word_id, word in words:
            try:
                print(f"\n处理单词: '{word}'")
                
                # 统计单词在所有歌词中出现的总次数（原有功能）
                total_count = 0
                # 统计单词出现于多少条不同歌词记录（新增功能）
                variety_count = 0
                
                word_lower = (word or "").lower()
                pattern = r'\b' + re.escape(word_lower) + r'\b'
                
                for lyric_id, lyric in all_lyrics:
                    lyric_text = lyric or ""
                    # 将歌词转为小写进行不区分大小写的匹配
                    lyric_lower = lyric_text.lower()
                    
                    # 使用正则表达式匹配单词边界
                    matches = re.findall(pattern, lyric_lower)
                    count_in_lyric = len(matches)
                    
                    if count_in_lyric > 0:
                        # 原有详细输出
                        print(f"  歌词{lyric_id}: '{lyric_text}'")
                        print(f"    - 包含 {count_in_lyric} 个 '{word}'")
                        total_count += count_in_lyric
                        # 如果该歌词至少出现一次，则计入 variety（不同记录数）
                        variety_count += 1
                
                # 更新dictionary表中的count字段（保持原有功能）
                # 并将新增的 variety_count 写入 variety 字段（以 text 形式保存）
                cursor.execute("""
                    UPDATE dictionary 
                    SET count = ?, variety = ?
                    WHERE id = ?
                """, (total_count, str(variety_count), word_id))
                
                print(f"  单词 '{word}' 总计出现次数: {total_count}")
                print(f"  单词 '{word}' 出现在 {variety_count} 条不同的 lyric_raw 记录中 (已写入 variety)")
                
            except Exception as e:
                print(f"处理单词 '{word}' 时出错: {e}")
        
        # 提交事务
        conn.commit()
        print("\n所有单词统计完成并已更新到数据库")
        
    except sqlite3.Error as e:
        print(f"\n数据库操作错误: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            print("\n数据库连接已关闭")

if __name__ == "__main__":
    main()
