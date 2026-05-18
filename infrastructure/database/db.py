import logging
import os
import re
import threading
from collections import deque
from contextlib import contextmanager

from config.settings import Config

logger = logging.getLogger(__name__)

USE_SQLITE = os.getenv("USE_SQLITE", "true").lower() == "true"


class _MySQLPool:
    """A simple queue-based MySQL connection pool."""

    def __init__(self, pool_size, **connect_kwargs):
        self._pool_size = pool_size
        self._connect_kwargs = connect_kwargs
        self._pool = deque()
        self._lock = threading.Lock()
        self._all_connections = []
        self._closed = False

        for _ in range(pool_size):
            conn = self._create_connection()
            self._pool.append(conn)
            self._all_connections.append(conn)

        logger.info("MySQL connection pool initialized with %d connections", pool_size)

    def _create_connection(self):
        import pymysql

        return pymysql.connect(**self._connect_kwargs)

    def get_connection(self):
        with self._lock:
            if self._closed:
                raise RuntimeError("Connection pool is closed")
            if self._pool:
                return self._pool.popleft()
        # Pool exhausted -- create a temporary overflow connection
        logger.warning("Connection pool exhausted, creating overflow connection")
        return self._create_connection()

    def return_connection(self, conn):
        with self._lock:
            if self._closed:
                conn.close()
                return
            try:
                conn.ping(reconnect=True)
            except Exception:
                logger.warning("Dropping stale MySQL connection from pool")
                try:
                    conn.close()
                except Exception:
                    pass
                conn = self._create_connection()
                self._all_connections.append(conn)
            self._pool.append(conn)

    def close_all(self):
        with self._lock:
            self._closed = True
            for conn in self._all_connections:
                try:
                    conn.close()
                except Exception:
                    pass
            for conn in self._pool:
                try:
                    conn.close()
                except Exception:
                    pass
            self._pool.clear()
            self._all_connections.clear()
            logger.info("MySQL connection pool closed")


class Database:
    def __init__(self):
        self.is_sqlite = USE_SQLITE
        self._lock = threading.Lock()  # protects SQLite (single connection)
        self._pool = None              # MySQL pool
        self._sqlite_conn = None       # single SQLite connection
        self.connect()

    def connect(self):
        if self.is_sqlite:
            self._connect_sqlite()
        else:
            self._connect_mysql()

    def _connect_sqlite(self):
        import sqlite3

        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "mail_system.db")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        self._sqlite_conn = conn
        self._init_sqlite_tables()
        logger.info("SQLite database connected: %s", db_path)

    def _connect_mysql(self):
        self._pool = _MySQLPool(
            pool_size=getattr(Config, "DB_POOL_SIZE", 10),
            host=Config.DB_HOST,
            port=int(Config.DB_PORT),
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            charset="utf8mb4",
            autocommit=False,
            cursorclass=__import__("pymysql").cursors.DictCursor,
        )

    def _init_sqlite_tables(self):
        self._run_init_sql()
        self._migrate_sqlite()

    def _run_init_sql(self):
        sql_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "init.sql")
        if not os.path.exists(sql_file):
            return

        with open(sql_file, "r", encoding="utf-8") as f:
            content = self._mysql_sql_to_sqlite(f.read())

        for stmt in self._split_sql(content):
            upper = stmt.upper()
            if not stmt or upper.startswith("CREATE DATABASE") or upper.startswith("USE "):
                continue
            try:
                self._sqlite_conn.execute(stmt)
            except Exception as exc:
                logger.debug("SQLite init skipped statement: %s", exc)
        self._sqlite_conn.commit()

    def _migrate_sqlite(self):
        try:
            self._sqlite_conn.execute("ALTER TABLE emails ADD COLUMN user_id INTEGER")
        except Exception:
            pass
        self._sqlite_conn.commit()

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

    def _adapt_sql(self, sql):
        if self.is_sqlite:
            return sql.replace("%s", "?")
        return sql

    # ------------------------------------------------------------------
    # Connection acquisition / release (internal)
    # ------------------------------------------------------------------

    def _get_connection(self):
        if self.is_sqlite:
            # Single shared connection guarded by a lock
            if self._sqlite_conn is None:
                self._connect_sqlite()
            return self._sqlite_conn
        # MySQL -- borrow from pool
        return self._pool.get_connection()

    def _return_connection(self, conn):
        if self.is_sqlite:
            # Nothing to do -- the connection stays open
            return
        self._pool.return_connection(conn)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    @contextmanager
    def get_cursor(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            self._return_connection(conn)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, sql, params=None):
        if self.is_sqlite:
            with self._lock:
                with self.get_cursor() as cursor:
                    cursor.execute(self._adapt_sql(sql), params or ())
                    return cursor
        else:
            with self.get_cursor() as cursor:
                cursor.execute(self._adapt_sql(sql), params or ())
                return cursor

    def fetch_one(self, sql, params=None):
        if self.is_sqlite:
            with self._lock:
                with self.get_cursor() as cursor:
                    cursor.execute(self._adapt_sql(sql), params or ())
                    row = cursor.fetchone()
                    return dict(row) if row is not None else None
        else:
            with self.get_cursor() as cursor:
                cursor.execute(self._adapt_sql(sql), params or ())
                return cursor.fetchone()

    def fetch_all(self, sql, params=None):
        if self.is_sqlite:
            with self._lock:
                with self.get_cursor() as cursor:
                    cursor.execute(self._adapt_sql(sql), params or ())
                    rows = cursor.fetchall()
                    return [dict(row) for row in rows]
        else:
            with self.get_cursor() as cursor:
                cursor.execute(self._adapt_sql(sql), params or ())
                return cursor.fetchall()

    def close(self):
        if self.is_sqlite and self._sqlite_conn:
            self._sqlite_conn.close()
            self._sqlite_conn = None
            logger.info("SQLite connection closed")
        elif self._pool:
            self._pool.close_all()
            self._pool = None


db = Database()
