import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'chat_history.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_chat_history_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_message(session_id, role, content):
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO chat_history (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)',
        (session_id, role, content, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

def get_chat_history(session_id):
    conn = get_db_connection()
    cursor = conn.execute(
        'SELECT role, content, timestamp FROM chat_history WHERE session_id = ? ORDER BY id',
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
