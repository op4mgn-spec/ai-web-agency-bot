import requests

token = '8740453272:AAG5MyW2cvsiPaRT3i3V4feM7bRKoGhyFbU'

for port in [4343, 4449, 19443, 15152, 13417, 8765]:
    try:
        proxies = {
            'http': f'http://127.0.0.1:{port}',
            'https': f'http://127.0.0.1:{port}'
        }
        r = requests.get(f'https://api.telegram.org/bot{token}/getMe', proxies=proxies, timeout=3)
        print(f"SUCCESS on port {port}:", r.json())
    except Exception as e:
        print(f"Port {port} failed:", e)
