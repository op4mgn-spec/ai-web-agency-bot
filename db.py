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
            status TEXT DEFAULT 'NEW',
            brief_step INTEGER DEFAULT 0,
            brief_data TEXT DEFAULT '{}',
            bot_variant TEXT DEFAULT 'Variant A (Консультант)',
            site_url TEXT DEFAULT '',
            site_path TEXT DEFAULT '',
            feedback TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Migration for existing databases missing new columns
    for col, col_type in [
        ('brief_step', "INTEGER DEFAULT 0"),
        ('bot_variant', "TEXT DEFAULT 'Variant A (Консультант)'"),
        ('site_url', "TEXT DEFAULT ''"),
        ('site_path', "TEXT DEFAULT ''"),
        ('feedback', "TEXT DEFAULT ''")
    ]:
        try:
            cursor.execute(f"ALTER TABLE leads ADD COLUMN {col} {col_type}")
        except Exception:
            pass # Column already exists
    
    # Full Chat Dialog History table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            sender TEXT,
            text TEXT,
            bot_variant TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # A/B Test Stats table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_variants (
            name TEXT PRIMARY KEY,
            system_prompt TEXT,
            chats_count INTEGER DEFAULT 0,
            briefs_count INTEGER DEFAULT 0,
            sales_count INTEGER DEFAULT 0
        )
    ''')
    
    # Form Submissions Log
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS form_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_url TEXT,
            company_name TEXT,
            status TEXT,
            error_message TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Leads Queue Table (Outreach Queue & Timezone scheduling)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT,
            target_url TEXT UNIQUE,
            phone TEXT,
            city TEXT,
            timezone_offset INTEGER DEFAULT 3,
            status TEXT DEFAULT 'PENDING',
            scheduled_at TIMESTAMP,
            error_message TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def get_or_create_lead(telegram_id: int, username: str = "", full_name: str = ""):
    init_db() # Ensure schema migration
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("SELECT count(*) FROM leads")
        count = cursor.fetchone()[0]
        
        variants = [
            "Variant A (Консультант)",
            "Variant B (Прямые Продажи)",
            "Variant C (Демо-Специалист)",
            "Variant D (Архитектор Решений)"
        ]
        variant = variants[count % len(variants)]
        
        cursor.execute(
            "INSERT INTO leads (telegram_id, username, full_name, status, bot_variant) VALUES (?, ?, ?, 'NEW', ?)",
            (telegram_id, username or "", full_name or "", variant)
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

def update_brief_step(telegram_id: int, step: int):
    conn = get_connection()
    cursor = conn.cursor()
    status = "BRIEFING" if step > 0 and step < 7 else "INCOMPLETE_BRIEF"
    cursor.execute(
        "UPDATE leads SET brief_step = ?, status = ?, updated_at = ? WHERE telegram_id = ?",
        (step, status, datetime.now().isoformat(), telegram_id)
    )
    conn.commit()
    conn.close()

def update_lead_brief(telegram_id: int, brief_dict: dict):
    conn = get_connection()
    cursor = conn.cursor()
    brief_json = json.dumps(brief_dict, ensure_ascii=False)
    cursor.execute(
        "UPDATE leads SET brief_data = ?, status = 'WAITING_PAYMENT', updated_at = ? WHERE telegram_id = ?",
        (brief_json, datetime.now().isoformat(), telegram_id)
    )
    conn.commit()
    conn.close()

def log_chat_message(telegram_id: int, sender: str, text: str, bot_variant: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (telegram_id, sender, text, bot_variant) VALUES (?, ?, ?, ?)",
        (telegram_id, sender, text, bot_variant)
    )
    conn.commit()
    conn.close()

def get_all_leads_crm():
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads ORDER BY updated_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_lead_messages(telegram_id: int):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM messages WHERE telegram_id = ? ORDER BY timestamp ASC", (telegram_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_ab_stats():
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            bot_variant, 
            COUNT(*) as total_leads,
            SUM(CASE WHEN brief_data != '{}' THEN 1 ELSE 0 END) as briefs_count,
            SUM(CASE WHEN status IN ('PAID', 'GENERATED', 'DELIVERED') THEN 1 ELSE 0 END) as sales_count
        FROM leads 
        GROUP BY bot_variant
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def save_generated_site(telegram_id: int, site_url: str, site_path: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE leads SET site_url = ?, site_path = ?, status = 'GENERATED', updated_at = ? WHERE telegram_id = ?",
        (site_url, site_path, datetime.now().isoformat(), telegram_id)
    )
    conn.commit()
    conn.close()

def is_lead_duplicate(target_url: str, phone: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    clean_url = target_url.lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
    
    cursor.execute("SELECT id FROM leads_queue WHERE LOWER(target_url) LIKE ?", (f"%{clean_url}%",))
    if cursor.fetchone():
        conn.close()
        return True
        
    if phone:
        clean_phone = "".join(filter(str.isdigit, phone))
        if len(clean_phone) >= 7:
            cursor.execute("SELECT id FROM leads_queue WHERE phone LIKE ?", (f"%{clean_phone[-7:]}%",))
            if cursor.fetchone():
                conn.close()
                return True
                
    conn.close()
    return False

def add_to_lead_queue(company_name: str, target_url: str, phone: str = "", city: str = "", timezone_offset: int = 3):
    init_db()
    if is_lead_duplicate(target_url, phone):
        return False
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO leads_queue (company_name, target_url, phone, city, timezone_offset) VALUES (?, ?, ?, ?, ?)",
            (company_name, target_url, phone, city, timezone_offset)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding lead to queue: {e}")
        conn.close()
        return False

def get_pending_queue_leads(limit: int = 10):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads_queue WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT ?", (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def update_queue_status(queue_id: int, status: str, error_message: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE leads_queue SET status = ?, error_message = ? WHERE id = ?",
        (status, error_message, queue_id)
    )
    conn.commit()
    conn.close()

def get_incomplete_brief_leads():
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM leads 
        WHERE (status = 'INCOMPLETE_BRIEF' OR (brief_step > 0 AND brief_step < 7))
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

if __name__ == "__main__":
    init_db()
    print("Database updated and auto-migrated.")
