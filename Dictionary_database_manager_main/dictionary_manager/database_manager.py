import sqlite3
from sqlite3 import Error
import glob
import os

class DatabaseManager:
    def __init__(self):
        self.conn = None
        self.db_file = None
        # 获取项目根目录路径（Dictionary_database_manager_main的父目录）
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        
    def connect_database(self, db_file):
        """连接到数据库"""
        try:
            # 构建完整的数据库文件路径（相对于项目根目录）
            if not os.path.isabs(db_file):
                self.db_file = os.path.join(self.project_root, db_file)
            else:
                self.db_file = db_file
            self.conn = sqlite3.connect(self.db_file)
            return True
        except Error as e:
            print(f"无法连接到数据库: {e}")
            return False
    
    def close_connection(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.db_file = None
    
    def get_tables(self):
        """获取数据库中所有表"""
        if not self.conn:
            return []
            
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = cursor.fetchall()
            return [table[0] for table in tables]
        except Error as e:
            print(f"加载表失败: {e}")
            return []
    
    def get_fields(self, table_name):
        """从数据库加载指定表的字段名称"""
        if not self.conn or not table_name:
            return []
            
        try:
            cursor = self.conn.cursor()
            # 查询表结构
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            # 提取字段名称（排除id字段）
            return [col[1] for col in columns if col[1] != 'id']
        except Error as e:
            print(f"加载字段失败: {e}")
            return []
    
    def create_table(self, table_name, fields):
        """创建新表"""
        if not self.conn or not table_name or not fields:
            return False
            
        try:
            cursor = self.conn.cursor()
            
            # 构建CREATE TABLE语句
            fields_def = ", ".join([f'"{field}" TEXT' for field in fields])
            create_table_sql = f'''
                CREATE TABLE {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    {fields_def},
                    UNIQUE("{fields[0]}") -- 第一个字段作为唯一键
                )
            '''
            cursor.execute(create_table_sql)
            self.conn.commit()
            return True
        except Error as e:
            print(f"创建表失败: {e}")
            return False
    
    def drop_table(self, table_name):
        """删除指定表"""
        if not self.conn or not table_name:
            return False
            
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"DROP TABLE {table_name}")
            self.conn.commit()
            return True
        except Error as e:
            print(f"删除表失败: {e}")
            return False
    
    def rename_table(self, old_name, new_name):
        """重命名表"""
        if not self.conn or not old_name or not new_name:
            return False
            
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"ALTER TABLE {old_name} RENAME TO {new_name}")
            self.conn.commit()
            return True
        except Error as e:
            print(f"重命名表失败: {e}")
            return False
    
    def add_field(self, table_name, field_name):
        """添加新字段"""
        if not self.conn or not table_name or not field_name:
            return False
            
        try:
            cursor = self.conn.cursor()
            # 添加新字段（SQLite 3.35.0+支持）
            cursor.execute(f'ALTER TABLE {table_name} ADD COLUMN "{field_name}" TEXT')
            self.conn.commit()
            return True
        except Error as e:
            # 处理旧版本SQLite不支持ADD COLUMN的情况
            if "near \"ADD\": syntax error" in str(e):
                return self.add_field_compatibility_mode(table_name, field_name)
            else:
                print(f"添加字段失败: {e}")
                return False
    
    def add_field_compatibility_mode(self, table_name, field_name):
        """兼容旧版本SQLite的添加字段方法"""
        try:
            # 1. 创建临时表
            cursor = self.conn.cursor()
            
            # 获取当前表结构
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            # 构建新表结构（包含所有旧字段和新字段）
            new_columns = []
            for col in columns:
                new_columns.append(f'"{col[1]}" {col[2]}')
            
            # 添加新字段
            new_columns.append(f'"{field_name}" TEXT')
            
            # 创建临时表
            cursor.execute(f'''
                CREATE TABLE temp_table (
                    {", ".join(new_columns)}
                )
            ''')
            
            # 2. 复制数据到临时表
            all_columns = [f'"{col[1]}"' for col in columns]
            cursor.execute(f'''
                INSERT INTO temp_table ({", ".join(all_columns)})
                SELECT {", ".join(all_columns)} FROM {table_name}
            ''')
            
            # 3. 删除原表
            cursor.execute(f"DROP TABLE {table_name}")
            
            # 4. 重命名临时表
            cursor.execute(f"ALTER TABLE temp_table RENAME TO {table_name}")
            
            self.conn.commit()
            return True
        except Error as e:
            print(f"兼容模式添加字段失败: {e}")
            return False
    
    def delete_field(self, table_name, field_name):
        """删除字段"""
        if not self.conn or not table_name or not field_name:
            return False
            
        try:
            # 尝试直接删除字段（SQLite 3.35.0+支持）
            cursor = self.conn.cursor()
            cursor.execute(f'ALTER TABLE {table_name} DROP COLUMN "{field_name}"')
            self.conn.commit()
            return True
        except Error as e:
            # 处理不支持DROP COLUMN的情况
            return self.delete_field_compatibility_mode(table_name, field_name)
    
    def delete_field_compatibility_mode(self, table_name, field_name):
        """兼容旧版本SQLite的删除字段方法"""
        try:
            # 1. 创建临时表（不包含要删除的字段）
            cursor = self.conn.cursor()
            
            # 获取当前表结构
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            # 构建新表结构（排除要删除的字段）
            new_columns = []
            remaining_columns = []
            
            for col in columns:
                if col[1] != field_name:
                    new_columns.append(f'"{col[1]}" {col[2]}')
                    remaining_columns.append(f'"{col[1]}"')
            
            # 创建临时表
            cursor.execute(f'''
                CREATE TABLE temp_table (
                    {", ".join(new_columns)}
                )
            ''')
            
            # 2. 复制数据到临时表（不包含要删除的字段）
            cursor.execute(f'''
                INSERT INTO temp_table ({", ".join(remaining_columns)})
                SELECT {", ".join(remaining_columns)} FROM {table_name}
            ''')
            
            # 3. 删除原表
            cursor.execute(f"DROP TABLE {table_name}")
            
            # 4. 重命名临时表
            cursor.execute(f"ALTER TABLE temp_table RENAME TO {table_name}")
            
            self.conn.commit()
            return True
        except Error as e:
            print(f"兼容模式删除字段失败: {e}")
            return False
    
    def rename_field(self, table_name, old_name, new_name):
        """重命名字段"""
        if not self.conn or not table_name or not old_name or not new_name:
            return False
            
        try:
            # 尝试直接重命名字段（SQLite 3.25.0+支持）
            cursor = self.conn.cursor()
            cursor.execute(f'ALTER TABLE {table_name} RENAME COLUMN "{old_name}" TO "{new_name}"')
            self.conn.commit()
            return True
        except Error as e:
            # 处理不支持RENAME COLUMN的情况
            return self.rename_field_compatibility_mode(table_name, old_name, new_name)
    
    def rename_field_compatibility_mode(self, table_name, old_name, new_name):
        """兼容旧版本SQLite的重命名字段方法"""
        try:
            # 1. 创建临时表（包含重命名后的字段）
            cursor = self.conn.cursor()
            
            # 获取当前表结构
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            # 构建新表结构（包含重命名后的字段）
            new_columns = []
            remaining_columns = []
            
            for col in columns:
                field_name = new_name if col[1] == old_name else col[1]
                new_columns.append(f'"{field_name}" {col[2]}')
                remaining_columns.append(f'"{col[1]}"')
            
            # 创建临时表
            cursor.execute(f'''
                CREATE TABLE temp_table (
                    {", ".join(new_columns)}
                )
            ''')
            
            # 2. 复制数据到临时表
            cursor.execute(f'''
                INSERT INTO temp_table ({", ".join([new_name if col[1] == old_name else col[1] for col in columns])})
                SELECT {", ".join(remaining_columns)} FROM {table_name}
            ''')
            
            # 3. 删除原表
            cursor.execute(f"DROP TABLE {table_name}")
            
            # 4. 重命名临时表
            cursor.execute(f"ALTER TABLE temp_table RENAME TO {table_name}")
            
            self.conn.commit()
            return True
        except Error as e:
            print(f"兼容模式重命名字段失败: {e}")
            return False
    
    def table_exists(self, table_name):
        """检查表是否存在"""
        if not self.conn or not table_name:
            return False
            
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            return cursor.fetchone() is not None
        except Error as e:
            print(f"检查表名失败: {e}")
            return False
    
    def get_all_db_files(self):
        """获取项目根目录下所有的.db文件"""
        # 搜索项目根目录下的所有.db文件
        db_files = glob.glob(os.path.join(self.project_root, "*.db"))
        # 返回仅包含文件名的列表，不包含路径
        return [os.path.basename(db_file) for db_file in db_files]
    
    def execute_query(self, query, params=None):
        """执行SQL查询"""
        if not self.conn:
            return None
            
        try:
            cursor = self.conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor
        except Error as e:
            print(f"执行查询失败: {e}")
            return None
    
    def commit(self):
        """提交事务"""
        if self.conn:
            try:
                self.conn.commit()
                return True
            except Error as e:
                print(f"提交事务失败: {e}")
                return False
        return False
    
    def get_all_text_fields(self):
        """获取所有表的所有文本字段"""
        if not self.conn:
            return []
            
        tables = self.get_tables()
        all_fields = []
        
        for table in tables:
            fields = self.get_fields(table)
            if fields:
                all_fields.append((table, fields))
        
        return all_fields
    
    def global_search(self, keyword):
        """全局搜索所有表的所有字段"""
        if not self.conn or not keyword:
            print(f"全局搜索参数无效: conn={self.conn}, keyword={keyword}")
            return []
            
        results = []
        all_fields = self.get_all_text_fields()
        
        print(f"开始全局搜索: keyword='{keyword}', 表字段列表={all_fields}")
        
        for table, fields in all_fields:
            # 构建搜索条件，搜索所有字段
            where_clause = " OR ".join([f'"{field}" LIKE ?' for field in fields])
            query = f"SELECT id, {', '.join([f'"{field}"' for field in fields])} FROM {table} WHERE {where_clause}"
            
            try:
                cursor = self.conn.cursor()
                params = [f'%{keyword}%'] * len(fields)
                print(f"执行搜索: table={table}, query={query}, params={params}")
                cursor.execute(query, params)
                rows = cursor.fetchall()
                print(f"搜索表 {table} 找到 {len(rows)} 行数据")
                
                # 处理搜索结果
                for row in rows:
                    row_id = row[0]
                    for i, field in enumerate(fields):
                        field_value = row[i+1]
                        if field_value and keyword in str(field_value):
                            results.append({
                                'table': table,
                                'id': row_id,
                                'field': field,
                                'value': field_value
                            })
                            print(f"  匹配到: table={table}, id={row_id}, field={field}, value='{field_value}'")
            except Error as e:
                print(f"搜索表 {table} 失败: {e}")
                continue
        
        print(f"全局搜索完成，共找到 {len(results)} 个匹配项")
        return results
    
    def global_replace(self, keyword, replacement, match_records):
        """全局替换所有匹配的内容"""
        if not self.conn or not keyword or not replacement:
            print("替换参数不完整")
            return 0, []
            
        replaced_count = 0
        replaced_records = []
        
        try:
            print(f"开始全局替换: 查找='{keyword}', 替换为='{replacement}', 匹配记录数={len(match_records)}")
            
            # 开始事务
            self.conn.execute('BEGIN TRANSACTION')
            print("事务已开始")
            
            # 按表分组处理替换
            table_groups = {}
            for record in match_records:
                table = record['table']
                if table not in table_groups:
                    table_groups[table] = []
                table_groups[table].append(record)
            
            print(f"按表分组完成，共 {len(table_groups)} 个表需要处理")
            
            for table, records in table_groups.items():
                print(f"处理表: {table}, 记录数={len(records)}")
                
                # 按字段分组
                field_groups = {}
                for record in records:
                    field = record['field']
                    if field not in field_groups:
                        field_groups[field] = []
                    field_groups[field].append(record)
                
                for field, records in field_groups.items():
                    print(f"  处理字段: {field}, 记录数={len(records)}")
                    
                    # 构建更新语句
                    update_query = f"UPDATE {table} SET \"{field}\" = REPLACE(\"{field}\", ?, ?) WHERE id = ?"
                    print(f"  SQL: {update_query}")
                    
                    for record in records:
                        try:
                            cursor = self.conn.cursor()
                            cursor.execute(update_query, (keyword, replacement, record['id']))
                            
                            if cursor.rowcount > 0:
                                replaced_count += 1
                                new_value = record['value'].replace(keyword, replacement)
                                replaced_records.append({
                                    'table': table,
                                    'id': record['id'],
                                    'field': field,
                                    'old_value': record['value'],
                                    'new_value': new_value
                                })
                                print(f"    成功更新记录 {record['id']}: {record['value']} -> {new_value}")
                            else:
                                print(f"    记录 {record['id']} 未更新，可能已被修改")
                        except Error as e:
                            print(f"    更新表 {table} 记录 {record['id']} 字段 {field} 失败: {e}")
                            raise
            
            # 提交事务
            self.conn.commit()
            print(f"事务已提交，共替换 {replaced_count} 个匹配项")
            return replaced_count, replaced_records
        except Exception as e:
            # 回滚事务
            self.conn.rollback()
            print(f"全局替换失败，事务已回滚: {e}")
            return 0, []