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

    # System Settings Table (Persist API Keys & Config)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    # Departmental Initiatives / Roadmap Table (Executive Dashboard)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS department_initiatives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT,
            role_title TEXT,
            title TEXT,
            description TEXT,
            kpi TEXT,
            priority TEXT DEFAULT 'MEDIUM',
            status TEXT DEFAULT 'IN_PROGRESS',
            approval_status TEXT DEFAULT 'APPROVED',
            hypothesis_impact TEXT DEFAULT '',
            executed_results TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    for col, col_type in [
        ('approval_status', "TEXT DEFAULT 'APPROVED'"),
        ('hypothesis_impact', "TEXT DEFAULT ''"),
        ('executed_results', "TEXT DEFAULT ''")
    ]:
        try:
            cursor.execute(f"ALTER TABLE department_initiatives ADD COLUMN {col} {col_type}")
        except Exception:
            pass

    # Financial Ledger Table (CFO Revenues & Expenses)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS financial_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_type TEXT,
            category TEXT,
            amount REAL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Fulfillment & Order Execution SLA Metrics Table (COO Operations)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fulfillment_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            company_name TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            delivered_at TIMESTAMP,
            turnaround_hours REAL DEFAULT 24.0,
            sla_status TEXT DEFAULT 'SLA_PASSED_24H',
            qa_score INTEGER DEFAULT 5
        )
    ''')

    # Autonomous Dev Tasks Table (Antigravity Code Bridge)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS autonomous_dev_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            prompt TEXT,
            status TEXT DEFAULT 'PENDING',
            commit_hash TEXT DEFAULT '',
            files_changed TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            error_message TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
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

    # Also load cold outreach leads from leads_queue
    try:
        cursor.execute("SELECT * FROM leads_queue ORDER BY id DESC")
        queue_rows = [dict(r) for r in cursor.fetchall()]
        for q in queue_rows:
            q_status = q.get("status", "PENDING")
            st = "COLLECTED" if q_status == "PENDING" else ("OUTREACH_SENT" if q_status == "SENT" else q_status)
            rows.append({
                "telegram_id": f"queue_{q['id']}",
                "username": q.get("city") or "РФ",
                "full_name": q.get("company_name") or "Лид из базы",
                "status": st,
                "bot_variant": "🎯 Сбор базы (Outreach)",
                "site_url": q.get("target_url") or "",
                "site_path": "",
                "feedback": f"🌐 {q.get('target_url', '')} | 📞 {q.get('phone', '')}",
                "created_at": q.get("created_at") or datetime.now().isoformat(),
                "updated_at": q.get("created_at") or datetime.now().isoformat(),
                "brief_step": 0,
                "brief_data": json.dumps({
                    "target_url": q.get("target_url"),
                    "phone": q.get("phone"),
                    "city": q.get("city"),
                    "tz": f"UTC+{q.get('timezone_offset', 3)}"
                }, ensure_ascii=False),
                "is_queue": True,
                "queue_id": q["id"]
            })
    except Exception as e:
        print(f"Error merging queue leads into CRM: {e}")

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

def get_queue_lead_by_id(queue_id: int):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads_queue WHERE id = ?", (queue_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

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

def set_setting(key: str, value: str):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_setting(key: str, default: str = "") -> str:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else default
    except Exception:
        conn.close()
        return default

def get_queue_lead_by_param(param: str):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    clean_param = param.lower().replace("lead_", "").strip()
    if clean_param.isdigit():
        cursor.execute("SELECT * FROM leads_queue WHERE id = ?", (int(clean_param),))
        row = cursor.fetchone()
        if row:
            conn.close()
            return dict(row)
            
    cursor.execute("SELECT * FROM leads_queue WHERE target_url LIKE ? OR company_name LIKE ?", (f"%{param}%", f"%{param}%"))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_department_initiatives(department: str = None):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    if department and department != 'ALL':
        cursor.execute("SELECT * FROM department_initiatives WHERE department = ? ORDER BY id DESC", (department,))
    else:
        cursor.execute("SELECT * FROM department_initiatives ORDER BY id DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def add_department_initiative(department: str, role_title: str, title: str, description: str, kpi: str, priority: str = "MEDIUM", status: str = "IN_PROGRESS"):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO department_initiatives (department, role_title, title, description, kpi, priority, status, approval_status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'APPROVED', ?, ?)
    """, (department, role_title, title, description, kpi, priority, status, now_str, now_str))
    conn.commit()
    conn.close()

def add_department_initiative_with_approval(department: str, role_title: str, title: str, description: str, kpi: str, hypothesis_impact: str = "", priority: str = "HIGH", approval_status: str = "PENDING_APPROVAL", status: str = "BACKLOG"):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO department_initiatives (department, role_title, title, description, kpi, priority, status, approval_status, hypothesis_impact, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (department, role_title, title, description, kpi, priority, status, approval_status, hypothesis_impact, now_str, now_str))
    init_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return init_id

def update_initiative_approval(initiative_id: int, approval_status: str):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    new_status = "IN_PROGRESS" if approval_status == "APPROVED" else ("REJECTED" if approval_status == "REJECTED" else "BACKLOG")
    cursor.execute("""
        UPDATE department_initiatives SET approval_status = ?, status = ?, updated_at = ? WHERE id = ?
    """, (approval_status, new_status, now_str, initiative_id))
    conn.commit()
    conn.close()

def get_initiative_by_id(initiative_id: int):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM department_initiatives WHERE id = ?", (initiative_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_department_initiative(initiative_id: int):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM department_initiatives WHERE id = ?", (initiative_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def deduplicate_initiatives():
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    # Step 1: Remove exact duplicates where department and title are identical (keep the lowest ID)
    cursor.execute("""
        DELETE FROM department_initiatives
        WHERE id NOT IN (
            SELECT MIN(id) FROM department_initiatives GROUP BY department, title
        )
    """)
    removed_1 = cursor.rowcount

    # Step 2: Remove test initiatives with duplicate or repetitive descriptions
    cursor.execute("""
        DELETE FROM department_initiatives
        WHERE id NOT IN (
            SELECT MIN(id) FROM department_initiatives GROUP BY description
        )
    """)
    removed_2 = cursor.rowcount
    
    total_removed = removed_1 + removed_2
    conn.commit()
    conn.close()
    return total_removed

def update_initiative_status(initiative_id: int, new_status: str):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("""
        UPDATE department_initiatives SET status = ?, updated_at = ? WHERE id = ?
    """, (new_status, now_str, initiative_id))
    conn.commit()
    conn.close()

def get_implemented_initiatives_journal():
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, department, role_title, title, description, kpi, hypothesis_impact, executed_results, 
               strftime('%Y-%m-%d', updated_at) as date_key, updated_at
        FROM department_initiatives
        WHERE status = 'COMPLETED' OR approval_status = 'APPROVED'
        ORDER BY updated_at DESC, id DESC
    ''')
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    grouped = {}
    for r in rows:
        dk = r.get("date_key")
        if not dk or dk == "None":
            # fallback to created_at or today
            dk = datetime.now().strftime("%Y-%m-%d")
        if dk not in grouped:
            grouped[dk] = []
        grouped[dk].append(r)

    result = []
    for date_key, inits in grouped.items():
        result.append({
            "date": date_key,
            "count": len(inits),
            "initiatives": inits
        })
    return result

def add_financial_transaction(transaction_type: str, category: str, amount: float, description: str):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO financial_ledger (transaction_type, category, amount, description)
        VALUES (?, ?, ?, ?)
    """, (transaction_type, category, amount, description))
    conn.commit()
    conn.close()

def get_financial_summary():
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(amount) FROM financial_ledger WHERE transaction_type = 'INCOME'")
    res_inc = cursor.fetchone()[0]
    total_income = float(res_inc) if res_inc else 0.0

    cursor.execute("SELECT SUM(amount) FROM financial_ledger WHERE transaction_type = 'EXPENSE'")
    res_exp = cursor.fetchone()[0]
    total_expense = float(res_exp) if res_exp else 0.0

    cursor.execute("SELECT * FROM financial_ledger ORDER BY id DESC LIMIT 20")
    transactions = [dict(r) for r in cursor.fetchall()]
    conn.close()

    net_profit = total_income - total_expense
    margin_percent = round(((net_profit) / total_income * 100), 1) if total_income > 0 else 0.0

    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "net_profit": net_profit,
        "margin_percent": margin_percent,
        "transactions": transactions
    }

def get_owner_dashboard_data():
    initiatives = get_department_initiatives()
    finances = get_financial_summary()
    leads = get_all_leads_crm()
    ab_stats = get_ab_stats()
    
    total_leads = len(leads)
    paid_leads = len([l for l in leads if l.get('status') in ['PAID', 'GENERATED', 'DELIVERED']])
    delivered_leads = len([l for l in leads if l.get('status') == 'DELIVERED'])
    
    conversion_rate = round((paid_leads / total_leads * 100), 1) if total_leads > 0 else 0.0

    return {
        "initiatives": initiatives,
        "finances": finances,
        "ab_stats": ab_stats,
        "implemented_journal": get_implemented_initiatives_journal(),
        "executive_summary": {
            "total_leads": total_leads,
            "paid_leads": paid_leads,
            "delivered_leads": delivered_leads,
            "conversion_rate": conversion_rate,
            "revenue": finances["total_income"],
            "net_profit": finances["net_profit"],
            "margin_percent": finances["margin_percent"],
            "sla_pass_rate": 100.0 if delivered_leads > 0 else 100.0
        }
    }

def create_autonomous_task(chat_id: int, prompt: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO autonomous_dev_tasks (chat_id, prompt, status) VALUES (?, ?, 'PENDING')",
        (chat_id, prompt)
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id

def get_pending_autonomous_tasks():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM autonomous_dev_tasks WHERE status = 'PENDING' ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def update_autonomous_task(task_id: int, status: str, commit_hash: str = '', files_changed: str = '', summary: str = '', error_message: str = ''):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE autonomous_dev_tasks 
        SET status = ?, commit_hash = ?, files_changed = ?, summary = ?, error_message = ?, completed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (status, commit_hash, files_changed, summary, error_message, task_id))
    conn.commit()
    conn.close()

def get_all_autonomous_tasks(limit: int = 20):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM autonomous_dev_tasks ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

if __name__ == "__main__":
    init_db()
    print("Database updated and auto-migrated.")

def update_department_initiative(id, title, description, kpi, hypothesis_impact):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE department_initiatives 
        SET title = ?, description = ?, kpi = ?, hypothesis_impact = ?, updated_at = CURRENT_TIMESTAMP 
        WHERE id = ?
    ''', (title, description, kpi, hypothesis_impact, id))
    conn.commit()
    conn.close()
