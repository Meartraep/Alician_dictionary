# debug_search_test.py
from database_manager import DatabaseManager

db = DatabaseManager()
ok = db.connect_database("translated.db")   # 或者你实际的 .db 文件名/路径
print("connect_database returned:", ok)
print("db_file:", db.db_file)
print("conn is None?", db.conn is None)
print("tables:", db.get_tables())
print("all text fields (sample):", db.get_all_text_fields())

# 尝试搜索一个你知道存在的词
res = db.global_search("AA", exact_match=False)
print("global_search returned count:", len(res))
for r in res[:10]:
    print(r)
