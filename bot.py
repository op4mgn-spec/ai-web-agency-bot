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
        f"Мы создаем современные сайты и лендинги под ключ для бизнеса всего за 1 день.\n\n"
        f"💡 Чем я могу помочь?\n"
        f"• Ответить на любые вопросы по разработке\n"
        f"• Заполнить короткий бриф на сайт\n"
        f"• Запустить генерацию сайта\n\n"
    )
    if is_admin:
        welcome_text += "👑 **Вы авторизованы как АДМИНИСТРАТОР студии.** Все уведомления о заказах будут приходить сюда!"
    
    keyboard = [
        [InlineKeyboardButton("📋 Заполнить бриф на сайт", callback_data="start_brief")],
        [InlineKeyboardButton("❓ Задать вопрос ИИ", callback_data="ask_question")],
        [InlineKeyboardButton("📞 Контакты студии", callback_data="contact_info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "start_brief":
        context.user_data["brief_step"] = "company_name"
        context.user_data["brief"] = {}
        await query.message.reply_text(
            "🚀 Отлично! Давайте заполним бриф за 4 простых шага.\n\n"
            "**Шаг 1 из 4**: Напишите **название вашей компании или проекта**:"
        )
    elif query.data == "ask_question":
        context.user_data["brief_step"] = None
        await query.message.reply_text("Задайте любой вопрос по созданию сайта, и наш ИИ ответит на него!")
    elif query.data == "contact_info":
        await query.message.reply_text("📞 Связь с основателем: @bers1q\nОфициальная студия: AI Web Studio")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    
    step = context.user_data.get("brief_step")
    
    # Briefing Flow
    if step == "company_name":
        context.user_data["brief"]["company_name"] = text
        context.user_data["brief_step"] = "niche"
        await update.message.reply_text("✅ Принято!\n\n**Шаг 2 из 4**: Какая у вас **сфера деятельности/ниша**? (например: Автосервис, Юрист, Ремонт квартир):")
        return
        
    elif step == "niche":
        context.user_data["brief"]["niche"] = text
        context.user_data["brief_step"] = "services"
        await update.message.reply_text("✅ Отлично!\n\n**Шаг 3 из 4**: Перечислите **основные услуги и цены** (в свободной форме):")
        return
        
    elif step == "services":
        context.user_data["brief"]["services"] = text
        context.user_data["brief_step"] = "phone"
        await update.message.reply_text("✅ Записал!\n\n**Шаг 4 из 4**: Укажите **номер телефона** для связи на сайте:")
        return

    elif step == "phone":
        context.user_data["brief"]["phone"] = text
        context.user_data["brief_step"] = None
        
        brief_data = context.user_data["brief"]
        db.update_lead_brief(user.id, brief_data)
        db.update_lead_status(user.id, "PAID")
        
        summary = (
            "🎉 **Бриф успешно заполнен!**\n\n"
            f"🏢 Компания: {brief_data['company_name']}\n"
            f"🎯 Ниша: {brief_data['niche']}\n"
            f"🛠 Услуги: {brief_data['services']}\n"
            f"📞 Телефон: {brief_data['phone']}\n\n"
            "⚡️ Наш ИИ-генератор уже приступил к сборке вашего сайта! Готовая ссылка прилетит в течение 1 минуты."
        )
        await update.message.reply_text(summary, parse_mode="Markdown")

        # Automatically generate landing page!
        try:
            site_id = f"lead_{user.id}"
            html_path = generate_website_html(brief_data, site_id)
            site_url = f"http://localhost:8000/generated_sites/{site_id}.html"
            db.save_generated_site(user.id, site_url, html_path)
            
            await update.message.reply_text(
                f"✅ **Ваш сайт успешно создан!**\n\n"
                f"🌐 Ссылка на локальный просмотр: {site_url}\n"
                f"📁 Файл на диске: `{html_path}`\n\n"
                f"Если хотите поправить текст, цвета или фото — просто напишите правки прямо сюда!"
            )
        except Exception as e:
            logging.error(f"Error generating site: {e}")

        # Send alert to Admin (@bers1q)
        if ADMIN_TELEGRAM_ID:
            try:
                admin_alert = (
                    f"💰 **НОВЫЙ ЗАКАЗ И БРИФ!**\n\n"
                    f"👤 Клиент: {user.full_name} (@{user.username})\n"
                    f"🏢 Компания: {brief_data['company_name']}\n"
                    f"🎯 Ниша: {brief_data['niche']}\n"
                    f"📞 Телефон: {brief_data['phone']}\n"
                    f"🌐 Файл сайта: `{site_id}.html`"
                )
                await context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=admin_alert, parse_mode="Markdown")
            except Exception as admin_err:
                logging.error(f"Admin notify error: {admin_err}")
        return

    # Regular AI Dialog using Gemini
    if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            prompt = (
                "Ты — профессиональный ИИ-консультант веб-студии AI Web Studio. "
                "Твоя цель — вежливо отвечать на вопросы клиента, вызывать доверие и предлагать заполнить бриф на сайт. "
                f"Сообщение клиента: '{text}'"
            )
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            await update.message.reply_text(response.text)
            return
        except Exception as e:
            logging.error(f"Gemini chat error: {e}")

    await update.message.reply_text("Спасибо за сообщение! Чтобы начать заполнение брифа на сайт, нажмите кнопку /start.")

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
        print(f"Using proxy: {PROXY_URL}")

    req = HTTPXRequest(**request_kwargs)
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).request(req).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    print("Telegram Sales Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
