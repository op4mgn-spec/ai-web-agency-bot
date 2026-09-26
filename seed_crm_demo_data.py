import os
import sqlite3
import json
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "agency.db")

def seed_demo_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("[+] Seeding comprehensive demo CRM data across all sales funnel stages...")

    demo_leads = [
        {
            "telegram_id": 10001,
            "username": "alex_smirnov_auto",
            "full_name": "Алексей Смирнов (Автосервис)",
            "status": "NEW",
            "brief_step": 0,
            "brief_data": "{}",
            "bot_variant": "Variant A (Консультант)",
            "site_url": "",
            "site_path": "",
            "feedback": "Первичный вопрос по автосервису",
            "dialog": [
                ("USER", "/start"),
                ("BOT", "👋 Здравствуйте, Алексей!\n\nЯ — ИИ-консультант **AI Web Studio**.\nМы создаем продающие сайты под ключ за 24 часа всего за 9 900 руб.\n\n💬 Задайте мне любой вопрос текстом или 🎤 **надиктуйте голосом**!"),
                ("USER", "Здравствуйте! Подскажите, сколько стоит сделать сайт для автосервиса в Москве?"),
                ("BOT", "Здравствуйте, Алексей! Разработка продающего сайта для автосервиса под ключ стоит 9 900 руб., срок выполнения — всего 24 часа. В стоимость входит адаптивный дизайн, форма онлайн-записи и установка Яндекс Метрики. Показать вам готовые демо-примеры по автосервису?"),
                ("USER", "🔘 [Нажата кнопка: show_demo_niches]"),
                ("BOT", "🎨 Вот готовый интерактивный демо-сайт автосервиса: https://ai-web-agency-bot.onrender.com/generated_sites/demo_auto.html"),
                ("USER", "🎤 [Голосовое сообщение]"),
                ("BOT", "🎧 *Распознаю голосовое сообщение...*"),
                ("BOT", "🎤 **Распознано**: «_Посмотрел демо, выглядит солидно. А как происходит оформление заявки?_»"),
                ("BOT", "Все очень просто! Нажмите кнопку ниже и ответьте на 7 вопросов брифа текстом или 🎤 голосом, и мы начнем подготовку вашего сайта!")
            ]
        },
        {
            "telegram_id": 10002,
            "username": "cleaning_maria",
            "full_name": "Мария Ковалева (Клининг)",
            "status": "INCOMPLETE_BRIEF",
            "brief_step": 3,
            "brief_data": json.dumps({"company_name": "Чистый Дом 24", "niche": "Уборка квартир и офисов"}),
            "bot_variant": "Variant B (Прямые Продажи)",
            "site_url": "",
            "site_path": "",
            "feedback": "Бросила бриф на шаге 3/7",
            "dialog": [
                ("USER", "/start"),
                ("BOT", "👋 Здравствуйте, Мария!\nЯ — ИИ-консультант AI Web Studio..."),
                ("USER", "🔘 [Нажата кнопка: start_brief]"),
                ("BOT", "📋 **Разработка сайта — Шаг 1 из 7**\n\nНапишите или 🎤 **надиктуйте голосом** официальное название вашей компании:"),
                ("USER", "Клининговая компания «Чистый Дом 24»"),
                ("BOT", "✅ Принято!\n\n**Шаг 2 из 7**: Напишите или 🎤 **надиктуйте голосом** вашу сферу бизнеса и целевую аудиторию:"),
                ("USER", "Уборка квартир, генеральная уборка и мытье окон для частных клиентов в Санкт-Петербурге"),
                ("BOT", "✅ Отлично!\n\n**Шаг 3 из 7**: Напишите или 🎤 **надиктуйте голосом** основные товары/услуги и цены:"),
                ("BOT", "⚠️ **Авто-дожим по брифу**: Мария, вы остановились на шаге 3 из 7 (Услуги и цены). Завершите бриф текстом или голосом, чтобы мы зафиксировали за вами стоимость 9 900 руб!")
            ]
        },
        {
            "telegram_id": 10003,
            "username": "volkov_stomatology",
            "full_name": "Дмитрий Волков (Стоматология)",
            "status": "OBJECTION",
            "brief_step": 0,
            "brief_data": "{}",
            "bot_variant": "Variant B (Прямые Продажи)",
            "site_url": "",
            "site_path": "",
            "feedback": "Возражение по цене: у фрилансера 3000 руб",
            "dialog": [
                ("USER", "Здравствуйте! 9 900 руб за сайт — это дорого. Мне студент-фрилансер обещал сделать за 3 000 рублей."),
                ("BOT", "Дмитрий, отличный вопрос! Давайте честно сравним: за 3 000 руб фрилансер будет делать сайт 3-4 недели, может пропасть со связи, а верстка будет тормозить на смартфонах. У нас за 9 900 руб вы получаете готовый продающий сайт за 24 часа с проверкой арт-директора, мобильной адаптацией и установленной Яндекс Метрикой. Каждая первая же заявка от пациента окупит эту разницу! Запустим бриф?"),
                ("USER", "Нет, спасибо. 3 000 руб меня устраивает больше. Если сорвет сроки — вернусь к вам."),
                ("BOT", "Принято, Дмитрий! Наш бот и контакты всегда под рукой. Если возникнут задержки с фрилансером — пишите, сделаем под ключ за 24 часа!")
            ]
        },
        {
            "telegram_id": 10004,
            "username": "elena_legal_services",
            "full_name": "Елена Морозова (Юрист)",
            "status": "REJECTED",
            "brief_step": 0,
            "brief_data": "{}",
            "bot_variant": "Variant D (Архитектор Решений)",
            "site_url": "",
            "site_path": "",
            "feedback": "Недоверие к ИИ: опасается ошибок в текстах",
            "dialog": [
                ("USER", "Я юрист. Нейросети не могут составить грамотный сайт по праву. Это будет шаблонный текст с ошибками в законах."),
                ("BOT", "Елена, вы совершенно правы: слепо доверять юридические тексты только ИИ нельзя! Наша технология — это 'AI Speed + Human QA'. ИИ строит современный дизайн и структуру за минуты, но перед сдачей тексты и верстку лично проверяет и утверждает арт-директор. Вы можете сами продиктовать любые юридические формулировки!"),
                ("USER", "🎤 [Голосовое сообщение]"),
                ("BOT", "🎧 *Распознаю голосовое сообщение...*"),
                ("BOT", "🎤 **Распознано**: «_Пока не готова рисковать репутацией. Вернемся к вопросу в следующем месяце._»"),
                ("BOT", "Понимаем вас, Елена! Спасибо за открытость. Зафиксировали ваш запрос, будем на связи!")
            ]
        },
        {
            "telegram_id": 10005,
            "username": "petrov_repair",
            "full_name": "Сергей Петров (Ремонт квартир)",
            "status": "OBJECTION",
            "brief_step": 0,
            "brief_data": "{}",
            "bot_variant": "Variant C (Демо-Специалист)",
            "site_url": "",
            "site_path": "",
            "feedback": "Возражение по предоплате: требовал сначала сделать сайт",
            "dialog": [
                ("USER", "Я не плачу предоплату. Сделайте сначала сайт под мой ремонт квартир, а если понравится — я заплачу 9 900."),
                ("BOT", "Сергей, мы отлично понимаем ваше желание обезопасить себя! Именно поэтому вы прямо сейчас можете посмотреть наш интерактивный макет по ремонту квартир: https://ai-web-agency-bot.onrender.com/generated_sites/demo_repair.html. Заполнение брифа абсолютно бесплатно, а оплата происходит только перед выгрузкой готовности!"),
                ("USER", "Я подумаю над этим. Позже напишу."),
                ("BOT", "Хорошо, Сергей! Всегда рад помочь. Нажмите /start, когда будете готовы!")
            ]
        },
        {
            "telegram_id": 10006,
            "username": "sokolova_beauty",
            "full_name": "Ольга Соколова (СПА-салон)",
            "status": "WAITING_PAYMENT",
            "brief_step": 7,
            "brief_data": json.dumps({
                "company_name": "Luxe Beauty SPA",
                "niche": "Салон красоты и СПА",
                "services": "Массаж, уход за лицом, маникюр",
                "utp": "Скидка 20% новым клиентам на первый визит",
                "color_theme": "Нюдовый, бежевый и золото",
                "blocks": "Прайс, Отзывы, Форма онлайн-записи",
                "phone": "+7 (999) 123-45-67"
            }, ensure_ascii=False),
            "bot_variant": "Variant A (Консультант)",
            "site_url": "",
            "site_path": "",
            "feedback": "Бриф полностью заполнен, ожидает оплаты",
            "dialog": [
                ("USER", "Отправила номер телефона и все ответы по брифу."),
                ("BOT", "🎉 **Бриф успешно сформирован!**\n\n🏢 Компания: Luxe Beauty SPA\n🎯 Ниша: Салон красоты и СПА\n🛠 Услуги: Массаж, уход за лицом, маникюр\n⭐ УТП: Скидка 20% новым клиентам\n🎨 Цвета: Нюдовый, бежевый и золото\n📞 Телефон: +7 (999) 123-45-67\n\n💰 **Стоимость разработки**: 9 900 руб."),
                ("USER", "Отлично, как произвести оплату?"),
                ("BOT", "Вы можете произвести симуляцию оплаты по кнопке ниже!")
            ]
        },
        {
            "telegram_id": 10007,
            "username": "vasiliev_dent",
            "full_name": "Игорь Васильев (Стоматология)",
            "status": "GENERATED",
            "brief_step": 7,
            "brief_data": json.dumps({
                "company_name": "Дента Плюс",
                "niche": "Стоматологический центр",
                "services": "Имплантация, отбеливание, брекеты",
                "utp": "Бесплатный снимок и первичная консультация",
                "color_theme": "Бело-голубой медицинский",
                "blocks": "Врачи, Услуги, Цены, Запись",
                "phone": "+7 (495) 777-88-99"
            }, ensure_ascii=False),
            "bot_variant": "Variant C (Демо-Специалист)",
            "site_url": "https://ai-web-agency-bot.onrender.com/generated_sites/demo_dental.html",
            "site_path": "generated_sites/demo_dental.html",
            "feedback": "Сайт сгенерирован ИИ, ожидает проверки арт-директора",
            "dialog": [
                ("USER", "🔘 [Нажата кнопка: pay_order]"),
                ("BOT", "✅ **Оплата принята (9 900 руб.)!** Ваш заказ передан арт-директору (@bers1q). Ведется сборка лендинга!"),
                ("BOT", "⏳ ИИ сгенерировал верстку для «Дента Плюс». Направлено на утверждение арт-директору.")
            ]
        },
        {
            "telegram_id": 10008,
            "username": "romanov_auto",
            "full_name": "Михаил Романов (Автотехцентр)",
            "status": "DELIVERED",
            "brief_step": 7,
            "brief_data": json.dumps({
                "company_name": "АвтоТехЦентр Романов",
                "niche": "Ремонт двигателей и КПП",
                "services": "Капитальный ремонт ДВС, диагностика, замена масла",
                "utp": "Гарантия 2 года на все выполненные работы",
                "color_theme": "Темно-серый с оранжевыми акцентами",
                "blocks": "Калькулятор ремонта, Отзывы, Карта проезда",
                "phone": "+7 (495) 111-22-33"
            }, ensure_ascii=False),
            "bot_variant": "Variant B (Прямые Продажи)",
            "site_url": "https://ai-web-agency-bot.onrender.com/generated_sites/demo_auto.html",
            "site_path": "generated_sites/demo_auto.html",
            "feedback": "Успешная сделка! Сайт передан клиенту",
            "dialog": [
                ("USER", "Ребята, спасибо огромнейшее! Сайт запущен в Яндекс Директ, уже получили первых 5 клиентов за день!"),
                ("BOT", "Михаил, замечательный результат! Рады сотрудничеству! По любым вопросам продвижения — мы всегда на связи!")
            ]
        }
    ]

    for lead in demo_leads:
        # Upsert lead into database
        cursor.execute("DELETE FROM leads WHERE telegram_id = ?", (lead["telegram_id"],))
        cursor.execute("DELETE FROM messages WHERE telegram_id = ?", (lead["telegram_id"],))

        now_str = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO leads (telegram_id, username, full_name, status, brief_step, brief_data, bot_variant, site_url, site_path, feedback, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            lead["telegram_id"],
            lead["username"],
            lead["full_name"],
            lead["status"],
            lead["brief_step"],
            lead["brief_data"],
            lead["bot_variant"],
            lead["site_url"],
            lead["site_path"],
            lead["feedback"],
            now_str,
            now_str
        ))

        # Insert full chat dialog history
        base_time = datetime.now() - timedelta(hours=len(lead["dialog"]))
        for idx, (sender, text) in enumerate(lead["dialog"]):
            msg_time = (base_time + timedelta(minutes=idx * 5)).isoformat()
            cursor.execute("""
                INSERT INTO messages (telegram_id, sender, text, bot_variant, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (lead["telegram_id"], sender, text, lead["bot_variant"], msg_time))

    conn.commit()
    conn.close()
    print("[+] Successfully seeded 8 rich demo leads across ALL CRM funnel stages!")

if __name__ == "__main__":
    seed_demo_data()
