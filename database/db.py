import os
import re

from config import Config


USE_SQLITE = os.getenv("USE_SQLITE", "true").lower() == "true"


class Database:
    def __init__(self):
        self.connection = None
        self.is_sqlite = USE_SQLITE
        self.connect()

    def connect(self):
        if self.is_sqlite:
            self._connect_sqlite()
        else:
            self._connect_mysql()

    def _connect_sqlite(self):
        import sqlite3

        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mail_system.db")
        self.connection = sqlite3.connect(db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._init_sqlite_tables()

    def _connect_mysql(self):
        import pymysql

        self.connection = pymysql.connect(
            host=Config.DB_HOST,
            port=int(Config.DB_PORT),
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            charset="utf8mb4",
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor,
        )

    def _init_sqlite_tables(self):
        sql_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "init.sql")
        if not os.path.exists(sql_file):
            return

        with open(sql_file, "r", encoding="utf-8") as f:
            content = self._mysql_sql_to_sqlite(f.read())

        for stmt in self._split_sql(content):
            upper = stmt.upper()
            if not stmt or upper.startswith("CREATE DATABASE") or upper.startswith("USE "):
                continue
            try:
                self.connection.execute(stmt)
            except Exception as exc:
                print(f"SQLite init skipped statement: {exc}")
        self.connection.commit()

    def _mysql_sql_to_sqlite(self, content):
        content = re.sub(
            r"INT\s+PRIMARY\s+KEY\s+AUTO_INCREMENT",
            "INTEGER PRIMARY KEY AUTOINCREMENT",
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(r"\bJSON\b", "TEXT", content, flags=re.IGNORECASE)
        content = re.sub(
            r"\s+ON\s+UPDATE\s+CURRENT_TIMESTAMP",
            "",
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(
            r"ON\s+DUPLICATE\s+KEY\s+UPDATE\s+config_value\s*=\s*VALUES\(config_value\)",
            "ON CONFLICT(config_key) DO UPDATE SET config_value = excluded.config_value",
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(
            r"DEFAULT\s+CHARACTER\s+SET\s+\w+\s+COLLATE\s+\w+",
            "",
            content,
            flags=re.IGNORECASE,
        )
        return content

    def _split_sql(self, content):
        statements = []
        current = []
        in_string = False
        quote = ""

        for char in content:
            if char in ("'", '"'):
                if not in_string:
                    in_string = True
                    quote = char
                elif quote == char:
                    in_string = False
            if char == ";" and not in_string:
                statements.append("".join(current).strip())
                current = []
            else:
                current.append(char)

        tail = "".join(current).strip()
        if tail:
            statements.append(tail)
        return statements

    def _ensure_connection(self):
        if self.connection is None:
            self.connect()
        elif not self.is_sqlite:
            self.connection.ping(reconnect=True)

    def _adapt_sql(self, sql):
        if self.is_sqlite:
            return sql.replace("%s", "?")
        return sql

    def execute(self, sql, params=None):
        self._ensure_connection()
        cursor = self.connection.cursor()
        try:
            cursor.execute(self._adapt_sql(sql), params or ())
            self.connection.commit()
            return cursor
        except Exception:
            self.connection.rollback()
            cursor.close()
            raise

    def fetch_one(self, sql, params=None):
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        cursor.close()
        if row is None:
            return None
        return dict(row) if self.is_sqlite else row

    def fetch_all(self, sql, params=None):
        cursor = self.execute(sql, params)
        rows = cursor.fetchall()
        cursor.close()
        if self.is_sqlite:
            return [dict(row) for row in rows]
        return rows

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None


db = Database()
