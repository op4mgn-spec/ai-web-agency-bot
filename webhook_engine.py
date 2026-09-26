import os
import json
import logging
import base64
import requests
import db
from generator import generate_website_html

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "8740453272:AAG5MyW2cvsiPaRT3i3V4feM7bRKoGhyFbU"
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# User state memory for brief steps
user_states = {}

def transcribe_voice_note(file_id: str) -> str:
    global GEMINI_API_KEY, TELEGRAM_BOT_TOKEN
    key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY or db.get_setting("GEMINI_API_KEY")
    if not key:
        return ""
        
    try:
        # Step 1: Get Telegram file path
        r = requests.get(f"{API_URL}/getFile?file_id={file_id}", timeout=5).json()
        if not r.get("ok"):
            return ""
        file_path = r["result"]["file_path"]
        
        # Step 2: Download raw voice audio bytes
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        audio_bytes = requests.get(file_url, timeout=10).content
        base64_audio = base64.b64encode(audio_bytes).decode('utf-8')

        # Step 3: Call Gemini API multimodal audio endpoint
        models_to_try = get_working_models(key)
        for model_name in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "audio/ogg",
                                "data": base64_audio
                            }
                        },
                        {
                            "text": "Расшифруй это голосовое сообщение от клиента на русском языке. Напиши только распознанный текст."
                        }
                    ]
                }]
            }
            res = requests.post(url, json=payload, headers=headers, timeout=15).json()
            if "candidates" in res and len(res["candidates"]) > 0:
                parts = res["candidates"][0].get("content", {}).get("parts", [])
                if parts and "text" in parts[0]:
                    return parts[0]["text"].strip()
    except Exception as e:
        print(f"Error transcribing voice note: {e}")
    return ""

PERSONA_PROMPTS = {
    "Variant A (Консультант)": """
Ты — старший ИИ-консультант веб-студии AI Web Studio. 
Твой стиль: заботливый, экспертный, вежливый. 
Твоя цель: ответить на вопросы клиента про разработку сайтов, объяснить ценность гибридной разработки (скорость ИИ + ручной контроль арт-директором studio), цены (9 900 руб) и сроки (24 часа).
Мягко подводи клиента к заполнению 7 шагов брифа.
""",
    "Variant B (Прямые Продажи)": """
Ты — энергичный ведущий менеджер по продажам AI Web Studio. 
Твой стиль: активный, уверенный, ориентированный на выгоду и срочность.
Твоя цель: подчеркнуть супер-цену (9 900 руб вместо 45 000 руб), рекордный срок (24 часа) и дать мощный призыв запустить бриф прямо сейчас.
""",
    "Variant C (Демо-Специалист)": """
Ты — визуальный специалист и демо-презентатор AI Web Studio. 
Твой стиль: креативный, лаконичный, сфокусированный на дизайне, адаптивности и visual UX.
Твоя цель: показать, как здорово будет выглядеть готовый сайт клиента, и предложить прямо сейчас собрать первый макет по брифу.
""",
    "Variant D (Архитектор Решений)": """
Ты — технический архитектор и маркетолог AI Web Studio. 
Твой стиль: аналитический, системный, сфокусированный на конверсии, SEO и воронках продаж.
Твоя цель: объяснить клиенту, как сайт будет приводить заявки, какие блоки нужны в его нише, и предложить заполнить бриф.
"""
}
SYSTEM_SALES_PROMPT = PERSONA_PROMPTS["Variant A (Консультант)"]

def send_telegram_message(chat_id, text, reply_markup=None, parse_mode="Markdown", bot_variant=""):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        r = requests.post(f"{API_URL}/sendMessage", json=payload, timeout=5)
        # Automatically log every outbound bot message into agency.db
        if text and str(chat_id).replace("-", "").isdigit():
            db.log_chat_message(int(chat_id), "BOT", text, bot_variant)
        return r.json()
    except Exception as e:
        print(f"Error sending telegram message: {e}")
        return None

def answer_callback_query(callback_query_id):
    try:
        requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": callback_query_id}, timeout=3)
    except Exception:
        pass

CACHED_WORKING_MODEL = None

def get_working_models(key):
    global CACHED_WORKING_MODEL
    if CACHED_WORKING_MODEL:
        return [CACHED_WORKING_MODEL]
    
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        r = requests.get(url, timeout=5)
        data = r.json()
        if "models" in data:
            valid_models = []
            for m in data["models"]:
                name = m.get("name", "").replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    valid_models.append(name)
            if valid_models:
                print(f"✅ Discovered valid Gemini models for key: {valid_models}")
                return valid_models
    except Exception as e:
        print(f"Error querying ListModels: {e}")
    
    return ['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-2.5-flash']

def safe_generate_ai(prompt, chat_id=None):
    global GEMINI_API_KEY, CACHED_WORKING_MODEL
    key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY or db.get_setting("GEMINI_API_KEY")
    if not key or key == "your_gemini_api_key_here":
        print("Gemini API Key is missing or default")
        return "", "Ключ Gemini API не настроен. Отправьте команду /setkey AIzaSy... для подключения."

    models_to_try = get_working_models(key)
    errors = []

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
        headers = {"Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=10)
            data = r.json()
            if "candidates" in data and len(data["candidates"]) > 0:
                parts = data["candidates"][0].get("content", {}).get("parts", [])
                if parts and "text" in parts[0]:
                    CACHED_WORKING_MODEL = model_name
                    return parts[0]["text"].strip(), None
            elif "error" in data:
                err_msg = data['error'].get('message', str(data['error']))
                print(f"Gemini API Error ({model_name}): {err_msg}")
                errors.append(f"{model_name}: {err_msg}")
        except Exception as e:
            print(f"Gemini REST Exception ({model_name}): {e}")
            errors.append(f"{model_name}: {str(e)}")
            continue

    CACHED_WORKING_MODEL = None
    last_err = "; ".join(errors) if errors else "Неизвестная ошибка Gemini API"
    return "", last_err

DEMO_NICHES = {
    "auto": {"title": "🚘 Автосервис & СТО", "file": "demo_auto.html", "keywords": ["авто", "сто", "шиномонтаж", "машин", "сервис"]},
    "cleaning": {"title": "🧹 Клининг & Уборка", "file": "demo_cleaning.html", "keywords": ["клининг", "уборк", "чистк", "мытье"]},
    "dental": {"title": "🦷 Стоматология & Медицина", "file": "demo_dental.html", "keywords": ["стоматолог", "зуб", "медицин", "клиник", "врач"]},
    "repair": {"title": "🔨 Ремонт квартир", "file": "demo_repair.html", "keywords": ["ремонт", "отделк", "строй", "квартир"]},
    "legal": {"title": "⚖️ Юридические услуги", "file": "demo_legal.html", "keywords": ["юрист", "адвокат", "право", "юридич"]},
    "beauty": {"title": "💅 Салон красоты & СПА", "file": "demo_beauty.html", "keywords": ["салон", "красот", "спа", "массаж", "маникюр", "парикмахер"]}
}

def detect_niche_key(text: str) -> str:
    if not text:
        return None
    text_lower = text.lower()
    for key, info in DEMO_NICHES.items():
        for kw in info["keywords"]:
            if kw in text_lower:
                return key
    return None

def process_telegram_update(update_data):
    global GEMINI_API_KEY, ADMIN_TELEGRAM_ID
    db.init_db()

    # Handle Callback Queries (Button Clicks)
    if "callback_query" in update_data:
        cb = update_data["callback_query"]
        answer_callback_query(cb["id"])
        user = cb["from"]
        chat_id = user["id"]
        data = cb["data"]
        
        lead = db.get_or_create_lead(chat_id, user.get("username", ""), user.get("first_name", ""))
        bot_variant = lead.get("bot_variant", "Variant A (Консультант)")

        # Log button click interaction to database
        db.log_chat_message(chat_id, "USER", f"🔘 [Нажата кнопка: {data}]", bot_variant)

        if data == "start_brief":
            user_states[chat_id] = {"step": 1, "brief": {}}
            db.update_brief_step(chat_id, 1)
            msg = "📋 **Разработка сайта — Шаг 1 из 7**\n\nНапишите или 🎤 **надиктуйте голосом** официальное название вашей компании или проекта:"
            db.log_chat_message(chat_id, "BOT", msg, bot_variant)
            send_telegram_message(chat_id, msg)

        elif data == "ask_question":
            user_states[chat_id] = {"step": None}
            msg = "💬 Задайте любой вопрос текстом или 🎤 **надиктуйте голосом** по созданию сайта, стоимости или гарантиям!"
            db.log_chat_message(chat_id, "BOT", msg, bot_variant)
            send_telegram_message(chat_id, msg)

        elif data == "contact_info":
            msg = "📞 **Связь со службой поддержки AI Web Studio**\n\nВы можете задать любой вопрос прямо сюда в чат, надиктовать голосом или написать нашим специалистам!"
            db.log_chat_message(chat_id, "BOT", msg, bot_variant)
            send_telegram_message(chat_id, msg)

        elif data in ["show_demo_niches", "show_all_demo_niches"]:
            crm_base = os.getenv("RENDER_EXTERNAL_URL") or "https://ai-web-agency-bot.onrender.com"
            base = crm_base.rstrip('/')
            
            brief_data = json.loads(lead.get("brief_data", "{}"))
            client_niche = brief_data.get("niche", "") or lead.get("full_name", "")
            niche_key = detect_niche_key(client_niche) if data == "show_demo_niches" else None

            if niche_key and data != "show_all_demo_niches":
                info = DEMO_NICHES[niche_key]
                demo_url = f"{base}/generated_sites/{info['file']}"
                msg = (
                    f"🎯 **Интерактивный демо-сайт специально для вашей ниши ({info['title']})**\n\n"
                    f"Мы подготовили рабочий пример продающего лендинга под вашу сферу бизнеса! "
                    f"Нажмите кнопку ниже, чтобы открыть его в браузере:"
                )
                kbd = {"inline_keyboard": [
                    [{"text": f"🌐 Открыть демо: {info['title']}", "url": demo_url}],
                    [{"text": "🎨 Посмотреть демо всех 6 ниш", "callback_data": "show_all_demo_niches"}],
                    [{"text": "📝 Заполнить бриф на сайт", "callback_data": "start_brief"}]
                ]}
            else:
                msg = "🎨 **Примеры готовых сайтов по популярным нишам**\n\nВыберите вашу сферу бизнеса, чтобы открылся интерактивный демо-сайт:"
                kbd = {"inline_keyboard": [
                    [{"text": "🚘 Автосервис & СТО", "url": f"{base}/generated_sites/demo_auto.html"}],
                    [{"text": "🧹 Клининг & Уборка", "url": f"{base}/generated_sites/demo_cleaning.html"}],
                    [{"text": "🦷 Стоматология & Медицина", "url": f"{base}/generated_sites/demo_dental.html"}],
                    [{"text": "🔨 Ремонт квартир", "url": f"{base}/generated_sites/demo_repair.html"}],
                    [{"text": "⚖️ Юридические услуги", "url": f"{base}/generated_sites/demo_legal.html"}],
                    [{"text": "💅 Салон красоты & СПА", "url": f"{base}/generated_sites/demo_beauty.html"}]
                ]}
            db.log_chat_message(chat_id, "BOT", msg, bot_variant)
            send_telegram_message(chat_id, msg, reply_markup=kbd)
            return

        elif data == "pay_order":
            db.update_lead_status(chat_id, "PAID")
            msg = "✅ **Оплата принята (9 900 руб.)!**\n\nВаш заказ передан арт-директору студии. После проверки брифа и утверждения верстки ваш сайт будет выслан вам в этот чат!"
            db.log_chat_message(chat_id, "BOT", msg, bot_variant)
            send_telegram_message(chat_id, msg)

            # Alert Admin @bers1q
            admin_id = ADMIN_TELEGRAM_ID or chat_id
            brief_data = json.loads(lead.get("brief_data", "{}"))
            alert = (
                f"💰 **НОВАЯ ОПЛАТА (9 900 руб)!**\n\n"
                f"👤 Заказчик: {user.get('first_name')} (@{user.get('username')})\n"
                f"🏢 Компания: {brief_data.get('company_name', 'Не указано')}\n"
                f"📞 Телефон: {brief_data.get('phone', 'Не указано')}\n\n"
                f"Запустить генерацию сайта?"
            )
            kbd = {"inline_keyboard": [[{"text": "🔨 Сгенерировать сайт", "callback_data": f"admin_gen_{chat_id}"}]]}
            send_telegram_message(admin_id, alert, reply_markup=kbd)

        elif data.startswith("admin_gen_"):
            target_id = int(data.split("_")[2])
            leads = db.get_all_leads_crm()
            target = next((l for l in leads if l['telegram_id'] == target_id), None)
            if target:
                brief_data = json.loads(target.get("brief_data", "{}"))
                send_telegram_message(chat_id, f"⏳ Начинаю ИИ-генерацию сайта для {brief_data.get('company_name')}...")
                site_id = f"lead_{target_id}"
                html_path = generate_website_html(brief_data, site_id)
                db.save_generated_site(target_id, f"http://localhost:8000/generated_sites/{site_id}.html", html_path)

                review = (
                    f"✅ **САЙТ СГЕНЕРИРОВАН!**\n\n"
                    f"🏢 Проект: {brief_data.get('company_name')}\n"
                    f"📄 Файл: `{html_path}`\n\n"
                    f"Утверждаете вариант для отправки клиенту?"
                )
                kbd = {"inline_keyboard": [
                    [{"text": "🚀 Утвердить и отправить", "callback_data": f"admin_app_{target_id}"}],
                    [{"text": "🔄 Перегенерировать", "callback_data": f"admin_gen_{target_id}"}]
                ]}
                send_telegram_message(chat_id, review, reply_markup=kbd)

        elif data.startswith("admin_app_"):
            target_id = int(data.split("_")[2])
            db.update_lead_status(target_id, "DELIVERED")
            leads = db.get_all_leads_crm()
            target = next((l for l in leads if l['telegram_id'] == target_id), None)
            brief_data = json.loads(target.get("brief_data", "{}")) if target else {}
            
            client_msg = (
                f"🎉 **Ваш сайт создан и утвержден арт-директором!**\n\n"
                f"🏢 Проект: {brief_data.get('company_name')}\n"
                f"Напишите прямо сюда, если хотите внести какие-либо правки!"
            )
            send_telegram_message(target_id, client_msg)
            send_telegram_message(chat_id, f"✅ Готово! Сайт отправлен клиенту (@{target.get('username') if target else ''}).")

        return

    # Handle Normal & Media Messages
    if "message" in update_data:
        msg = update_data["message"]
        user = msg["from"]
        chat_id = user["id"]
        
        text = msg.get("text", "").strip()
        if not text:
            if "voice" in msg:
                file_id = msg["voice"]["file_id"]
                send_telegram_message(chat_id, "🎧 *Распознаю голосовое сообщение...*")
                transcribed = transcribe_voice_note(file_id)
                if transcribed:
                    text = transcribed
                    send_telegram_message(chat_id, f"🎤 **Распознано**: «_{text}_»")
                else:
                    text = "🎤 [Голосовое сообщение]"
            elif "photo" in msg:
                text = "📷 [Фотографическое изображение]"
            elif "document" in msg:
                text = "📄 [Вложенный файл]"
            elif "sticker" in msg:
                text = "😊 [Стикер]"
            elif "caption" in msg:
                text = f"📷 {msg['caption']}"
            else:
                text = "[Нетекстовое сообщение]"

        lead = db.get_or_create_lead(chat_id, user.get("username", ""), user.get("first_name", ""))
        bot_variant = lead.get("bot_variant", "Variant A (Консультант)")

        db.log_chat_message(chat_id, "USER", text, bot_variant)

        user_username = (user.get("username") or "").lower().replace("@", "")
        user_id_str = str(chat_id)
        if user_username == "bers1q":
            ADMIN_TELEGRAM_ID = user_id_str

        is_admin = (user_username == "bers1q") or (user_id_str == str(ADMIN_TELEGRAM_ID))

        # Admin Command to set Gemini API key directly from Telegram!
        if text.startswith("/setkey"):
            parts = text.split(maxsplit=1)
            if len(parts) > 1:
                new_key = parts[1].strip()
                if not new_key.startswith("AIza"):
                    send_telegram_message(chat_id, "⚠️ **Ошибка**: Ключ Gemini API должен начинаться с `AIza...`\nСкопируйте ключ из Google AI Studio: https://aistudio.google.com/app/apikey")
                    return

                ADMIN_TELEGRAM_ID = user_id_str
                GEMINI_API_KEY = new_key
                os.environ["GEMINI_API_KEY"] = new_key
                db.set_setting("GEMINI_API_KEY", new_key)
                db.set_setting("ADMIN_TELEGRAM_ID", user_id_str)

                # Perform live API test immediately
                test_ans, test_err = safe_generate_ai("Привет! Проверка работы ключа.", chat_id)
                if test_ans:
                    msg = (
                        f"✅ **Gemini API Key успешно сохранен и ПРОВЕРЕН!**\n\n"
                        f"🔑 Ключ: `{new_key[:8]}...{new_key[-4:]}`\n"
                        f"👑 Авторизован админ: @{user_username or 'пользователь'} (ID: `{chat_id}`)\n\n"
                        f"🤖 **Тестовый ответ ИИ**: \"{test_ans}\""
                    )
                else:
                    msg = (
                        f"⚠️ **Ключ сохранен в БД, но при тесте Google API вернул ошибку**:\n\n"
                        f"`{test_err}`\n\n"
                        f"Убедитесь, что ваш ключ активен в Google AI Studio."
                    )
                send_telegram_message(chat_id, msg)
            else:
                send_telegram_message(chat_id, "🔑 **Инструкция**: Отправьте команду в формате:\n`/setkey AIzaSyВашСкопированныйКлюч`")
            return

        # CRM Command to open Web CRM system directly in Telegram or Browser!
        if text in ["/crm", "/admin", "/dashboard", "/crm_dashboard"]:
            crm_base = os.getenv("RENDER_EXTERNAL_URL") or "https://ai-web-agency-bot.onrender.com"
            crm_url = f"{crm_base.rstrip('/')}/crm"
            
            if not is_admin:
                msg = "⛔️ **Доступ ограничен**. Панель CRM доступна только администраторам."
                send_telegram_message(chat_id, msg)
                return

            msg = (
                f"⚡️ **Панель управления AI Web Agency CRM**\n\n"
                f"📊 Отслеживание лидов, этапов брифов, A/B статистики и истории диалогов.\n\n"
                f"Выберите способ открытия:"
            )
            kbd = {"inline_keyboard": [
                [{"text": "📱 Открыть CRM в Telegram (WebApp)", "web_app": {"url": crm_url}}],
                [{"text": "🌐 Открыть CRM в браузере", "url": crm_url}]
            ]}
            send_telegram_message(chat_id, msg, reply_markup=kbd)
            return

        # Item 7: Dynamic Price Calculator Command
        if text in ["/calculator", "/calc", "калькулятор"]:
            msg = (
                "🧮 **Калькулятор стоимости разработки сайта**\n\n"
                "• Базовый продающий лендинг (24 часа): **9 900 руб.**\n"
                "• Настройка SEO и индексация: **+2 900 руб.**\n"
                "• Подключение Telegram / WhatsApp бота: **+3 900 руб.**\n"
                "• Срочная экспресс-сдача (12 часов): **+2 500 руб.**\n"
                "• Установка Яндекс Метрики: **Бесплатно (в подарок)**\n\n"
                "Заполните бриф, чтобы зафиксировать точную смету!"
            )
            kbd = {"inline_keyboard": [[{"text": "📝 Заполнить бриф на сайт", "callback_data": "start_brief"}]]}
            send_telegram_message(chat_id, msg, reply_markup=kbd)
            return

        # Item 41: Promo Coupon Engine Command
        if text.startswith("/promo"):
            parts = text.split(maxsplit=1)
            code = parts[1].strip().upper() if len(parts) > 1 else ""
            if code in ["START2026", "AI2026", "BERS1Q"]:
                msg = "🎉 **Промокод активирован!**\n\nВам предоставлена скидка 10% на разработку сайта. Итоговая стоимость: **8 910 руб.** вместо 9 900 руб. Нажмите запустить бриф!"
                kbd = {"inline_keyboard": [[{"text": "📝 Заполнить бриф со скидкой", "callback_data": "start_brief"}]]}
            else:
                msg = "🎟 **Введите промокод**:\nНапример: `/promo START2026` для получения скидки 10%!"
                kbd = None
            send_telegram_message(chat_id, msg, reply_markup=kbd)
            return

        # Item 23: Upsell Tier Engine Command
        if text in ["/upsell", "поддержка", "хостинг"]:
            msg = (
                "🚀 **Дополнительные пакеты поддержки и развития сайта**:\n\n"
                "1. **Пакет 'Технический Забото-Сервис'** (1 900 руб/мес):\n"
                "   • Скоростной хостинг и продление SSL-сертификата\n"
                "   • Ежемесячное обновление контента и цен\n"
                "   • Резервное копирование 24/7\n\n"
                "2. **Пакет 'SEO & Трафик'** (5 900 руб/мес):\n"
                "   • Продвижение в Яндекс и Google\n"
                "   • Настройка контекстной рекламы Яндекс Директ\n\n"
                "Напишите основателю @bers1q для подключения любого пакета!"
            )
            send_telegram_message(chat_id, msg)
            return

        # Item 31: SSL & Custom Domain Assistant Command
        if text in ["/domain", "/ssl", "домен"]:
            msg = (
                "🌐 **Инструкция по привязке вашего собственного доменного имени**:\n\n"
                "1. Перейдите в панель вашего регистратора доменов (Reg.ru, Nic.ru, Beget и др.).\n"
                "2. В настройках DNS добавьте **A-запись**:\n"
                "   • Имя (Host): `@`\n"
                "   • Значение (IP): `216.24.57.1`\n"
                "3. Наш технический специалист поможет подключить бесплатный SSL-сертификат за 5 минут!"
            )
            send_telegram_message(chat_id, msg)
            return

        # Handle /start with Deep Linking lead identification
        if text.startswith("/start"):
            user_states[chat_id] = {"step": None, "brief": {}}
            crm_base = os.getenv("RENDER_EXTERNAL_URL") or "https://ai-web-agency-bot.onrender.com"
            base = crm_base.rstrip('/')
            crm_url = f"{base}/crm"

            # Parse start payload (e.g. /start lead_1 or /start autoprofi)
            parts = text.split(maxsplit=1)
            target_lead = None
            if len(parts) > 1:
                param = parts[1].strip()
                target_lead = db.get_queue_lead_by_param(param)

            if target_lead:
                company = target_lead.get("company_name", "Ваша Компания")
                city = target_lead.get("city", "")
                target_url = target_lead.get("target_url", "")
                
                welcome = (
                    f"👋 Здравствуйте, представители компании **{company}**"
                    f"{' (' + city + ')' if city else ''}!\n\n"
                    f"🎯 Мы изучили ваш сайт (`{target_url}`) и подготовили специализированное предложение по созданию "
                    f"высококонверсионного лендинга нового поколения под ключ за 24 часа.\n\n"
                    f"💰 **Стоимость разработки под ключ**: 9 900 руб.\n"
                    f"💬 Вы можете задать вопрос текстом или 🎤 **надиктовать голосом**, а также посмотреть готовые демо-макеты!"
                )
                buttons = [
                    [{"text": "🎨 Примеры сайтов по нишам (6 демо)", "callback_data": "show_demo_niches"}],
                    [{"text": "📝 Заполнить бриф (текст или 🎤 голос)", "callback_data": "start_brief"}],
                    [{"text": "❓ Задать вопрос менеджеру", "callback_data": "ask_question"}],
                    [{"text": "📞 Контакты основателя", "callback_data": "contact_info"}]
                ]
            else:
                welcome = (
                    f"👋 Здравствуйте, {user.get('first_name')}!\n\n"
                    f"Я — ИИ-консультант **AI Web Studio**.\n"
                    f"Мы создаем продающие сайты под ключ за 24 часа всего за 9 900 руб.\n\n"
                    f"💬 Задайте мне любой вопрос текстом или 🎤 **надиктовать голосом**! Я с радостью отвечу и помогу составить бриф."
                )
                buttons = [
                    [{"text": "🎨 Примеры сайтов по нишам (6 демо)", "callback_data": "show_demo_niches"}],
                    [{"text": "📝 Заполнить бриф (текст или 🎤 голос)", "callback_data": "start_brief"}],
                    [{"text": "❓ Задать вопрос менеджеру", "callback_data": "ask_question"}],
                    [{"text": "📞 Контакты основателя", "callback_data": "contact_info"}]
                ]

            if is_admin:
                welcome += "\n\n👑 **Режим АДМИНИСТРАТОРА активен.**\n• `/crm` — открыть CRM-систему\n• `/setkey AIzaSy...` — установить Gemini API ключ"
                buttons.insert(0, [{"text": "📊 Панель управления CRM", "web_app": {"url": crm_url}}])

            kbd = {"inline_keyboard": buttons}
            db.log_chat_message(chat_id, "BOT", welcome, bot_variant)
            send_telegram_message(chat_id, welcome, reply_markup=kbd)
            return

        # Handle 7-Step Brief
        state = user_states.get(chat_id, {})
        step = state.get("step")

        if step == 1:
            state["brief"]["company_name"] = text
            state["step"] = 2
            db.update_brief_step(chat_id, 2)
            m = "✅ Принято!\n\n**Шаг 2 из 7**: Напишите или 🎤 **надиктуйте голосом** вашу **сферу бизнеса и целевую аудиторию**:"
            db.log_chat_message(chat_id, "BOT", m, bot_variant)
            send_telegram_message(chat_id, m)
            return

        elif step == 2:
            state["brief"]["niche"] = text
            state["step"] = 3
            db.update_brief_step(chat_id, 3)
            m = "✅ Отлично!\n\n**Шаг 3 из 7**: Напишите или 🎤 **надиктуйте голосом** **основные товары/услуги и цены**:"
            db.log_chat_message(chat_id, "BOT", m, bot_variant)
            send_telegram_message(chat_id, m)
            return

        elif step == 3:
            state["brief"]["services"] = text
            state["step"] = 4
            db.update_brief_step(chat_id, 4)
            m = "✅ Записал!\n\n**Шаг 4 из 7**: Напишите или 🎤 **надиктуйте голосом** ваше **главное преимущество или УТП**:"
            db.log_chat_message(chat_id, "BOT", m, bot_variant)
            send_telegram_message(chat_id, m)
            return

        elif step == 4:
            state["brief"]["utp"] = text
            state["step"] = 5
            db.update_brief_step(chat_id, 5)
            m = "✅ Отлично!\n\n**Шаг 5 из 7**: Напишите или 🎤 **надиктуйте голосом** пожелания по **стилю и цветам**:"
            db.log_chat_message(chat_id, "BOT", m, bot_variant)
            send_telegram_message(chat_id, m)
            return

        elif step == 5:
            state["brief"]["color_theme"] = text
            state["step"] = 6
            db.update_brief_step(chat_id, 6)
            m = "✅ Принято!\n\n**Шаг 6 из 7**: Напишите или 🎤 **надиктуйте голосом**, какие **блоки нужны на сайте** (Калькулятор, Отзывы, Вопросы):"
            db.log_chat_message(chat_id, "BOT", m, bot_variant)
            send_telegram_message(chat_id, m)
            return

        elif step == 6:
            state["brief"]["blocks"] = text
            state["step"] = 7
            db.update_brief_step(chat_id, 7)
            m = "✅ Запомнил!\n\n**Шаг 7 из 7**: Напишите или 🎤 **надиктуйте голосом** **номер телефона / WhatsApp** на сайте:"
            db.log_chat_message(chat_id, "BOT", m, bot_variant)
            send_telegram_message(chat_id, m)
            return

        elif step == 7:
            state["brief"]["phone"] = text
            state["step"] = None
            brief_data = state["brief"]
            db.update_lead_brief(chat_id, brief_data)

            summary = (
                "🎉 **Бриф успешно сформирован!**\n\n"
                f"🏢 Компания: {brief_data['company_name']}\n"
                f"🎯 Ниша: {brief_data['niche']}\n"
                f"🛠 Услуги: {brief_data['services']}\n"
                f"⭐ УТП: {brief_data['utp']}\n"
                f"🎨 Цвета: {brief_data['color_theme']}\n"
                f"📞 Телефон: {brief_data['phone']}\n\n"
                "💰 **Стоимость разработки**: 9 900 руб.\n"
                "Оплата принимается официально. Нажмите кнопку ниже для подтверждения заказа."
            )
            kbd = {"inline_keyboard": [[{"text": "💳 Симулировать Оплату (9 900 руб.)", "callback_data": "pay_order"}]]}
            db.log_chat_message(chat_id, "BOT", summary, bot_variant)
            send_telegram_message(chat_id, summary, reply_markup=kbd)
            return

        # General Conversational Q&A via Gemini REST API using specific A/B Persona
        persona_prompt = PERSONA_PROMPTS.get(bot_variant, PERSONA_PROMPTS["Variant A (Консультант)"])
        prompt = f"{persona_prompt}\n\nВопрос клиента: '{text}'"
        ai_ans, err_details = safe_generate_ai(prompt, chat_id)

        if ai_ans:
            db.log_chat_message(chat_id, "BOT", ai_ans, bot_variant)
            send_telegram_message(chat_id, ai_ans)
        else:
            if err_details:
                debug_msg = f"⚠️ **Отладка Gemini API**: Ошибка при вызове ИИ:\n`{err_details}`"
                send_telegram_message(chat_id, debug_msg)

            fallback = (
                f"Спасибо за вопрос! Как эксперт по сайтам, скажу: мы создаем продающие лендинги под ключ за 24 часа "
                f"за 9 900 руб. Хотите запустить расчет проекта? Заполните бриф по кнопке ниже!"
            )
            kbd = {"inline_keyboard": [[{"text": "📝 Заполнить бриф на сайт", "callback_data": "start_brief"}]]}
            db.log_chat_message(chat_id, "BOT", fallback, bot_variant)
            send_telegram_message(chat_id, fallback, reply_markup=kbd)
