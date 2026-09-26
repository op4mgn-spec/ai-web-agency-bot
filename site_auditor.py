"""
site_auditor.py - Cold Prospect Intelligence & Website Audit Generator (Items 5 & 42)
Detects tech stack / CMS and identifies conversion bottlenecks for cold outreach proposals.
"""

import sys
import os
import requests
import re
from urllib.parse import urlparse

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def audit_website(url: str) -> dict:
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url

    result = {
        "url": url,
        "cms": "Неизвестная CMS / Самописный HTML",
        "has_ssl": url.startswith("https://"),
        "has_viewport": False,
        "has_title": False,
        "has_description": False,
        "audit_points": [],
        "score": 100
    }

    try:
        r = requests.get(url, timeout=7, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        html = r.text.lower()
        
        # Detect CMS
        if "tilda" in html or "tildacdn" in html:
            result["cms"] = "Tilda"
        elif "wp-content" in html or "wordpress" in html:
            result["cms"] = "WordPress"
        elif "bitrix" in html or "b_option" in html:
            result["cms"] = "1C-Bitrix"
        elif "wix.com" in html:
            result["cms"] = "Wix"
        elif "modx" in html:
            result["cms"] = "MODX"

        # Check mobile responsiveness
        if '<meta name="viewport"' in html or '<meta name=\'viewport\'' in html:
            result["has_viewport"] = True
        else:
            result["audit_points"].append("❌ Отсутствует метатег адаптивности для мобильных устройств")
            result["score"] -= 25

        # Check SSL
        if not result["has_ssl"]:
            result["audit_points"].append("❌ Сайт работает по незащищенному протоколу HTTP (нет SSL)")
            result["score"] -= 25

        # Check SEO title
        if "<title>" in html and "</title>" in html:
            result["has_title"] = True
        else:
            result["audit_points"].append("❌ Не заполнен базовый тег Title для Яндекс/Google")
            result["score"] -= 25

        # Check meta description
        if 'name="description"' in html or 'name=\'description\'' in html:
            result["has_description"] = True
        else:
            result["audit_points"].append("❌ Отсутствует Meta Description для поисковой выдачи")
            result["score"] -= 25

        if not result["audit_points"]:
            result["audit_points"].append("⚠️ Сайт устарел визуально и уступает новым ИИ-лендингам 2026 года")

    except Exception as e:
        result["audit_points"].append(f"⚠️ Ошибка при подключении к сайту: {e}")
        result["score"] = 50

    return result

def format_audit_proposal(url: str, company_name: str) -> str:
    audit = audit_website(url)
    points_text = "\n".join(audit["audit_points"][:3])
    
    proposal = (
        f"Здравствуйте, команда '{company_name}'!\n\n"
        f"Мы провели экспресс-анализ вашего текущего сайта ({url}):\n"
        f"• Платформа: {audit['cms']}\n"
        f"• Оценка оптимизации: {audit['score']}/100\n"
        f"{points_text}\n\n"
        f"Мы готовы создать для вас новый мобильный продающий лендинг за 24 часа всего за 9 900 руб.\n"
        f"Посмотрите пример готового сайта в нашем Telegram-боте: https://t.me/Aisiteconsultantbot?start={urlparse(url).netloc.replace('.', '_')}"
    )
    return proposal

if __name__ == "__main__":
    test_url = "http://auto-profi-msk.ru/feedback"
    res = audit_website(test_url)
    print(f"Audit Result for {test_url}:\n{res}")
    print("\nFormatted Cold Proposal:\n" + format_audit_proposal(test_url, "АвтоСервис Профи"))
