import http.server
import socketserver
import os
import json
import urllib.parse
import db

PORT = int(os.getenv("PORT", 8000))
DIRECTORY = os.path.dirname(__file__)

class CRMHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Healthcheck / Keep-Alive Ping
        if path == "/ping" or path == "/health":
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

        # Fallback to static files (generated_sites, etc.)
        super().do_GET()

def run_server():
    with socketserver.TCPServer(("", PORT), CRMHandler) as httpd:
        print(f"Web CRM & Health Server running at http://0.0.0.0:{PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
