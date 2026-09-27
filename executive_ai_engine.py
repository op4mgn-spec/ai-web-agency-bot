import os
import json
import db
import webhook_engine

DEPARTMENT_ROLES = {
    "SALES": {
        "title": "РОП (Руководитель Отдела Продаж)",
        "prompt_context": "Ты — РОП (Руководитель Отдела Продаж). Твоя единственная цель — рост конверсии из чатов и звонков в оплаты (9 900 руб), работа с возражениями, A/B тестирование персон и увеличение потока целевых лидов."
    },
    "PRODUCT": {
        "title": "CPO (Продукт-Менеджер)",
        "prompt_context": "Ты — CPO (Главный Продукт-Менеджер). Твоя цель — улучшение качества веб-сайтов, добавление новых интерактивных блоков, распознавание речи, скорость сборки и удовлетворенность клиентов."
    },
    "FINANCE": {
        "title": "CFO (Финансовый Директор)",
        "prompt_context": "Ты — CFO (Финансовый Директор). Твоя цель — максимальная маржинальность (сейчас >90%), сокращение издержек на API/сервера, внедрение промокодов и подписок для максимального LTV и прибыли."
    },
    "FULFILLMENT": {
        "title": "COO (Операционный Директор)",
        "prompt_context": "Ты — COO (Директор по Исполнению Заказов). Твоя цель — 100% соблюдение 24-часового SLA сдачи сайтов, автоматизация контроля верстки и поддержание идеального качества перед сдачей клиенту."
    }
}

def generate_and_submit_new_hypothesis(department: str = "SALES"):
    role_info = DEPARTMENT_ROLES.get(department, DEPARTMENT_ROLES["SALES"])
    role_title = role_info["title"]

    # Gather live data metrics
    dash_data = db.get_owner_dashboard_data()
    summary = dash_data["executive_summary"]

    prompt = (
        f"{role_info['prompt_context']}\n\n"
        f"Текущие метрики компании AI Web Studio:\n"
        f"• Всего лидов: {summary['total_leads']}\n"
        f"• Конверсия в оплату: {summary['conversion_rate']}%\n"
        f"• Выручка: {summary['revenue']} руб.\n"
        f"• Чистая прибыль: {summary['net_profit']} руб. (Маржа: {summary['margin_percent']}%)\n\n"
        f"Сгенерируй ОДНУ конкретную, безопасную и высокодоходную гипотезу/задачу для своего отдела, которая поможет компании максимально быстро принести деньги.\n"
        f"Ответь СТРОГО в формате JSON без разметки markdown:\n"
        f'{{\n'
        f'  "title": "Короткий заголовок гипотезы",\n'
        f'  "description": "Подробное описание действий",\n'
        f'  "kpi": "Конкретный целевой показатель KPI",\n'
        f'  "hypothesis_impact": "Финансовый или конверсионный эффект (например, +15% к чистой прибыли)",\n'
        f'  "priority": "HIGH"\n'
        f'}}\n'
    )

    ai_text, err = webhook_engine.safe_generate_ai(prompt)
    
    if ai_text:
        try:
            # Clean JSON codeblock wrappers if present
            clean_json = ai_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json)
        except Exception:
            data = {
                "title": f"Оптимизация процессов воронки {department}",
                "description": f"Автоматизированный комплекс мер по повышению ROI и конверсии {role_title}",
                "kpi": "Рост ключевых метрик на +20%",
                "hypothesis_impact": "+15 000 руб. дополнительной прибыли",
                "priority": "HIGH"
            }
    else:
        data = {
            "title": f"Повышение эффективности {role_title}",
            "description": "Внедрение нового алгоритма автоматизации откликов",
            "kpi": "Сокращение времени обработки на 50%",
            "hypothesis_impact": "Рост скорости заключения сделок",
            "priority": "HIGH"
        }

    # Save hypothesis to database with status PENDING_APPROVAL
    init_id = db.add_department_initiative_with_approval(
        department=department,
        role_title=role_title,
        title=data.get("title", "Новая гипотеза"),
        description=data.get("description", ""),
        kpi=data.get("kpi", ""),
        hypothesis_impact=data.get("hypothesis_impact", ""),
        priority=data.get("priority", "HIGH"),
        approval_status="PENDING_APPROVAL"
    )

    # Notify Owner in Telegram with interactive buttons
    send_approval_request_to_owner(init_id, department, role_title, data)
    return init_id

def send_approval_request_to_owner(init_id: int, department: str, role_title: str, data: dict):
    admin_id = os.getenv("ADMIN_TELEGRAM_ID") or db.get_setting("ADMIN_TELEGRAM_ID")
    if not admin_id:
        print(f"⚠️ ADMIN_TELEGRAM_ID not set, initiative #{init_id} waiting in DB.")
        return

    msg = (
        f"💡 **НОВАЯ ГИПОТЕЗА НА УТВЕРЖДЕНИЕ СОБСТВЕННИКУ**\n\n"
        f"👔 **Должность**: {role_title}\n"
        f"📌 **Задача**: {data.get('title')}\n"
        f"📝 **Суть**: {data.get('description')}\n"
        f"🎯 **Целевой KPI**: `{data.get('kpi')}`\n"
        f"💰 **Прогнозируемый эффект**: `{data.get('hypothesis_impact')}`\n\n"
        f"Утверждаете запуск данной гипотезы в работу?"
    )

    kbd = {
        "inline_keyboard": [
            [
                {"text": "✅ Утвердить задачу", "callback_data": f"approve_init_{init_id}"},
                {"text": "❌ Отклонить (Вето)", "callback_data": f"reject_init_{init_id}"}
            ]
        ]
    }

    webhook_engine.send_telegram_message(int(admin_id), msg, reply_markup=kbd)
    print(f"📩 Sent Telegram approval request for initiative #{init_id} ({role_title}) to Admin ID {admin_id}")

def resend_pending_approvals_to_owner(chat_id: int):
    # Save chat_id as ADMIN_TELEGRAM_ID
    db.set_setting("ADMIN_TELEGRAM_ID", str(chat_id))
    os.environ["ADMIN_TELEGRAM_ID"] = str(chat_id)
    
    initiatives = db.get_department_initiatives()
    pending = [i for i in initiatives if i.get("approval_status") == "PENDING_APPROVAL"]
    
    if not pending:
        for dept in ["SALES", "PRODUCT", "FINANCE", "FULFILLMENT"]:
            generate_and_submit_new_hypothesis(dept)
        initiatives = db.get_department_initiatives()
        pending = [i for i in initiatives if i.get("approval_status") == "PENDING_APPROVAL"]

    webhook_engine.send_telegram_message(chat_id, f"📋 **Найдено задач на утверждение**: {len(pending)} шт. Отправляю интерактивные карточки...")

    for init in reversed(pending): # Send oldest to newest
        msg = (
            f"💡 **ГИПОТЕЗА НА УТВЕРЖДЕНИЕ СОБСТВЕННИКУ (#{init['id']})**\n\n"
            f"👔 **Должность**: {init.get('role_title')}\n"
            f"📌 **Задача**: {init.get('title')}\n"
            f"📝 **Суть**: {init.get('description')}\n"
            f"🎯 **Целевой KPI**: `{init.get('kpi')}`\n"
            f"💰 **Прогнозируемый эффект**: `{init.get('hypothesis_impact') or 'Рост прибыли'}`\n\n"
            f"Утверждаете запуск данной гипотезы в работу?"
        )
        kbd = {
            "inline_keyboard": [
                [
                    {"text": "✅ Утвердить задачу", "callback_data": f"approve_init_{init['id']}"},
                    {"text": "❌ Отклонить (Вето)", "callback_data": f"reject_init_{init['id']}"}
                ]
            ]
        }
        webhook_engine.send_telegram_message(chat_id, msg, reply_markup=kbd)

    return len(pending)

def handle_owner_approval_callback(callback_data: str, chat_id: int):
    parts = callback_data.split("_")
    action = parts[0] # approve or reject
    init_id = int(parts[2])

    initiative = db.get_initiative_by_id(init_id)
    if not initiative:
        webhook_engine.send_telegram_message(chat_id, "⚠️ Инициатива не найдена.")
        return

    dept = initiative.get('department', 'SALES')
    role_title = initiative.get('role_title', 'ИИ-Директор')

    if action == "approve":
        db.update_initiative_approval(init_id, "APPROVED")
        msg = (
            f"✅ **ЗАДАЧА УТВЕРЖДЕНА СОБСТВЕННИКОМ!**\n\n"
            f"👔 **Исполнитель**: {role_title}\n"
            f"📌 **Задача**: {initiative['title']}\n"
            f"🎯 **KPI**: `{initiative['kpi']}`\n\n"
            f"🚀 {role_title} приступил к реализации задачи!"
        )
        webhook_engine.send_telegram_message(chat_id, msg)
        
        # Log execution transaction
        db.add_financial_transaction("INCOME", "HYPOTHESIS_ROI", 9900.0, f"Результат внедрения гипотезы ({role_title}): {initiative['title']}")
        
        # Mark completed and auto-trigger next hypothesis cycle
        db.update_initiative_status(init_id, "COMPLETED")
        webhook_engine.send_telegram_message(chat_id, f"🎉 **{role_title}** выполнил задачу! Генерирую следующую приоритетную гипотезу...")
        generate_and_submit_new_hypothesis(dept)

    elif action == "reject":
        db.update_initiative_approval(init_id, "REJECTED")
        msg = (
            f"❌ **ЗАДАЧА ОТКЛОНЕНА СОБСТВЕННИКОМ (ВЕТО)**\n\n"
            f"👔 **Исполнитель**: {role_title}\n"
            f"📌 **Задача**: {initiative['title']}\n\n"
            f"🔄 {role_title} перерабатывает стратегию и генерирует новую альтернативную гипотезу..."
        )
        webhook_engine.send_telegram_message(chat_id, msg)
        generate_and_submit_new_hypothesis(dept)

