import threading
import time
import os
import server
import bot

def run_web_server():
    print("Starting Web Server thread on port 8000...")
    server.run_server()

def run_telegram_bot():
    print("Starting Telegram Sales Bot thread...")
    bot.main()

if __name__ == "__main__":
    print("🚀 Initializing AI Web Studio Cloud Services...")
    
    # Start web server in background thread
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()

    # Start Telegram Bot on main thread
    time.sleep(1)
    run_telegram_bot()
