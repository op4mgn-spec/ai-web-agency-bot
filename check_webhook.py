import requests
import json

token = '8740453272:AAG5MyW2cvsiPaRT3i3V4feM7bRKoGhyFbU'

print("Checking getWebhookInfo and getMe...")
# Test via different proxy endpoints
endpoints = [
    f"https://api.telegram.org/bot{token}/getWebhookInfo",
    f"https://api.telegram.org/bot{token}/getMe"
]

for url in endpoints:
    try:
        r = requests.get(url, timeout=5)
        print(f"URL {url}:", r.json())
    except Exception as e:
        print(f"URL {url} Error:", e)
