import http.server
import socketserver
import os
import json
import urllib.parse
import threading
import requests
import db
import webhook_engine

PORT = int(os.getenv("PORT", 8000))
DIRECTORY = os.path.dirname(__file__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "8740453272:AAG5MyW2cvsiPaRT3i3V4feM7bRKoGhyFbU"

class CRMHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Diagnostic endpoint: Tests Telegram API directly from cloud container!
        if path == "/test-tg":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            try:
                r_me = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe", timeout=5).json()
                r_wh = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo", timeout=5).json()
                data = {"getMe": r_me, "getWebhookInfo": r_wh, "RENDER_EXTERNAL_URL": os.getenv("RENDER_EXTERNAL_URL")}
                self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
            except Exception as e:
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        # Healthcheck / Keep-Alive Ping
        elif path == "/ping" or path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # Serve Web CRM Dashboard on homepage
        elif path == "/" or path == "/crm":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            crm_path = os.path.join(DIRECTORY, "crm_dashboard.html")
            with open(crm_path, "rb") as f:
                self.wfile.write(f.read())
            return

        # Serve Owner Executive Dashboard
        elif path == "/owner" or path == "/executive":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            owner_path = os.path.join(DIRECTORY, "owner_dashboard.html")
            with open(owner_path, "rb") as f:
                self.wfile.write(f.read())
            return

        # API: Owner Executive Dashboard Combined Data
        elif path == "/api/owner_dashboard":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            data = db.get_owner_dashboard_data()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            return

        # API: CRM Data (Leads + A/B Stats)
        elif path == "/api/crm_data":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            leads = db.get_all_leads_crm()
            ab_stats = db.get_ab_stats()
            data = {"leads": leads, "ab_stats": ab_stats}
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            return

        # API: Full Chat Dialog History for a Lead
        elif path == "/api/chat_history":
            telegram_id = query.get("telegram_id", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            messages = []
            if telegram_id:
                try:
                    messages = db.get_lead_messages(int(telegram_id))
                except Exception as e:
                    print(f"Error fetching chat history: {e}")
            self.wfile.write(json.dumps(messages, ensure_ascii=False).encode("utf-8"))
            return

        # API: Export CRM Leads as CSV (Item 45)
        elif path == "/api/export_crm":
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8-sig")
            self.send_header("Content-Disposition", "attachment; filename=leads_export.csv")
            self.end_headers()
            
            leads = db.get_all_leads_crm()
            lines = ["Telegram ID;Username;Full Name;Status;Bot Variant;Created At;Updated At"]
            for l in leads:
                lines.append(f"{l.get('telegram_id')};{l.get('username')};{l.get('full_name')};{l.get('status')};{l.get('bot_variant')};{l.get('created_at')};{l.get('updated_at')}")
            
            csv_data = "\n".join(lines)
            self.wfile.write(csv_data.encode("utf-8-sig"))
            return

        # Client Portal Link Endpoint (Item 37)
        elif path.startswith("/status/"):
            target_id_str = path.replace("/status/", "").strip()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            
            lead_info = None
            if target_id_str.isdigit():
                leads = db.get_all_leads_crm()
                lead_info = next((l for l in leads if l['telegram_id'] == int(target_id_str)), None)
            
            if lead_info:
                brief_data = json.loads(lead_info.get("brief_data", "{}"))
                status = lead_info.get("status", "NEW")
                status_texts = {
                    "NEW": "🆕 Заказ создан",
                    "BRIEFING": "📝 Заполнение брифа",
                    "INCOMPLETE_BRIEF": "⚠️ Бриф не дозаполнен",
                    "WAITING_PAYMENT": "💰 Ожидает подтверждения",
                    "PAID": "✅ Оплачен / В разработке",
                    "GENERATED": "🔨 Сайт сгенерирован (на проверке арт-директора)",
                    "DELIVERED": "🚀 Сайт утвержден и доставлен!"
                }
                status_str = status_texts.get(status, status)
                site_url = lead_info.get("site_url", "")
                site_btn = f'<p style="margin-top:20px;"><a href="{site_url}" style="background:#3b82f6;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;">🌐 Открыть готовый сайт</a></p>' if site_url else ''

                html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8"><title>Статус заказа | {brief_data.get('company_name', 'Проект')}</title>
    <style>
        body {{ font-family: sans-serif; background: #0f172a; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; }}
        .card {{ background: #1e293b; padding: 40px; border-radius: 16px; max-width: 500px; width: 100%; border: 1px solid #334155; text-align: center; }}
        .status {{ font-size: 20px; font-weight: bold; color: #10b981; margin: 20px 0; background: #064e3b; padding: 10px; border-radius: 8px; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>🏢 {brief_data.get('company_name', 'Ваш Проект')}</h2>
        <p style="color: #94a3b8; margin-top: 5px;">Статус вашего заказа в AI Web Studio:</p>
        <div class="status">{status_str}</div>
        <p style="color: #cbd5e1; font-size: 14px;">Ниша: {brief_data.get('niche', 'Не указана')}</p>
        {site_btn}
    </div>
</body></html>"""
                self.wfile.write(html.encode("utf-8"))
            else:
                self.wfile.write(b"<html><body><h2>Lead not found</h2></body></html>")
            return

        # Fallback to static files
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Handle Telegram Webhook POST requests via Webhook Engine
        if path == "/webhook" or path == "/telegram-webhook":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            # Immediately acknowledge webhook to Telegram to avoid 5-second timeout retries!
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")

            try:
                update_data = json.loads(post_data.decode('utf-8'))
                threading.Thread(target=webhook_engine.process_telegram_update, args=(update_data,), daemon=True).start()
            except Exception as e:
                print(f"Error starting async webhook worker: {e}")
            return

        # API: Direct Admin Message to Telegram Client
        elif path == "/api/send_admin_message":
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            telegram_id = body.get('telegram_id')
            text = body.get('text', '').strip()

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()

            if not telegram_id or not text:
                self.wfile.write(json.dumps({"error": "Missing telegram_id or text"}).encode('utf-8'))
                return

            lead = db.get_or_create_lead(int(telegram_id))
            bot_variant = lead.get('bot_variant', 'Variant A (Консультант)')

            # Send directly to client's Telegram chat from Bot
            sent_res = webhook_engine.send_telegram_message(int(telegram_id), text)
            
            # Log as BOT message in dialog history
            db.log_chat_message(int(telegram_id), "BOT", f"✍️ [Менеджер]: {text}", bot_variant)
            
            # If lead was in REJECTED/OBJECTION, advance to ADMIN_NEGOTIATING
            if lead.get('status') in ['REJECTED', 'OBJECTION', 'LOST']:
                db.update_lead_status(int(telegram_id), 'ADMIN_NEGOTIATING')

            res_data = {"status": "ok", "message": "Сообщение отправлено клиенту в Telegram!", "sent": sent_res}
            self.wfile.write(json.dumps(res_data, ensure_ascii=False).encode('utf-8'))
            return

        # API: Verify / Simulate Payment for Lead
        elif path == "/api/verify_payment":
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            telegram_id = body.get('telegram_id')

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()

            if not telegram_id:
                self.wfile.write(json.dumps({"error": "Missing telegram_id"}).encode('utf-8'))
                return

            db.update_lead_status(int(telegram_id), "PAID")
            
            # Notify client in Telegram
            msg = "✅ **Оплата 9 900 руб. официально подтверждена!**\n\nВаш заказ зафиксирован в системе. Арт-директор приступил к сборке и утверждению макета!"
            webhook_engine.send_telegram_message(int(telegram_id), msg)
            db.log_chat_message(int(telegram_id), "BOT", msg, "Система")

            self.wfile.write(json.dumps({"status": "ok", "message": "Оплата подтверждена!"}).encode('utf-8'))
            return

        # API: Update Lead Status from CRM
        elif path == "/api/update_lead_status":
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            telegram_id = body.get('telegram_id')
            new_status = body.get('status')

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()

            if not telegram_id or not new_status:
                self.wfile.write(json.dumps({"error": "Missing args"}).encode('utf-8'))
                return

            db.update_lead_status(int(telegram_id), new_status)
            self.wfile.write(json.dumps({"status": "ok", "new_status": new_status}).encode('utf-8'))
            return

        # API: Update Departmental Initiative Status from Owner Dashboard
        elif path == "/api/update_initiative_status":
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            init_id = body.get('id')
            new_status = body.get('status')

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()

            if not init_id or not new_status:
                self.wfile.write(json.dumps({"error": "Missing args"}).encode('utf-8'))
                return

            db.update_initiative_status(int(init_id), new_status)
            self.wfile.write(json.dumps({"status": "ok", "id": init_id, "new_status": new_status}).encode('utf-8'))
            return

        self.send_response(404)
        self.end_headers()

def run_server():
    with socketserver.TCPServer(("", PORT), CRMHandler) as httpd:
        print(f"Web CRM & Health Server running at http://0.0.0.0:{PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
