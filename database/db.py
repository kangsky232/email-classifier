import os
from config import Config

USE_SQLITE = os.getenv('USE_SQLITE', 'true').lower() == 'true'

if USE_SQLITE:
    import sqlite3
    
    class Database:
        def __init__(self):
            self.connection = None
            self.connect()
        
        def connect(self):
            try:
                db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mail_system.db')
                self.connection = sqlite3.connect(db_path, check_same_thread=False)
                self.connection.row_factory = sqlite3.Row
                self.connection.execute("PRAGMA foreign_keys = ON")
                self._init_tables()
            except Exception as e:
                print(f"SQLite连接失败: {e}")
                self.connection = None
        
        def _init_tables(self):
            sql_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'init.sql')
            if os.path.exists(sql_file):
                with open(sql_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    content = content.replace('INT PRIMARY KEY AUTO_INCREMENT', 'INTEGER PRIMARY KEY AUTOINCREMENT')
                    content = content.replace('JSON', 'TEXT')
                    content = content.replace('ON UPDATE CURRENT_TIMESTAMP', '')
                    content = content.replace('ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)', 'ON CONFLICT(config_key) DO UPDATE SET config_value = excluded.config_value')
                    content = content.replace('ENGINE=InnoDB', '')
                    content = content.replace('DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci', '')
                    for stmt in content.split(';'):
                        stmt = stmt.strip()
                        if stmt and not stmt.startswith('--'):
                            upper = stmt.upper()
                            if 'CREATE DATABASE' in upper or upper.startswith('USE '):
                                continue
                            try:
                                self.connection.execute(stmt)
                            except Exception:
                                pass
                self.connection.commit()
        
        def execute(self, sql, params=None):
            if not self.connection:
                self.connect()
            try:
                sql = sql.replace('%s', '?')
                cursor = self.connection.cursor()
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                self.connection.commit()
                return cursor
            except Exception as e:
                print(f"执行SQL失败: {e}")
                raise
        
        def fetch_one(self, sql, params=None):
            cursor = self.execute(sql, params)
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        
        def fetch_all(self, sql, params=None):
            cursor = self.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        
        def close(self):
            if self.connection:
                self.connection.close()
else:
    import pymysql
    
    class Database:
        def __init__(self):
            self.connection = None
            self.connect()
        
        def connect(self):
            try:
                self.connection = pymysql.connect(
                    host=Config.DB_HOST,
                    port=Config.DB_PORT,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD,
                    database=Config.DB_NAME,
                    charset='utf8mb4',
                    cursorclass=pymysql.cursors.DictCursor
                )
            except Exception as e:
                print(f"数据库连接失败: {e}")
                self.connection = None
        
        def execute(self, sql, params=None):
            if not self.connection:
                self.connect()
            try:
                with self.connection.cursor() as cursor:
                    cursor.execute(sql, params)
                    self.connection.commit()
                    return cursor
            except Exception as e:
                print(f"执行SQL失败: {e}")
                self.connection.rollback()
                raise
        
        def fetch_one(self, sql, params=None):
            cursor = self.execute(sql, params)
            return cursor.fetchone()
        
        def fetch_all(self, sql, params=None):
            cursor = self.execute(sql, params)
            return cursor.fetchall()
        
        def close(self):
            if self.connection:
                self.connection.close()

db = Database()
