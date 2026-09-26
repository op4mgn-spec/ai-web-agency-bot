import requests

token = '8740453272:AAG5MyW2cvsiPaRT3i3V4feM7bRKoGhyFbU'

urls = [
    f"https://api.telegram.org/bot{token}/getMe",
    f"https://tgproxy.org/bot{token}/getMe",
    f"https://telegram-api.b-cdn.net/bot{token}/getMe",
    f"https://botapi.tlgrm.app/bot{token}/getMe"
]

for url in urls:
    try:
        r = requests.get(url, timeout=4)
        print(f"URL SUCCESS {url}:", r.json())
    except Exception as e:
        print(f"URL Failed {url}:", type(e).__name__)
