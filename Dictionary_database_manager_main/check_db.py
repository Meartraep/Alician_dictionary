import sqlite3

# 连接数据库
conn = sqlite3.connect('translated.db')
cursor = conn.cursor()

# 检查dictionary表结构
print('dictionary表结构:')
cursor.execute('PRAGMA table_info(dictionary)')
for col in cursor.fetchall():
    print(col)

# 检查raw表结构
print('\nraw表结构:')
cursor.execute('PRAGMA table_info(raw)')
for col in cursor.fetchall():
    print(col)

# 查看前5条dictionary记录
print('\ndictionary表前5条记录:')
cursor.execute('SELECT * FROM dictionary LIMIT 5')
for row in cursor.fetchall():
    print(row)

# 关闭连接
conn.close()