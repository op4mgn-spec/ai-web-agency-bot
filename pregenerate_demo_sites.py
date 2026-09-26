"""
pregenerate_demo_sites.py - Generates 6 Niche Demo Landing Pages for AI Web Agency
"""

import sys
import os
import db
from generator import generate_website_html

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

DEMO_NICHES = [
    {
        "id": "demo_auto",
        "company_name": "АвтоТехЦентр 'DrivePro'",
        "niche": "Автосервис и СТО",
        "phone": "+7 (495) 777-11-22",
        "services": "Компьютерная диагностика, ремонт ДВС и КПП, замена масла, шиномонтаж 24/7",
        "utp": "Диагностика бесплатно при ремонте. Гарантия 1 год на все работы и запчасти.",
        "color_theme": "#ef4444" # Red
    },
    {
        "id": "demo_cleaning",
        "company_name": "Клининг-Сервис 'Чистый Дом'",
        "niche": "Уборка и клининг",
        "phone": "+7 (812) 888-33-44",
        "services": "Генеральная уборка квартир, мойка окон, химчистка мебели и ковров, уборка после ремонта",
        "utp": "Безопасная гипоаллергенная химия. Расчет стоимости по фото за 5 минут!",
        "color_theme": "#06b6d4" # Cyan
    },
    {
        "id": "demo_dental",
        "company_name": "Стоматология 'ДентаКлиник'",
        "niche": "Стоматология и медицина",
        "phone": "+7 (843) 555-99-00",
        "services": "Лечение зубов без боли, имплантация под ключ, виниры, отбеливание Zoom 4",
        "utp": "Первичный осмотр и снимки — 0 руб. Лечение в рассрочку 0% на 12 месяцев.",
        "color_theme": "#10b981" # Emerald Green
    },
    {
        "id": "demo_repair",
        "company_name": "Ремонтно-Строительная Компания 'МастерСтрой'",
        "niche": "Ремонт квартир и офисов",
        "phone": "+7 (343) 444-22-11",
        "services": "Дизайнерский ремонт под ключ, черновая отделка, сантехника и электрика",
        "utp": "Фиксированная смета без доплат. Клининг и вывоз мусора в подарок!",
        "color_theme": "#f59e0b" # Amber / Orange
    },
    {
        "id": "demo_legal",
        "company_name": "Юридическое Бюро 'Правовой Щит'",
        "niche": "Юридические услуги и защита",
        "phone": "+7 (383) 333-66-55",
        "services": "Списание долгов и банкротство, арбитражные споры, защита бизнеса",
        "utp": "Оплата за результат по договору. 98% выигранных дел в судах.",
        "color_theme": "#3b82f6" # Royal Blue
    },
    {
        "id": "demo_beauty",
        "company_name": "Салон Красоты 'Beauty Lounge'",
        "niche": "Салон красоты и спа",
        "phone": "+7 (861) 222-88-99",
        "services": "Стрижки и окрашивание, лазерная эпиляция, маникюр и педикюр, уход за лицом",
        "utp": "Скидка 20% на первый визит! Онлайн-запись 24/7 и напитки бесплатно.",
        "color_theme": "#ec4899" # Pink
    }
]

def build_all_demos():
    print("==========================================")
    print("🎨 BUILDING 6 NICHE DEMO LANDING PAGES")
    print("==========================================")
    
    generated_paths = {}
    for demo in DEMO_NICHES:
        site_id = demo["id"]
        print(f"🔨 Generating demo site for: {demo['company_name']} ({demo['niche']})...")
        path = generate_website_html(demo, site_id)
        generated_paths[site_id] = path
        print(f"   ✅ Saved to: {path}")

    print("\n🎉 ALL 6 DEMO LANDING PAGES SUCCESSFULLY GENERATED!")
    return generated_paths

if __name__ == "__main__":
    build_all_demos()
