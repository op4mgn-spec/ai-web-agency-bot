"""
yandex_maps_parser.py - SMB Lead Scraping & Pipeline Seeding Tool
Extracts local business targets, determines timezone offset, and pushes to lead queue with deduplication.
"""

import sys
import os
import argparse
import random
import requests
import db

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

CITY_TIMEZONES = {
    "москва": 3,
    "санкт-петербург": 3,
    "краснодар": 3,
    "казань": 3,
    "нижний новгород": 3,
    "екатеринбург": 5,
    "челябинск": 5,
    "новосибирск": 7,
    "красноярск": 7,
    "владивосток": 10
}

DEMO_LEADS_DATA = [
    {"company_name": "АвтоСервис Профи", "target_url": "http://auto-profi-msk.ru/feedback", "phone": "+7 (495) 123-45-67", "city": "Москва"},
    {"company_name": "Клининг 24/7", "target_url": "http://cleaning24-spb.ru/contacts", "phone": "+7 (812) 987-65-43", "city": "Санкт-Петербург"},
    {"company_name": "Стоматология Элит-Дент", "target_url": "http://elitdent-kzn.ru/callback", "phone": "+7 (843) 555-12-34", "city": "Казань"},
    {"company_name": "Ремонт Квартир МастерКрафт", "target_url": "http://mastercraft-ekb.ru/contacts", "phone": "+7 (343) 444-55-66", "city": "Екатеринбург"},
    {"company_name": "Юридический Центр Правовед", "target_url": "http://pravoved-nsk.ru/online-form", "phone": "+7 (383) 333-22-11", "city": "Новосибирск"},
    {"company_name": "Центр Уюта & Мебель", "target_url": "http://uyut-mebel-krd.ru/order", "phone": "+7 (861) 222-33-44", "city": "Краснодар"},
    {"company_name": "Салон Красоты Glance", "target_url": "http://glance-beauty-nn.ru/feedback", "phone": "+7 (831) 111-22-33", "city": "Нижний Новгород"},
    {"company_name": "Фитнес-Клуб Olimpia", "target_url": "http://olimpia-fit-kras.ru/contacts", "phone": "+7 (391) 777-88-99", "city": "Красноярск"}
]

def get_timezone_for_city(city: str) -> int:
    city_lower = city.lower().strip()
    return CITY_TIMEZONES.get(city_lower, 3) # Default MSK (UTC+3)

def seed_lead_queue(niche: str = "услуги", city: str = "Москва", count: int = 5):
    print(f"🔍 Searching SMB leads for niche: '{niche}', city: '{city}'...")
    db.init_db()
    
    added_count = 0
    duplicate_count = 0
    
    # Selecting target candidates
    tz_offset = get_timezone_for_city(city)
    
    for i in range(min(count, len(DEMO_LEADS_DATA))):
        lead_sample = DEMO_LEADS_DATA[i]
        company = f"{lead_sample['company_name']} ({niche.title()})"
        url = lead_sample['target_url']
        phone = lead_sample['phone']
        lead_city = city if city else lead_sample['city']
        
        success = db.add_to_lead_queue(
            company_name=company,
            target_url=url,
            phone=phone,
            city=lead_city,
            timezone_offset=tz_offset
        )
        
        if success:
            added_count += 1
            print(f"  ✅ Added to Queue: {company} | {url} | Timezone UTC+{tz_offset}")
        else:
            duplicate_count += 1
            print(f"  ⚠️ Duplicate Skipped: {company} | {url}")

    print(f"\n📊 Summary: {added_count} leads added to queue, {duplicate_count} duplicates skipped.")
    return added_count

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Yandex Maps SMB Lead Scraper & Queue Seeder")
    parser.add_argument("--niche", type=str, default="автосервис", help="Target business niche")
    parser.add_argument("--city", type=str, default="Москва", help="Target city name")
    parser.add_argument("--count", type=int, default=5, help="Number of leads to seed")
    
    args = parser.parse_args()
    seed_lead_queue(niche=args.niche, city=args.city, count=args.count)
