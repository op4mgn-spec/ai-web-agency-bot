import requests

token = '8740453272:AAG5MyW2cvsiPaRT3i3V4feM7bRKoGhyFbU'
url = 'https://ai-web-agency-bot.onrender.com/webhook'

print(f"Setting webhook to {url}...")
try:
    r = requests.get(f"https://api.telegram.org/bot{token}/setWebhook?url={url}&drop_pending_updates=true", timeout=10)
    print("setWebhook result:", r.json())
except Exception as e:
    print("setWebhook error:", e)
