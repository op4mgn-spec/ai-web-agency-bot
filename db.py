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
            status TEXT DEFAULT 'NEW',  -- NEW, BRIEFING, INCOMPLETE_BRIEF, WAITING_PAYMENT, PAID, GENERATED, DELIVERED
            brief_step INTEGER DEFAULT 0,
            brief_data TEXT DEFAULT '{}',
            bot_variant TEXT DEFAULT 'Variant A (Agile AI)',
            site_url TEXT DEFAULT '',
            site_path TEXT DEFAULT '',
            feedback TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Full Chat Dialog History table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            sender TEXT,  -- USER or BOT
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
            status TEXT,  -- SUCCESS, FAILED
            error_message TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert default A/B testing personas if empty
    cursor.execute("SELECT COUNT(*) FROM bot_variants")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO bot_variants (name, system_prompt) VALUES (?, ?)", (
            "Variant A (Консультант)",
            "Ты — мягкий эксперт-консультант веб-студии. Твоя цель — подробно и вежливо отвечать на вопросы, давать советы по продвижению бизнеса и плавно вести к заполнению брифа."
        ))
        cursor.execute("INSERT INTO bot_variants (name, system_prompt) VALUES (?, ?)", (
            "Variant B (Прямые Продажи)",
            "Ты — энергичный и уверенный директор по продажам. Твоя цель — четко отвечать на вопросы, приводить конкретные цифры и факты, закрывать все возражения и предлагать скидку 10% при оформлении прямо сейчас."
        ))

    conn.commit()
    conn.close()

def get_or_create_lead(telegram_id: int, username: str = "", full_name: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    if not row:
        # Assign A/B variant round-robin
        cursor.execute("SELECT count(*) FROM leads")
        count = cursor.fetchone()[0]
        variant = "Variant A (Консультант)" if count % 2 == 0 else "Variant B (Прямые Продажи)"
        
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
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads ORDER BY updated_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_lead_messages(telegram_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM messages WHERE telegram_id = ? ORDER BY timestamp ASC", (telegram_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_ab_stats():
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

if __name__ == "__main__":
    init_db()
    print("Database updated with CRM & Chat logging tables.")
