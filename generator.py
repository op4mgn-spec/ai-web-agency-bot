import os
import json
import re
import requests
from pathlib import Path

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

SITES_OUTPUT_DIR = Path(__file__).parent / "generated_sites"
SITES_OUTPUT_DIR.mkdir(exist_ok=True)

def generate_website_html(brief_data: dict, site_id: str) -> str:
    company_name = brief_data.get("company_name", "Наша Компания")
    niche = brief_data.get("niche", "Услуги и сервис")
    phone = brief_data.get("phone", "+7 (999) 000-00-00")
    services = brief_data.get("services", "Качественные услуги для вашего бизнеса")
    about = brief_data.get("utp", "Мы предоставляем профессиональные услуги со 100% гарантией качества.")
    color_theme = brief_data.get("color_theme", "#2563eb")

    ai_content = None
    key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY

    if key and key != "your_gemini_api_key_here":
        prompt = f"""
        Ты — лучший веб-копирайтер. Напиши текст для современного лендинга компании.
        Название: {company_name}
        Сфера/Ниша: {niche}
        Услуги: {services}
        О компании/УТП: {about}

        Верни ответ strictly в формате JSON со следующими полями:
        {{
            "hero_title": "Заголовок первого экрана (цепляющий, оффер)",
            "hero_subtitle": "Подзаголовок с выгодой для клиента",
            "features": ["Преимущество 1", "Преимущество 2", "Преимущество 3", "Преимущество 4"],
            "services_list": [
                {{"title": "Услуга 1", "description": "Описание услуги 1", "price": "от 1 000 руб."}},
                {{"title": "Услуга 2", "description": "Описание услуги 2", "price": "от 3 000 руб."}},
                {{"title": "Услуга 3", "description": "Описание услуги 3", "price": "от 5 000 руб."}}
            ],
            "cta_text": "Призыв к действию внизу страницы"
        }}
        """

        for model_name in ['gemini-3.8-flash', 'gemini-1.5-flash-latest', 'gemini-2.0-flash-latest']:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
            headers = {"Content-Type": "application/json"}
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            try:
                r = requests.post(url, json=payload, headers=headers, timeout=12)
                data = r.json()
                if "candidates" in data and len(data["candidates"]) > 0:
                    parts = data["candidates"][0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        raw_text = parts[0]["text"]
                        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                        if match:
                            ai_content = json.loads(match.group(0))
                            break
            except Exception as e:
                print(f"Generator Gemini REST Error ({model_name}): {e}")

    if not ai_content:
        ai_content = {
            "hero_title": f"Профессиональные услуги: {company_name}",
            "hero_subtitle": f"Качественное решение задач в сфере '{niche}' с гарантией результата.",
            "features": ["Высокая скорость работы", "Опыт более 5 лет", "Гарантия по договору", "Честные цены"],
            "services_list": [
                {"title": "Основная услуга", "description": services, "price": "Договорная"},
                {"title": "Консультация и аудит", "description": "Полный разбор вашей задачи", "price": "Бесплатно"},
                {"title": "Комплексное обслуживание", "description": "Сопровождение под ключ", "price": "Индивидуально"}
            ],
            "cta_text": "Оставьте заявку прямо сейчас и получите персональное предложение со скидкой!"
        }

    # Render HTML template
    features_html = "".join([f'<li class="feature-item">✓ {f}</li>' for f in ai_content['features']])
    
    services_html = "".join([
        f'''<div class="card">
            <h3>{s['title']}</h3>
            <p>{s['description']}</p>
            <div class="price">{s.get('price', '')}</div>
        </div>''' for s in ai_content['services_list']
    ])

    # SEO Meta Description & OpenGraph Tags
    meta_description = f"Официальный сайт компании '{company_name}'. {ai_content['hero_subtitle']}"
    og_title = f"{company_name} — {ai_content['hero_title']}"

    # Yandex Metrika Counter Slot (Item 34)
    metrika_code = brief_data.get("yandex_metrika", "")
    metrika_html = f"<!-- Yandex.Metrika counter -->\n{metrika_code}\n<!-- /Yandex.Metrika counter -->" if metrika_code else ""

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{company_name} | {niche}</title>
    <meta name="description" content="{meta_description}">
    <!-- OpenGraph Tags (Item 33) -->
    <meta property="og:title" content="{og_title}">
    <meta property="og:description" content="{meta_description}">
    <meta property="og:type" content="website">
    <meta property="og:locale" content="ru_RU">
    <style>
        :root {{
            --primary: {color_theme};
            --dark: #1e293b;
            --light: #f8fafc;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
        body {{ background-color: var(--light); color: var(--dark); line-height: 1.6; }}
        header {{ background: white; padding: 20px 5%; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 10px rgba(0,0,0,0.05); position: sticky; top: 0; z-index: 100; }}
        .logo {{ font-size: 24px; font-weight: bold; color: var(--primary); }}
        .phone-btn {{ background: var(--primary); color: white; padding: 10px 20px; text-decoration: none; border-radius: 8px; font-weight: 600; }}
        .hero {{ padding: 80px 5%; text-align: center; background: linear-gradient(135deg, white 0%, #edf2f7 100%); }}
        .hero h1 {{ font-size: 42px; margin-bottom: 20px; color: var(--dark); }}
        .hero p {{ font-size: 20px; color: #64748b; max-width: 700px; margin: 0 auto 30px; }}
        .btn {{ display: inline-block; background: var(--primary); color: white; padding: 15px 35px; text-decoration: none; font-size: 18px; border-radius: 8px; font-weight: bold; transition: 0.3s; }}
        .btn:hover {{ opacity: 0.9; transform: translateY(-2px); }}
        .section {{ padding: 60px 5%; max-width: 1200px; margin: 0 auto; }}
        .section-title {{ text-align: center; font-size: 32px; margin-bottom: 40px; }}
        .features-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; list-style: none; margin-bottom: 40px; }}
        .feature-item {{ background: white; padding: 20px; border-radius: 8px; font-size: 18px; font-weight: 500; border-left: 4px solid var(--primary); box-shadow: 0 2px 5px rgba(0,0,0,0.03); }}
        .services-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 30px; }}
        .card {{ background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
        .card h3 {{ font-size: 22px; margin-bottom: 15px; color: var(--primary); }}
        .card p {{ color: #64748b; margin-bottom: 20px; }}
        .card .price {{ font-weight: bold; font-size: 18px; color: var(--dark); }}
        .cta-box {{ background: var(--primary); color: white; padding: 50px 30px; border-radius: 16px; text-align: center; margin-top: 40px; }}
        .cta-box h2 {{ font-size: 32px; margin-bottom: 15px; }}
        .cta-box p {{ font-size: 18px; margin-bottom: 25px; opacity: 0.9; }}
        .legal-notice {{ font-size: 12px; opacity: 0.85; margin-top: 15px; display: block; }}
        footer {{ text-align: center; padding: 30px; color: #94a3b8; font-size: 14px; border-top: 1px solid #e2e8f0; margin-top: 60px; }}
        footer a {{ color: #64748b; text-decoration: underline; }}
    </style>
    {metrika_html}
</head>
<body>
    <header>
        <div class="logo">{company_name}</div>
        <a href="tel:{phone}" class="phone-btn">📞 {phone}</a>
    </header>

    <section class="hero">
        <h1>{ai_content['hero_title']}</h1>
        <p>{ai_content['hero_subtitle']}</p>
        <a href="#contact" class="btn">Получить консультацию</a>
    </section>

    <section class="section">
        <h2 class="section-title">Почему выбирают нас</h2>
        <ul class="features-grid">
            {features_html}
        </ul>
    </section>

    <section class="section">
        <h2 class="section-title">Наши Услуги</h2>
        <div class="services-grid">
            {services_html}
        </div>
    </section>

    <section class="section" id="contact">
        <div class="cta-box">
            <h2>Свяжитесь с нами</h2>
            <p>{ai_content['cta_text']}</p>
            <a href="tel:{phone}" class="btn" style="background: white; color: var(--primary);">Позвонить: {phone}</a>
            <span class="legal-notice">🔒 Отправляя данные, вы соглашаетесь на обработку персональных данных согласно 152-ФЗ РФ.</span>
        </div>
    </section>

    <footer>
        <p>© {company_name}. Все права защищены.</p>
        <p style="margin-top: 8px;"><a href="#" onclick="alert('Политика конфиденциальности: Данный сайт защищает ваши персональные данные в соответствии с Федеральным законом № 152-ФЗ РФ.'); return false;">Политика конфиденциальности (152-ФЗ)</a></p>
    </footer>
</body>
</html>
"""
    output_path = SITES_OUTPUT_DIR / f"{site_id}.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return str(output_path)
