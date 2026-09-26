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

        self.send_response(404)
        self.end_headers()

def run_server():
    with socketserver.TCPServer(("", PORT), CRMHandler) as httpd:
        print(f"Web CRM & Health Server running at http://0.0.0.0:{PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
