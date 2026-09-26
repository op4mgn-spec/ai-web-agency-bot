import os
import json
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.request import HTTPXRequest
from google import genai
from dotenv import load_dotenv, set_key
import db
from generator import generate_website_html

load_dotenv()

ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PROXY_URL = os.getenv("PROXY_URL")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

db.init_db()

SYSTEM_SALES_PROMPT = """
Ты — старший менеджер по продажам веб-студии AI Web Studio. Твоя задача — консультировать потенциальных клиентов, снятие всех их сомнений и возражений, и помощь в оформлении заказа.

Правила общения:
1. Будь вежливым, профессиональным и убедительным.
2. Цены: Лендинг "Быстрый старт" — 9 900 руб. Лендинг "Премиум" — 19 900 руб.
3. Сроки: 24 часа (благодаря ИИ-автоматизации первичной верстки и копирайтинга).
4. Гарантии: Официальная оплата, безналичный расчет, бесплатные правки до полного утверждения.
5. Работа с ИИ: Объясняй, что ИИ генерирует базовую структуру и продающий текст, а финальную проверку и доработку всегда делает человек (арт-директор).
6. Не перебивай диалог предложением заполнить бриф, если клиент задал конкретный вопрос. Сначала полностью ответь на его вопрос, а затем органично предложи сделать следующий шаг.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lead = db.get_or_create_lead(user.id, user.username, user.full_name)
    
    # Auto-detect Admin by username bers1q
    global ADMIN_TELEGRAM_ID
    if user.username and user.username.lower() == "bers1q":
        ADMIN_TELEGRAM_ID = str(user.id)
        try:
            set_key(ENV_FILE, "ADMIN_TELEGRAM_ID", str(user.id))
        except Exception:
            pass

    is_admin = (str(user.id) == str(ADMIN_TELEGRAM_ID)) or (user.username and user.username.lower() == "bers1q")

    welcome_text = (
        f"👋 Здравствуйте, {user.first_name}!\n\n"
        f"Я — ИИ-консультант **AI Web Studio**.\n"
        f"Мы создаем профессиональные продающие сайты для бизнеса под ключ за 24 часа.\n\n"
        f"💬 Напишите мне любой вопрос в чат (про цены, сроки, гарантии, примеры) или нажмите кнопку ниже для оформления заказа!"
    )
    if is_admin:
        welcome_text += "\n\n👑 **Режим АДМИНИСТРАТОРА активен.** Вы получаете все уведомления о новых заказах и утверждаете сайты перед отправкой клиентам."
    
    keyboard = [
        [InlineKeyboardButton("📝 Заполнить подробный бриф", callback_data="start_brief")],
        [InlineKeyboardButton("❓ Задать вопрос менеджеру", callback_data="ask_question")],
        [InlineKeyboardButton("📞 Контакты основателя", callback_data="contact_info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data

    if data == "start_brief":
        context.user_data["brief_step"] = 1
        context.user_data["brief"] = {}
        await query.message.reply_text(
            "📋 **Разработка сайта — Шаг 1 из 7**\n\n"
            "Напишите **официальное название вашей компании** или название проекта:"
        )
    elif data == "ask_question":
        context.user_data["brief_step"] = None
        await query.message.reply_text("Задайте любой интересующий вас вопрос по разработке сайта, стоимости или гарантиям!")
    elif data == "contact_info":
        await query.message.reply_text("📞 Связь с основателем студии: @bers1q\nОфициальный сайт: AI Web Studio")
    
    # Admin Controls
    elif data.startswith("admin_generate_"):
        target_client_id = int(data.split("_")[2])
        lead = db.get_lead(target_client_id)
        if not lead:
            await query.message.reply_text("❌ Заказ не найден в базе.")
            return

        brief_data = json.loads(lead.get("brief_data", "{}"))
        await query.message.reply_text(f"⏳ Начинаю ИИ-генерацию сайта для {brief_data.get('company_name', 'Клиента')}...")
        
        try:
            site_id = f"lead_{target_client_id}"
            html_path = generate_website_html(brief_data, site_id)
            site_url = f"http://localhost:8000/generated_sites/{site_id}.html"
            db.save_generated_site(target_client_id, site_url, html_path)

            admin_review_text = (
                f"✅ **САЙТ УСПЕШНО СГЕНЕРИРОВАН!**\n\n"
                f"👤 Клиент: {lead['full_name']} (@{lead['username']})\n"
                f"🏢 Компания: {brief_data.get('company_name')}\n\n"
                f"📄 **Просмотр верстки (на диске):**\n`{html_path}`\n\n"
                f"Утверждаете вариант для отправки клиенту?"
            )
            admin_kbd = [
                [InlineKeyboardButton("🚀 Утвердить и отправить клиенту", callback_data=f"admin_approve_{target_client_id}")],
                [InlineKeyboardButton("🔄 Перегенерировать", callback_data=f"admin_generate_{target_client_id}")]
            ]
            await query.message.reply_text(admin_review_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(admin_kbd))
        except Exception as e:
            await query.message.reply_text(f"❌ Ошибка генерации сайта: {e}")

    elif data.startswith("admin_approve_"):
        target_client_id = int(data.split("_")[2])
        lead = db.get_lead(target_client_id)
        brief_data = json.loads(lead.get("brief_data", "{}"))
        
        db.update_lead_status(target_client_id, "DELIVERED")
        
        # Deliver to client!
        try:
            client_msg = (
                f"🎉 **Ваш сайт успешно создан и утвержден арт-директором!**\n\n"
                f"🏢 Проект: {brief_data.get('company_name')}\n"
                f"📄 Файл верстки подготовлен к выгрузке.\n\n"
                f"Если вы хотите внести какие-либо правки в текст или структуру — просто напишите ваши пожелания прямо сюда в чат!"
            )
            await context.bot.send_message(chat_id=target_client_id, text=client_msg, parse_mode="Markdown")
            await query.message.reply_text(f"✅ Готово! Сайт успешно отправлен клиенту (@{lead['username']}).")
        except Exception as e:
            await query.message.reply_text(f"❌ Ошибка отправки клиенту: {e}")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    
    step = context.user_data.get("brief_step")
    
    # 7-Step Comprehensive Briefing Flow
    if step == 1:
        context.user_data["brief"]["company_name"] = text
        context.user_data["brief_step"] = 2
        await update.message.reply_text("✅ Принято!\n\n**Шаг 2 из 7**: Укажите вашу **сферу бизнеса и целевую аудиторию** (кто ваши клиенты?):")
        return
        
    elif step == 2:
        context.user_data["brief"]["niche"] = text
        context.user_data["brief_step"] = 3
        await update.message.reply_text("✅ Отлично!\n\n**Шаг 3 из 7**: Перечислите **основные товары/услуги и их цены**:")
        return

    elif step == 3:
        context.user_data["brief"]["services"] = text
        context.user_data["brief_step"] = 4
        await update.message.reply_text("✅ Записал!\n\n**Шаг 4 из 7**: Ваше **главное преимущество или УТП** (почему клиенты должны выбрать вас?):")
        return

    elif step == 4:
        context.user_data["brief"]["utp"] = text
        context.user_data["brief_step"] = 5
        await update.message.reply_text("✅ Отлично!\n\n**Шаг 5 из 7**: Пожелания по **стилю и цветовой гамме** (например: синий/строгий, яркий/современный):")
        return

    elif step == 5:
        context.user_data["brief"]["color_theme"] = text
        context.user_data["brief_step"] = 6
        await update.message.reply_text("✅ Принято!\n\n**Шаг 6 из 7**: Какие **блоки нужны на сайте**? (например: Калькулятор, Отзывы, Галерея работ, Вопросы-ответы):")
        return

    elif step == 6:
        context.user_data["brief"]["blocks"] = text
        context.user_data["brief_step"] = 7
        await update.message.reply_text("✅ Запомнил!\n\n**Шаг 7 из 7**: Укажите **номер телефона / WhatsApp** для клиентов на сайте:")
        return

    elif step == 7:
        context.user_data["brief"]["phone"] = text
        context.user_data["brief_step"] = None
        
        brief_data = context.user_data["brief"]
        db.update_lead_brief(user.id, brief_data)
        db.update_lead_status(user.id, "WAITING_PAYMENT")
        
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
        
        kbd = [[InlineKeyboardButton("💳 Симулировать Оплату (9 900 руб.)", callback_data=f"pay_order")]]
        await update.message.reply_text(summary, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kbd))
        return

    # Handle Payment Simulation / Confirmation
    if text == "/pay" or context.user_data.get("awaiting_payment"):
        db.update_lead_status(user.id, "PAID")
        await update.message.reply_text(
            "✅ **Оплата принята!**\n\n"
            "Ваш заказ передан основателю студии (@bers1q). После проверки брифа и запуска генерации ваш сайт будет передан вам на утверждение!"
        )
        
        # ALERT ADMIN @bers1q (NO AUTO GENERATION)
        if ADMIN_TELEGRAM_ID:
            brief_data = json.loads(db.get_lead(user.id).get("brief_data", "{}"))
            admin_alert = (
                f"💰 **НОВАЯ ОПЛАТА ЗАКАЗА (9 900 руб)!**\n\n"
                f"👤 Заказчик: {user.full_name} (@{user.username})\n"
                f"🏢 Компания: {brief_data.get('company_name')}\n"
                f"🎯 Ниша: {brief_data.get('niche')}\n"
                f"📞 Телефон: {brief_data.get('phone')}\n\n"
                f"Запустить генерацию и проверку верстки?"
            )
            admin_kbd = [
                [InlineKeyboardButton("🔨 Сгенерировать сайт", callback_data=f"admin_generate_{user.id}")]
            ]
            try:
                await context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=admin_alert, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(admin_kbd))
            except Exception as admin_err:
                logging.error(f"Admin alert error: {admin_err}")
        return

    # Advanced AI Sales Conversation & Objection Handling via Gemini
    if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            full_prompt = f"{SYSTEM_SALES_PROMPT}\n\nКлиент пишет: '{text}'"
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=full_prompt
            )
            await update.message.reply_text(response.text)
            return
        except Exception as e:
            logging.error(f"Gemini sales chat error: {e}")

    await update.message.reply_text("Спасибо за сообщение! Если вы хотите оформить заказ на сайт, нажмите /start.")

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is missing!")
        return

    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    request_kwargs = {
        "connect_timeout": 30.0,
        "read_timeout": 30.0
    }
    if PROXY_URL:
        request_kwargs["proxy"] = PROXY_URL

    req = HTTPXRequest(**request_kwargs)
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).request(req).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    print("Telegram Sales Bot starting with Admin Verification Flow...")
    app.run_polling()

if __name__ == "__main__":
    main()
