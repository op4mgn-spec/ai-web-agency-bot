import os
import json
import logging
import requests
import db
from generator import generate_website_html

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "8740453272:AAG5MyW2cvsiPaRT3i3V4feM7bRKoGhyFbU"
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# User state memory for brief steps
user_states = {}

SYSTEM_SALES_PROMPT = """
Ты — вежливый старший менеджер по продажам веб-студии AI Web Studio. 
Твоя цель — отвечать на вопросы клиента про сайты, цены (9 900 руб), сроки (24 часа) и гарантии. 
Будь кратък, убедителен и вежлив.
"""

def send_telegram_message(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        r = requests.post(f"{API_URL}/sendMessage", json=payload, timeout=5)
        return r.json()
    except Exception as e:
        print(f"Error sending telegram message: {e}")
        return None

def answer_callback_query(callback_query_id):
    try:
        requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": callback_query_id}, timeout=3)
    except Exception:
        pass

def safe_generate_ai(prompt):
    global GEMINI_API_KEY
    key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    if not key or key == "your_gemini_api_key_here":
        print("Gemini API Key is missing or default")
        return ""
        
    for model_name in ['gemini-1.5-flash', 'gemini-2.0-flash-exp', 'gemini-1.5-pro']:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
        headers = {"Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=10)
            data = r.json()
            if "candidates" in data and len(data["candidates"]) > 0:
                parts = data["candidates"][0].get("content", {}).get("parts", [])
                if parts and "text" in parts[0]:
                    return parts[0]["text"].strip()
            elif "error" in data:
                print(f"Gemini API Error ({model_name}): {data['error'].get('message')}")
        except Exception as e:
            print(f"Gemini REST Exception ({model_name}): {e}")
            continue
    return ""

def process_telegram_update(update_data):
    global GEMINI_API_KEY
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

        if data == "start_brief":
            user_states[chat_id] = {"step": 1, "brief": {}}
            db.update_brief_step(chat_id, 1)
            msg = "📋 **Разработка сайта — Шаг 1 из 7**\n\nНапишите **официальное название вашей компании** или проекта:"
            db.log_chat_message(chat_id, "BOT", msg, bot_variant)
            send_telegram_message(chat_id, msg)

        elif data == "ask_question":
            user_states[chat_id] = {"step": None}
            msg = "Задайте любой вопрос по созданию сайта, стоимости или гарантиям!"
            db.log_chat_message(chat_id, "BOT", msg, bot_variant)
            send_telegram_message(chat_id, msg)

        elif data == "contact_info":
            msg = "📞 Связь с основателем: @bers1q\nОфициальная студия: AI Web Studio"
            db.log_chat_message(chat_id, "BOT", msg, bot_variant)
            send_telegram_message(chat_id, msg)

        elif data == "pay_order":
            db.update_lead_status(chat_id, "PAID")
            msg = "✅ **Оплата принята (9 900 руб.)!**\n\nВаш заказ передан основателю студии (@bers1q). После проверки брифа и утверждения верстки ваш сайт будет выслан вам на утверждение!"
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

    # Handle Normal Messages
    if "message" in update_data and "text" in update_data["message"]:
        msg = update_data["message"]
        user = msg["from"]
        chat_id = user["id"]
        text = msg["text"].strip()

        lead = db.get_or_create_lead(chat_id, user.get("username", ""), user.get("first_name", ""))
        bot_variant = lead.get("bot_variant", "Variant A (Консультант)")

        db.log_chat_message(chat_id, "USER", text, bot_variant)

        is_admin = (user.get("username", "").lower() == "bers1q")

        # Admin Command to set Gemini API key directly from Telegram!
        if text.startswith("/setkey ") and is_admin:
            new_key = text.split(" ", 1)[1].strip()
            GEMINI_API_KEY = new_key
            os.environ["GEMINI_API_KEY"] = new_key
            send_telegram_message(chat_id, "🔑 **Gemini API Key успешно обновлен и активирован!**")
            return

        # Handle /start
        if text == "/start":
            user_states[chat_id] = {"step": None, "brief": {}}
            welcome = (
                f"👋 Здравствуйте, {user.get('first_name')}!\n\n"
                f"Я — ИИ-консультант **AI Web Studio**.\n"
                f"Мы создаем продающие сайты под ключ за 24 часа.\n\n"
                f"💬 Задайте мне любой вопрос в чат или нажмите кнопку ниже для заказа!"
            )
            if is_admin:
                welcome += "\n\n👑 **Режим АДМИНИСТРАТОРА активен.** Вы можете установить ключ API командой `/setkey AIzaSy...`."

            kbd = {"inline_keyboard": [
                [{"text": "📝 Заполнить подробный бриф", "callback_data": "start_brief"}],
                [{"text": "❓ Задать вопрос менеджеру", "callback_data": "ask_question"}],
                [{"text": "📞 Контакты основателя", "callback_data": "contact_info"}]
            ]}
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
            m = "✅ Принято!\n\n**Шаг 2 из 7**: Укажите вашу **сферу бизнеса и целевую аудиторию**:"
            db.log_chat_message(chat_id, "BOT", m, bot_variant)
            send_telegram_message(chat_id, m)
            return

        elif step == 2:
            state["brief"]["niche"] = text
            state["step"] = 3
            db.update_brief_step(chat_id, 3)
            m = "✅ Отлично!\n\n**Шаг 3 из 7**: Перечислите **основные товары/услуги и цены**:"
            db.log_chat_message(chat_id, "BOT", m, bot_variant)
            send_telegram_message(chat_id, m)
            return

        elif step == 3:
            state["brief"]["services"] = text
            state["step"] = 4
            db.update_brief_step(chat_id, 4)
            m = "✅ Записал!\n\n**Шаг 4 из 7**: Ваше **главное преимущество или УТП**:"
            db.log_chat_message(chat_id, "BOT", m, bot_variant)
            send_telegram_message(chat_id, m)
            return

        elif step == 4:
            state["brief"]["utp"] = text
            state["step"] = 5
            db.update_brief_step(chat_id, 5)
            m = "✅ Отлично!\n\n**Шаг 5 из 7**: Пожелания по **стилю и цветам**:"
            db.log_chat_message(chat_id, "BOT", m, bot_variant)
            send_telegram_message(chat_id, m)
            return

        elif step == 5:
            state["brief"]["color_theme"] = text
            state["step"] = 6
            db.update_brief_step(chat_id, 6)
            m = "✅ Принято!\n\n**Шаг 6 из 7**: Какие **блоки нужны на сайте** (Калькулятор, Отзывы, Ответа):"
            db.log_chat_message(chat_id, "BOT", m, bot_variant)
            send_telegram_message(chat_id, m)
            return

        elif step == 6:
            state["brief"]["blocks"] = text
            state["step"] = 7
            db.update_brief_step(chat_id, 7)
            m = "✅ Запомнил!\n\n**Шаг 7 из 7**: Укажите **номер телефона / WhatsApp** на сайте:"
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

        # General Conversational Q&A via Gemini REST API
        prompt = f"{SYSTEM_SALES_PROMPT}\nВопрос клиента: '{text}'"
        ai_ans = safe_generate_ai(prompt)

        if ai_ans:
            db.log_chat_message(chat_id, "BOT", ai_ans, bot_variant)
            send_telegram_message(chat_id, ai_ans)
        else:
            fallback = (
                f"Спасибо за вопрос! Как эксперт по сайтам, скажу: мы создаем продающие лендинги под ключ за 24 часа "
                f"за 9 900 руб. Хотите запустить расчет проекта? Заполните бриф по кнопке ниже!"
            )
            kbd = {"inline_keyboard": [[{"text": "📝 Заполнить бриф на сайт", "callback_data": "start_brief"}]]}
            db.log_chat_message(chat_id, "BOT", fallback, bot_variant)
            send_telegram_message(chat_id, fallback, reply_markup=kbd)
