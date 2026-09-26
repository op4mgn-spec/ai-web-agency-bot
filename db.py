import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "agency.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Leads / Clients table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            status TEXT DEFAULT 'NEW',  -- NEW, BRIEFING, PAID, GENERATED, REVIEW, COMPLETED
            brief_data TEXT DEFAULT '{}',
            site_url TEXT DEFAULT '',
            site_path TEXT DEFAULT '',
            feedback TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Form Submissions Log
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS form_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_url TEXT,
            company_name TEXT,
            status TEXT,  -- SUCCESS, FAILED
            error_message TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def get_or_create_lead(telegram_id: int, username: str = "", full_name: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute(
            "INSERT INTO leads (telegram_id, username, full_name, status) VALUES (?, ?, ?, 'NEW')",
            (telegram_id, username or "", full_name or "")
        )
        conn.commit()
        cursor.execute("SELECT * FROM leads WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
    conn.close()
    return dict(row)

def update_lead_status(telegram_id: int, status: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE leads SET status = ?, updated_at = ? WHERE telegram_id = ?",
        (status, datetime.now().isoformat(), telegram_id)
    )
    conn.commit()
    conn.close()

def update_lead_brief(telegram_id: int, brief_dict: dict):
    conn = get_connection()
    cursor = conn.cursor()
    brief_json = json.dumps(brief_dict, ensure_ascii=False)
    cursor.execute(
        "UPDATE leads SET brief_data = ?, updated_at = ? WHERE telegram_id = ?",
        (brief_json, datetime.now().isoformat(), telegram_id)
    )
    conn.commit()
    conn.close()

def save_generated_site(telegram_id: int, site_url: str, site_path: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE leads SET site_url = ?, site_path = ?, status = 'GENERATED', updated_at = ? WHERE telegram_id = ?",
        (site_url, site_path, datetime.now().isoformat(), telegram_id)
    )
    conn.commit()
    conn.close()

def add_lead_feedback(telegram_id: int, feedback_text: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE leads SET feedback = ?, status = 'REVIEW', updated_at = ? WHERE telegram_id = ?",
        (feedback_text, datetime.now().isoformat(), telegram_id)
    )
    conn.commit()
    conn.close()

def log_form_submission(target_url: str, company_name: str, status: str, error_message: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO form_submissions (target_url, company_name, status, error_message) VALUES (?, ?, ?, ?)",
        (target_url, company_name, status, error_message)
    )
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
