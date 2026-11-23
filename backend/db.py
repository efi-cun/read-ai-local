import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from .config import DB_PATH

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db_connection()
    with conn:
        # Meetings
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                duration_seconds REAL DEFAULT 0,
                status TEXT DEFAULT 'live',
                audio_path TEXT,
                summary TEXT,
                key_topics TEXT,
                meet_code TEXT
            )
        """)
        # Participants (Attendance)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id TEXT NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                entry_time TEXT,
                exit_time TEXT,
                duration_seconds REAL DEFAULT 0,
                status TEXT DEFAULT 'Presente',
                talk_time_seconds REAL DEFAULT 0,
                talk_percentage REAL DEFAULT 0,
                FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
            )
        """)
        # Transcripts
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id TEXT NOT NULL,
                speaker TEXT NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                text TEXT NOT NULL,
                sentiment TEXT DEFAULT 'neutral',
                FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
            )
        """)
        # Action Items
        conn.execute("""
            CREATE TABLE IF NOT EXISTS action_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id TEXT NOT NULL,
                task TEXT NOT NULL,
                assignee TEXT DEFAULT 'Equipo',
                completed INTEGER DEFAULT 0,
                FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
            )
        """)
        # Rosters (Listas de Asistentes Predefinidas)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rosters (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                members_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Settings (Configuración de Calendario y Sistema)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
    conn.close()

# CRUD helpers
def create_meeting(meeting_id: str, title: str, meet_code: str = "") -> Dict[str, Any]:
    conn = get_db_connection()
    with conn:
        conn.execute(
            "INSERT INTO meetings (id, title, meet_code, status) VALUES (?, ?, ?, 'live')",
            (meeting_id, title, meet_code)
        )
    conn.close()
    return get_meeting(meeting_id)

def get_meeting(meeting_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def list_meetings() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM meetings ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_meeting_participants(meeting_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM participants WHERE meeting_id = ? ORDER BY entry_time ASC", (meeting_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_meeting_transcripts(meeting_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM transcripts WHERE meeting_id = ? ORDER BY start_time ASC", (meeting_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_meeting_action_items(meeting_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM action_items WHERE meeting_id = ?", (meeting_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]
