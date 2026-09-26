"""
proposal_generator.py - B2B Commercial Proposal (КП) Generator (Item 28)
Creates branded commercial proposal HTML documents for clients based on brief data.
"""

import sys
import os
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

OUTPUT_DIR = Path(__file__).parent / "generated_sites"
OUTPUT_DIR.mkdir(exist_ok=True)

def generate_commercial_proposal(brief_data: dict, client_id: str) -> str:
    company = brief_data.get("company_name", "Уважаемый Клиент")
    niche = brief_data.get("niche", "Услуги")
    services = brief_data.get("services", "Разработка веб-сайта")
    phone = brief_data.get("phone", "")

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Коммерческое предложение | {company}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f8fafc; color: #0f172a; padding: 40px 20px; }}
        .proposal-card {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 16px; padding: 40px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); border: 1px solid #e2e8f0; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #3b82f6; padding-bottom: 20px; margin-bottom: 30px; }}
        .logo {{ font-size: 24px; font-weight: bold; color: #3b82f6; }}
        .badge {{ background: #eff6ff; color: #1d4ed8; padding: 6px 14px; border-radius: 20px; font-weight: 600; font-size: 14px; }}
        h1 {{ font-size: 28px; margin-bottom: 10px; color: #1e293b; }}
        .subtitle {{ font-size: 16px; color: #64748b; margin-bottom: 30px; }}
        .price-box {{ background: #f1f5f9; padding: 25px; border-radius: 12px; margin: 25px 0; border-left: 5px solid #10b981; }}
        .price {{ font-size: 32px; font-weight: bold; color: #10b981; }}
        ul {{ margin-left: 20px; margin-bottom: 25px; line-height: 1.8; }}
        .footer {{ text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #94a3b8; font-size: 14px; }}
        .btn {{ display: inline-block; background: #3b82f6; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; margin-top: 15px; }}
    </style>
</head>
<body>
    <div class="proposal-card">
        <div class="header">
            <div class="logo">⚡️ AI Web Studio</div>
            <div class="badge">Официальное КП</div>
        </div>

        <h1>Коммерческое предложение по разработке сайта</h1>
        <div class="subtitle">Специально для компании: <strong>{company}</strong> ({niche})</div>

        <p>На основе анализа вашей ниши ({niche}) команда <strong>AI Web Studio</strong> подготовила решение по созданию высококонверсионного продающего лендинга под ключ.</p>

        <div class="price-box">
            <div>Фиксированная стоимость разработки:</div>
            <div class="price">9 900 руб.</div>
            <div style="font-size: 14px; color: #64748b; margin-top: 5px;">Срок сдачи: 24 часа с момента утверждения брифа</div>
        </div>

        <h3>Что входит в стоимость:</h3>
        <ul>
            <li>Индивидуальный ИИ-копирайтинг и проработка УТП</li>
            <li>Адаптивная мобильная верстка под все устройства</li>
            <li>Подключение формы сбора заявок в Telegram / WhatsApp</li>
            <li>Первичная оптимизация SEO (OpenGraph, Meta Title, Description)</li>
            <li>Соответствие 152-ФЗ РФ (Политика конфиденциальности)</li>
            <li>Проверка и согласование арт-директором студии</li>
        </ul>

        <div style="text-align: center;">
            <a href="https://t.me/Aisiteconsultantbot" class="btn">🚀 Запустить проект в работу</a>
        </div>

        <div class="footer">
            <p>AI Web Studio © 2026. Связь с руководителем: @bers1q</p>
        </div>
    </div>
</body>
</html>
"""
    out_path = OUTPUT_DIR / f"proposal_{client_id}.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
        
    return str(out_path)

if __name__ == "__main__":
    test_data = {"company_name": "АвтоСервис Профи", "niche": "Автосервис", "phone": "+7 (495) 123-45-67"}
    path = generate_commercial_proposal(test_data, "test_123")
    print(f"Generated Proposal at: {path}")
