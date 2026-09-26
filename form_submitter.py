import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
import time
from db import log_form_submission

DEFAULT_MESSAGE_TEMPLATE = """
Здравствуйте! Меня зовут {sender_name}, представляю сервис автоматической разработки сайтов для бизнеса ({niche}).
Мы заметили, что у вашего сайта есть потенциал для роста конверсии.
За 1 день можем создать для вашей компании новый современный сайт под ключ с гарантией.
Посмотреть примеры работ и сразу рассчитать стоимость можно в нашем Telegram-боте: {bot_link}
"""

def submit_to_contact_form(target_url: str, sender_name: str = "AI Web Studio", niche: str = "Ваша ниша", bot_link: str = "https://t.me/YourBotName") -> dict:
    """
    Parses a target website URL, discovers feedback/contact form inputs,
    and submits the custom proposal message.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(target_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find candidate forms
        forms = soup.find_all('form')
        if not forms:
            error = "No <form> elements found on page"
            log_form_submission(target_url, "", "FAILED", error)
            return {"status": "FAILED", "error": error}

        target_form = None
        form_inputs = {}

        # Scan for form with message/textarea or email/name fields
        for form in forms:
            inputs = form.find_all(['input', 'textarea', 'select'])
            has_text_area = any(inp.name == 'textarea' for inp in inputs)
            has_email_or_phone = any(
                re.search(r'email|phone|tel|contact|message|text|comment', inp.get('name', ''), re.IGNORECASE)
                for inp in inputs
            )
            if has_text_area or has_email_or_phone:
                target_form = form
                break

        if not target_form:
            target_form = forms[0] # Fallback to first form

        action = target_form.get('action', '')
        method = target_form.get('method', 'POST').upper()
        
        post_url = urllib.parse.urljoin(target_url, action) if action else target_url

        # Build payload based on field names
        payload = {}
        message_text = DEFAULT_MESSAGE_TEMPLATE.format(
            sender_name=sender_name,
            niche=niche,
            bot_link=bot_link
        )

        for inp in target_form.find_all(['input', 'textarea']):
            field_name = inp.get('name')
            if not field_name:
                continue
            
            field_type = inp.get('type', 'text').lower()
            name_lower = field_name.lower()

            if 'name' in name_lower or 'fio' in name_lower or 'contact' in name_lower:
                payload[field_name] = sender_name
            elif 'email' in name_lower or field_type == 'email':
                payload[field_name] = "info@aiwebstudio.ru"
            elif 'phone' in name_lower or 'tel' in name_lower or field_type == 'tel':
                payload[field_name] = "+7 (999) 000-00-00"
            elif inp.name == 'textarea' or 'msg' in name_lower or 'message' in name_lower or 'comment' in name_lower or 'text' in name_lower:
                payload[field_name] = message_text
            else:
                payload[field_name] = inp.get('value', 'Test')

        if method == 'POST':
            res = requests.post(post_url, data=payload, headers=headers, timeout=10)
        else:
            res = requests.get(post_url, params=payload, headers=headers, timeout=10)

        if res.status_code in (200, 201, 302):
            log_form_submission(target_url, "", "SUCCESS", f"HTTP {res.status_code}")
            return {"status": "SUCCESS", "submitted_fields": list(payload.keys())}
        else:
            error = f"HTTP status code {res.status_code}"
            log_form_submission(target_url, "", "FAILED", error)
            return {"status": "FAILED", "error": error}

    except Exception as e:
        log_form_submission(target_url, "", "FAILED", str(e))
        return {"status": "FAILED", "error": str(e)}

if __name__ == "__main__":
    print("Form submitter module initialized. Ready to process targets.")
