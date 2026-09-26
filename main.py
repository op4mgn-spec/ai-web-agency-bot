import threading
import time
import os
import requests
import server

PORT = int(os.getenv("PORT", 8000))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "8740453272:AAG5MyW2cvsiPaRT3i3V4feM7bRKoGhyFbU"
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL") or "https://ai-web-agency-bot.onrender.com"

def run_web_server():
    print(f"Starting Web Server thread on port {PORT}...")
    server.run_server()

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

if __name__ == "__main__":
    print("🚀 Initializing AI Web Studio Webhook Cloud Engine...")
    
    # Start web server in background thread
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()

    # Start Webhook setup and keepalive on main thread
    setup_webhook_and_keepalive()
