import os
import json
import logging
import asyncio
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.request import HTTPXRequest
from google import genai
from dotenv import load_dotenv, set_key
import db
import server
from generator import generate_website_html

load_dotenv()

ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")

OWNER_BOT_TOKEN = os.getenv("OWNER_BOT_TOKEN") or "8690113233:AAGLX7LTETCuxgfc79T_av0VKEikBBDTJtY"
CLIENT_BOT_TOKEN = os.getenv("CLIENT_BOT_TOKEN") or "8740453272:AAG5MyW2cvsiPaRT3i3V4feM7bRKoGhyFbU"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or OWNER_BOT_TOKEN
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PROXY_URL = os.getenv("PROXY_URL")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

db.init_db()

# A/B Testing System Prompts for Bot Personas
PERSONA_PROMPTS = {
    "Variant A (Консультант)": """
Ты — вежливый эксперт-консультант веб-студии AI Web Studio. 
Твоя цель — глубоко понимать проблему клиента, давать полезные советы по росту продаж бизнеса и отвечать на любые вопросы про сайты. 
Лендинг стоит 9 900 руб., 24 часа. Сначала полностью отвечай на вопросы клиента, а потом предлагай заполнить бриф.
""",
    "Variant B (Прямые Продажи)": """
Ты — энергичный директор по продажам AI Web Studio. 
Твоя цель — факты, приведение кейсов, ответы на все возражения и закрытие сделки. 
Стоимость — 9 900 руб., 24 часа. Будь убедителен, давай сильные офферы и предлагай сделать первый шаг прямо сейчас.
"""
}

async def safe_generate_ai_response(prompt: str) -> str:
    """Generates text via Gemini API with automatic model fallback."""
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        return ""
        
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        for model_name in ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                logging.warning(f"Model {model_name} failed: {e}")
                continue
    except Exception as global_err:
        logging.error(f"GenAI Client error: {global_err}")
            
    return ""

async def reply_and_log(update: Update, text: str, user_id: int, bot_variant: str = "", reply_markup=None, parse_mode=None):
    try:
        db.log_chat_message(user_id, "BOT", text, bot_variant)
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        logging.error(f"Error in reply_and_log: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lead = db.get_or_create_lead(user.id, user.username, user.full_name)
    bot_variant = lead.get("bot_variant", "Variant A (Консультант)")

    # Log incoming user message
    db.log_chat_message(user.id, "USER", "/start", bot_variant)
    
    # Auto-bind Admin for owner interactions
    global ADMIN_TELEGRAM_ID
    ADMIN_TELEGRAM_ID = str(user.id)
    db.set_setting("ADMIN_TELEGRAM_ID", str(user.id))
    try:
        set_key(ENV_FILE, "ADMIN_TELEGRAM_ID", str(user.id))
    except Exception:
        pass

    is_admin = True

    welcome_text = (
        f"👋 Здравствуйте, {user.first_name}!\n\n"
        f"Я — ИИ-консультант **AI Web Studio**.\n"
        f"Мы создаем профессиональные продающие сайты для бизнеса под ключ за 24 часа.\n\n"
        f"💬 Задайте мне любой вопрос текстом или 🎤 **надиктуйте голосом**! Я с радостью отвечу и помогу составить бриф."
    )
    welcome_text += "\n\n👑 **Режим СОБСТВЕННИКА активен.** Вы получаете все уведомления о новых заказах, видите CRM и утверждаете сайты ИИ-Совета Директоров."
    
    keyboard = [
        [InlineKeyboardButton("👑 Дашборд Собственника", url="https://ai-web-agency-bot.onrender.com/owner")],
        [InlineKeyboardButton("📊 CRM Воронка Лидов", url="https://ai-web-agency-bot.onrender.com/crm")],
        [InlineKeyboardButton("📝 Заполнить бриф (текст или 🎤 голос)", callback_data="start_brief")],
        [InlineKeyboardButton("❓ Задать вопрос менеджеру", callback_data="ask_question")],
        [InlineKeyboardButton("📞 Контакты основателя", callback_data="contact_info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await reply_and_log(update, welcome_text, user.id, bot_variant, reply_markup=reply_markup, parse_mode="Markdown")

    import executive_ai_engine
    executive_ai_engine.resend_pending_approvals_to_owner(user.id)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    lead = db.get_or_create_lead(user.id, user.username, user.full_name)
    bot_variant = lead.get("bot_variant", "Variant A (Консультант)")
    
    await query.answer()
    data = query.data

    if data == "start_brief":
        context.user_data["brief_step"] = 1
        context.user_data["brief"] = {}
        db.update_brief_step(user.id, 1)
        
        msg = "📋 **Разработка сайта — Шаг 1 из 7**\n\nНапишите или 🎤 **надиктуйте голосом** официальное название вашей компании или название проекта:"
        db.log_chat_message(user.id, "BOT", msg, bot_variant)
        await query.message.reply_text(msg, parse_mode="Markdown")

    elif data == "ask_question":
        context.user_data["brief_step"] = None
        msg = "💬 Задайте любой интересующий вас вопрос текстом или 🎤 **надиктуйте голосом**!"
        db.log_chat_message(user.id, "BOT", msg, bot_variant)
        await query.message.reply_text(msg)

    elif data.startswith("approve_init_") or data.startswith("reject_init_"):
        import executive_ai_engine
        executive_ai_engine.handle_owner_approval_callback(data, user.id)
        return

    elif data == "contact_info":
        msg = "📞 **Связь со службой поддержки AI Web Studio**\n\nЗадайте любой вопрос прямо сюда в чат!"
        db.log_chat_message(user.id, "BOT", msg, bot_variant)
        await query.message.reply_text(msg)
    
    # Admin Controls
    elif data.startswith("admin_generate_"):
        target_client_id = int(data.split("_")[2])
        lead_row = db.get_all_leads_crm()
        target = next((l for l in lead_row if l['telegram_id'] == target_client_id), None)
        
        if not target:
            await query.message.reply_text("❌ Заказ не найден в базе.")
            return

        brief_data = json.loads(target.get("brief_data", "{}"))
        await query.message.reply_text(f"⏳ Начинаю ИИ-генерацию сайта для {brief_data.get('company_name', 'Клиента')}...")
        
        try:
            site_id = f"lead_{target_client_id}"
            html_path = generate_website_html(brief_data, site_id)
            site_url = f"http://localhost:8000/generated_sites/{site_id}.html"
            db.save_generated_site(target_client_id, site_url, html_path)

            admin_review_text = (
                f"✅ **САЙТ УСПЕШНО СГЕНЕРИРОВАН!**\n\n"
                f"👤 Клиент: {target['full_name']} (@{target['username']})\n"
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
        lead_row = db.get_all_leads_crm()
        target = next((l for l in lead_row if l['telegram_id'] == target_client_id), None)
        brief_data = json.loads(target.get("brief_data", "{}"))
        
        db.update_lead_status(target_client_id, "DELIVERED")
        
        try:
            client_msg = (
                f"🎉 **Ваш сайт успешно создан и утвержден арт-директором!**\n\n"
                f"🏢 Проект: {brief_data.get('company_name')}\n"
                f"📄 Файл верстки подготовлен к выгрузке.\n\n"
                f"Если вы хотите внести какие-либо правки в текст или структуру — просто напишите ваши пожелания прямо сюда в чат!"
            )
            db.log_chat_message(target_client_id, "BOT", client_msg, bot_variant)
            await context.bot.send_message(chat_id=target_client_id, text=client_msg, parse_mode="Markdown")
            await query.message.reply_text(f"✅ Готово! Сайт успешно отправлен клиенту (@{target['username']}).")
        except Exception as e:
            await query.message.reply_text(f"❌ Ошибка отправки клиенту: {e}")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    
    lead = db.get_or_create_lead(user.id, user.username, user.full_name)
    bot_variant = lead.get("bot_variant", "Variant A (Консультант)")
    
    # Log incoming user message to CRM
    db.log_chat_message(user.id, "USER", text, bot_variant)

    step = context.user_data.get("brief_step")
    
    # 7-Step Comprehensive Briefing Flow
    if step == 1:
        context.user_data["brief"]["company_name"] = text
        context.user_data["brief_step"] = 2
        db.update_brief_step(user.id, 2)
        await reply_and_log(update, "✅ Принято!\n\n**Шаг 2 из 7**: Напишите или 🎤 **надиктуйте голосом** вашу **сферу бизнеса и целевую аудиторию** (кто ваши клиенты?):", user.id, bot_variant, parse_mode="Markdown")
        return
        
    elif step == 2:
        context.user_data["brief"]["niche"] = text
        context.user_data["brief_step"] = 3
        db.update_brief_step(user.id, 3)
        await reply_and_log(update, "✅ Отлично!\n\n**Шаг 3 из 7**: Напишите или 🎤 **надиктуйте голосом** **основные товары/услуги и их цены**:", user.id, bot_variant, parse_mode="Markdown")
        return

    elif step == 3:
        context.user_data["brief"]["services"] = text
        context.user_data["brief_step"] = 4
        db.update_brief_step(user.id, 4)
        await reply_and_log(update, "✅ Записал!\n\n**Шаг 4 из 7**: Напишите или 🎤 **надиктуйте голосом** ваше **главное преимущество или УТП** (почему клиенты должны выбрать вас?):", user.id, bot_variant, parse_mode="Markdown")
        return

    elif step == 4:
        context.user_data["brief"]["utp"] = text
        context.user_data["brief_step"] = 5
        db.update_brief_step(user.id, 5)
        await reply_and_log(update, "✅ Отлично!\n\n**Шаг 5 из 7**: Напишите или 🎤 **надиктуйте голосом** пожелания по **стилю и цветовой гамме** (например: синий/строгий, яркий/современный):", user.id, bot_variant, parse_mode="Markdown")
        return

    elif step == 5:
        context.user_data["brief"]["color_theme"] = text
        context.user_data["brief_step"] = 6
        db.update_brief_step(user.id, 6)
        await reply_and_log(update, "✅ Принято!\n\n**Шаг 6 из 7**: Напишите или 🎤 **надиктуйте голосом**, какие **блоки нужны на сайте**? (например: Калькулятор, Отзывы, Галерея работ, Вопросы-ответы):", user.id, bot_variant, parse_mode="Markdown")
        return

    elif step == 6:
        context.user_data["brief"]["blocks"] = text
        context.user_data["brief_step"] = 7
        db.update_brief_step(user.id, 7)
        await reply_and_log(update, "✅ Запомнил!\n\n**Шаг 7 из 7**: Напишите или 🎤 **надиктуйте голосом** **номер телефона / WhatsApp** для клиентов на сайте:", user.id, bot_variant, parse_mode="Markdown")
        return

    elif step == 7:
        context.user_data["brief"]["phone"] = text
        context.user_data["brief_step"] = None
        
        brief_data = context.user_data["brief"]
        db.update_lead_brief(user.id, brief_data)
        
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
        
        kbd = [[InlineKeyboardButton("💳 Симулировать Оплату (9 900 руб.)", callback_data="pay_order")]]
        await reply_and_log(update, summary, user.id, bot_variant, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
        return

    # Advanced Conversational AI Dialog via Gemini
    system_prompt = PERSONA_PROMPTS.get(bot_variant, PERSONA_PROMPTS["Variant A (Консультант)"])
    full_prompt = f"{system_prompt}\n\nИстория вопроса клиента: '{text}'"
    
    ai_reply = await safe_generate_ai_response(full_prompt)
    if ai_reply:
        await reply_and_log(update, ai_reply, user.id, bot_variant)
        return

    # Fallback response if AI is processing or offline
    fallback_reply = (
        f"Спасибо за вопрос! Как эксперт по сайтам ({bot_variant}), скажу: "
        f"мы создаем профессиональные лендинги под ключ за 24 часа за 9 900 руб. "
        f"Хотите рассчитать проект и заполнить бриф? Нажмите кнопку ниже!"
    )
    kbd = [[InlineKeyboardButton("📝 Заполнить бриф на сайт", callback_data="start_brief")]]
    await reply_and_log(update, fallback_reply, user.id, bot_variant, reply_markup=InlineKeyboardMarkup(kbd))

async def claim_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.set_setting("ADMIN_TELEGRAM_ID", str(user.id))
    msg = (
        f"👑 **ПРАВА СОБСТВЕННИКА УСПЕШНО АКТИВИРОВАНЫ!**\n\n"
        f"• Ваш Telegram ID: `{user.id}`\n"
        f"• Вы получаете все уведомления о заказах и карточки утверждения задач Совета Директоров."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
    import executive_ai_engine
    executive_ai_engine.resend_pending_approvals_to_owner(user.id)

async def owner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.set_setting("ADMIN_TELEGRAM_ID", str(user.id))
    owner_url = "https://ai-web-agency-bot.onrender.com/owner"
    msg = (
        f"👑 **Дашборд Собственника (Executive Command Center)**\n\n"
        f"📊 P&L отчетность (Выручка, Прибыль, Маржа >90%), план по отделам (РОП, CPO, CFO, COO) и кнопка генерации гипотез."
    )
    kbd = [[InlineKeyboardButton("👑 Открыть Дашборд Собственника", url=owner_url)]]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

async def crm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.set_setting("ADMIN_TELEGRAM_ID", str(user.id))
    crm_url = "https://ai-web-agency-bot.onrender.com/crm"
    msg = "⚡️ **Панель управления AI Web Agency CRM**\n\n📊 Отслеживание лидов, этапов брифов и истории диалогов."
    kbd = [[InlineKeyboardButton("📱 Открыть CRM", url=crm_url)]]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

async def hypothesis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.set_setting("ADMIN_TELEGRAM_ID", str(user.id))

    import executive_ai_engine
    args = context.args
    dept_arg = args[0].upper() if args else ""
    
    if dept_arg in ["SALES", "PRODUCT", "FINANCE", "FULFILLMENT"]:
        await update.message.reply_text(f"🧠 **ИИ-Совет Директоров**: Генерация гипотезы для отдела `{dept_arg}`...")
        executive_ai_engine.generate_and_submit_new_hypothesis(dept_arg)
    else:
        await update.message.reply_text("🧠 **ИИ-Совет Директоров**: Запуск авто-генерации гипотез для ВСЕХ 4 отделов (РОП, CPO, CFO, COO)...")
        for d in ["SALES", "PRODUCT", "FINANCE", "FULFILLMENT"]:
            executive_ai_engine.generate_and_submit_new_hypothesis(d)
        executive_ai_engine.resend_pending_approvals_to_owner(user.id)

async def async_main():
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is missing!")
        return

    request_kwargs = {
        "connect_timeout": 30.0,
        "read_timeout": 30.0
    }
    if PROXY_URL:
        request_kwargs["proxy"] = PROXY_URL

    req = HTTPXRequest(**request_kwargs)
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).request(req).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("claim", claim_command))
    app.add_handler(CommandHandler("setadmin", claim_command))
    app.add_handler(CommandHandler("owner", owner_command))
    app.add_handler(CommandHandler("crm", crm_command))
    app.add_handler(CommandHandler("hypothesis", hypothesis_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    server.telegram_app = app

    print(f"Starting Telegram Sales Bot context manager with token {TELEGRAM_BOT_TOKEN[:10]}...")
    async with app:
        await app.bot.delete_webhook(drop_pending_updates=True)
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        print("✅ Telegram Sales Bot polling engine ACTIVE and listening to updates!")
        await asyncio.Event().wait()

def main():
    try:
        asyncio.run(async_main())
    except Exception as e:
        print(f"Bot main loop error: {e}")

if __name__ == "__main__":
    main()
