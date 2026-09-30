"""数据库模型 — 使用 SQLite + 原生 sqlite3 零依赖"""

import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            weekday INTEGER NOT NULL,
            time TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL DEFAULT 180,
            notify_after_minutes INTEGER NOT NULL DEFAULT 5,
            dept_id INTEGER,
            enabled INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT NOT NULL,
            class_date TEXT NOT NULL,
            class_start_time TEXT NOT NULL,
            student_name TEXT NOT NULL,
            student_user_id TEXT NOT NULL,
            check_in_time TEXT,
            status TEXT NOT NULL DEFAULT 'absent',
            department TEXT DEFAULT '',
            job_number TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS notify_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT NOT NULL,
            channel TEXT NOT NULL,
            content TEXT NOT NULL,
            success INTEGER NOT NULL DEFAULT 1,
            sent_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
    """)

    # 兼容旧数据库：添加新列（如已存在则忽略）
    try:
        conn.execute("ALTER TABLE attendance_records ADD COLUMN department TEXT DEFAULT ''")
    except:
        pass
    try:
        conn.execute("ALTER TABLE attendance_records ADD COLUMN job_number TEXT DEFAULT ''")
    except:
        pass
    try:
        conn.execute("ALTER TABLE attendance_records ADD COLUMN manual_note TEXT DEFAULT ''")
    except:
        pass
    conn.commit()
    conn.close()


@contextmanager
def db_session():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
