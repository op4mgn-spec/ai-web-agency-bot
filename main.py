import threading
import time
import os
import requests
import server

import db
from webhook_engine import send_telegram_message

PORT = int(os.getenv("PORT", 8000))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "8740453272:AAG5MyW2cvsiPaRT3i3V4feM7bRKoGhyFbU"
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL") or "https://ai-web-agency-bot.onrender.com"

RECOVERY_MESSAGES = {
    "Variant A (Консультант)": "👋 Здравствуйте! Я заметил, что мы остановились на заполнении брифа. Есть ли у вас какие-либо вопросы? Давайте продолжим!",
    "Variant B (Прямые Продажи)": "⚡️ Напоминание: за вами забронирована цена 9 900 руб! Давайте за 1 минуту дозаполним бриф и отдадим макет в сборку?",
    "Variant C (Демо-Специалист)": "🎨 Наша студия готова приступить к отрисовке первых макетов! Закончим бриф, чтобы запустить генерацию?",
    "Variant D (Архитектор Решений)": "📊 Осталось ответить на пару вопросов брифа, чтобы сформировать полную структуру и воронку сайта под вашу нишу!"
}

def run_web_server():
    print(f"Starting Web Server thread on port {PORT}...")
    server.run_server()

def run_brief_recovery_loop():
    print("🔄 Starting Incomplete Brief Auto-Recovery Loop...")
    while True:
        try:
            incomplete_leads = db.get_incomplete_brief_leads()
            for lead in incomplete_leads:
                chat_id = lead['telegram_id']
                variant = lead.get('bot_variant', 'Variant A (Консультант)')
                msg = RECOVERY_MESSAGES.get(variant, RECOVERY_MESSAGES["Variant A (Консультант)"])
                
                kbd = {"inline_keyboard": [[{"text": "📝 Продолжить бриф", "callback_data": "start_brief"}]]}
                send_telegram_message(chat_id, msg, reply_markup=kbd)
                
                # Update status to avoid endless spam
                db.update_lead_status(chat_id, "BRIEF_RECOVERY_SENT")
                db.log_chat_message(chat_id, "BOT", f"[AUTO-RECOVERY] {msg}", variant)
                print(f"  📩 Auto-recovery message sent to lead {chat_id} ({variant})")
        except Exception as e:
            print(f"Error in brief recovery loop: {e}")
        
        time.sleep(600) # Check every 10 minutes

def setup_webhook_and_keepalive():
    time.sleep(3)
    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
    print(f"Auto-registering Telegram Webhook to {webhook_url}...")
    try:
        r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={webhook_url}&drop_pending_updates=true", timeout=10)
        print("SetWebhook response:", r.json())
    except Exception as e:
        print(f"SetWebhook error: {e}")

    # Keepalive loop
    ping_url = f"http://127.0.0.1:{PORT}/ping"
    while True:
        try:
            r = requests.get(ping_url, timeout=5)
            print(f"Keepalive ping status: {r.status_code}")
        except Exception as e:
            print(f"Keepalive ping error: {e}")
        time.sleep(240)

import shutil

def run_database_backup_loop():
    print("💾 Starting Automated Database Backup Loop...")
    db_file = os.path.join(os.path.dirname(__file__), "agency.db")
    backup_file = os.path.join(os.path.dirname(__file__), "agency_backup.db")
    while True:
        try:
            if os.path.exists(db_file):
                shutil.copy2(db_file, backup_file)
                print("  💾 Database snapshot backup saved to agency_backup.db")
        except Exception as e:
            print(f"Error in database backup loop: {e}")
        time.sleep(3600) # Backup every 1 hour

if __name__ == "__main__":
    print("🚀 Initializing AI Web Studio Webhook Cloud Engine...")

    # Auto-seed demo CRM data if leads count is low
    try:
        import seed_crm_demo_data
        leads_count = len(db.get_all_leads_crm())
        if leads_count < 5:
            print("🌱 Initializing CRM with demo leads across all stages...")
            seed_crm_demo_data.seed_demo_data()
    except Exception as e:
        print(f"Error seeding demo data on startup: {e}")
    
    # Start web server in background thread
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()

    # Start Incomplete Brief Recovery loop in background thread
    recovery_thread = threading.Thread(target=run_brief_recovery_loop, daemon=True)
    recovery_thread.start()

    # Start Database Backup loop in background thread (Item 48)
    backup_thread = threading.Thread(target=run_database_backup_loop, daemon=True)
    backup_thread.start()

    # Start Webhook setup and keepalive on main thread
    setup_webhook_and_keepalive()
