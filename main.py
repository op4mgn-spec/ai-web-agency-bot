import threading
import time
import os
import requests
import server
import bot

PORT = int(os.getenv("PORT", 8000))

def run_web_server():
    print(f"Starting Web Server thread on port {PORT}...")
    server.run_server()

def run_keepalive_ping():
    """Pings the local server every 4 minutes to prevent Render Free tier from sleeping."""
    time.sleep(10)
    url = f"http://127.0.0.1:{PORT}/ping"
    while True:
        try:
            r = requests.get(url, timeout=5)
            print(f"Keepalive ping status: {r.status_code}")
        except Exception as e:
            print(f"Keepalive ping error: {e}")
        time.sleep(240) # Every 4 minutes

def run_telegram_bot():
    print("Starting Telegram Sales Bot thread...")
    bot.main()

if __name__ == "__main__":
    print("🚀 Initializing AI Web Studio Cloud Services...")
    
    # Start web server in background thread
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()

    # Start keepalive thread
    ping_thread = threading.Thread(target=run_keepalive_ping, daemon=True)
    ping_thread.start()

    # Start Telegram Bot on main thread
    time.sleep(2)
    run_telegram_bot()
