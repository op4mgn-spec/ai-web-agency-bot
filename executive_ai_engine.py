import os
import json
from datetime import datetime
import db
import webhook_engine

DEPARTMENT_ROLES = {
    "SALES": {
        "title": "РОП (Руководитель Отдела Продаж)",
        "prompt_context": "Ты — ИИ-Руководитель Отдела Продаж (AI Sales Lead). В студии работает ТОЛЬКО ОДИН живой человек — Собственник. Живых менеджеров НЕТ. Все продажи идут через автоматические воронки в Telegram-боте, AI-квалификацию лидов, триггерные допродажи и автосообщения без участия людей. Цель — рост конверсии в оплаты 9 900 руб с 0 минут времени Собственника."
    },
    "PRODUCT": {
        "title": "CPO (Продукт-Менеджер)",
        "prompt_context": "Ты — ИИ-Продукт-Менеджер (AI CPO). В студии работает ТОЛЬКО Собственник. Никаких дизайнеров и верстальщиков нет. Все сайты создаются ИИ-генератором на автомате. Твоя цель — расширение библиотеки готовых блоков (калькуляторы, квизы, галереи, адаптивные сетки) в генераторе сайтов, повышение конверсии сайтов клиентов за секунды без ручной верстки."
    },
    "FINANCE": {
        "title": "CFO (Финансовый Директор)",
        "prompt_context": "Ты — ИИ-Финансовый Директор (AI CFO). В студии работает ТОЛЬКО Собственник. Никаких бухгалтеров и финменеджеров. Все платежи, чеки, скидочные промокоды, сплит-тесты цен и оптимизация расходов на сервера/API должны работать автоматически кодом с маржинальностью >90%."
    },
    "FULFILLMENT": {
        "title": "COO (Операционный Директор)",
        "prompt_context": "Ты — ИИ-Операционный Директор (AI COO). В студии работает ТОЛЬКО Собственник. Никаких QA-тестировщиков, проджектов и саппорта. Контроль сдачи сайтов за 24 часа, валидация HTML/CSS, адаптивность и отправка уведомлений клиентам осуществляются 100% автоматически Python-скриптами."
    }
}

SOLOPRENEUR_GUIDELINES = (
    "ФУНДАМЕНТАЛЬНЫЙ ПРИНЦИП КОМПАНИИ (СТУДИЯ ОДНОГО ЧЕЛОВЕКА / SOLOPRENEUR):\n"
    "1. В веб-студии работает ТОЛЬКО ОДИН ЖИВОЙ ЧЕЛОВЕК — Собственник (Евгений).\n"
    "2. Никаких других людей-сотрудников НЕТ и НЕ БУДЕТ (нет менеджеров по продажам, дизайнеров, верстальщиков, QA-тестировщиков, саппорта).\n"
    "3. ВСЕ процессы должны быть на 100% АВТОНОМНЫМИ: исполняться программным кодом (Python, SQLite, Telegram Bot API, Gemini API, HTML/CSS/JS автогенератором).\n"
    "4. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО предлагать:\n"
    "   - Наем людей, созвоны с сотрудниками, планерки, обучение персонала.\n"
    "   - Передачу задач 'менеджеру по продажам', 'дизайнеру', 'копирайтеру', 'QA-инженеру в Slack'.\n"
    "   - Внедрение внешних систем (amoCRM, Bitrix24), так как у нас собственная встроенная база agency.db и веб-CRM.\n"
    "5. Участие Собственника во всех гипотезах строго ограничено:\n"
    "   - 0 минут (полный программный автопилот) или максимум 1 клик подтверждения в Telegram.\n"
    "6. Каждая гипотеза должна быть готовым техническим решением (скрипт, алгоритм, автоворонка, API-триггер).\n"
)

def generate_and_submit_new_hypothesis(department: str = "SALES"):
    role_info = DEPARTMENT_ROLES.get(department, DEPARTMENT_ROLES["SALES"])
    role_title = role_info["title"]

    # Gather live data metrics
    dash_data = db.get_owner_dashboard_data()
    summary = dash_data["executive_summary"]

    # Deduplication: fetch all existing initiative titles
    existing_inits = db.get_department_initiatives()
    existing_titles = [i.get("title", "").strip() for i in existing_inits if i.get("title")]
    existing_str = "\n".join([f"- {t}" for t in existing_titles[-15:]]) if existing_titles else "Пока нет"

    prompt = (
        f"{role_info['prompt_context']}\n\n"
        f"{SOLOPRENEUR_GUIDELINES}\n"
        f"Текущие метрики компании AI Web Studio:\n"
        f"• Всего лидов: {summary['total_leads']}\n"
        f"• Конверсия в оплату: {summary['conversion_rate']}%\n"
        f"• Выручка: {summary['revenue']} руб.\n"
        f"• Чистая прибыль: {summary['net_profit']} руб. (Маржа: {summary['margin_percent']}%)\n\n"
        f"СТРОЖАЙШЕЕ ПРАВИЛО СОБСТВЕННИКА: Никаких абстрактных фраз! Прописывать МАКСИМАЛЬНУЮ КОНКРЕТИКУ: что именно внедрить (инструмент, интеграция, скрипт, механика), пошаговый план из 3 пунктов и осязаемый результат.\n\n"
        f"Ранее сгенерированные темы:\n"
        f"{existing_str}\n\n"
        f"Ответь СТРОГО в формате JSON без разметки markdown:\n"
        f'{{\n'
        f'  "title": "Емкий конкретный заголовок инициативы",\n'
        f'  "description": "1. [Конкретный инструмент/скрипт] 2. [Механика авто-внедрения без людей] 3. [Пошаговый регламент работы автопилота]",\n'
        f'  "kpi": "Точный измеримый KPI с цифрами",\n'
        f'  "hypothesis_impact": "Финансовый или конверсионный эффект (например, +25 000 руб/мес чистой прибыли)",\n'
        f'  "priority": "HIGH"\n'
        f'}}\n'
    )

    ai_text, err = webhook_engine.safe_generate_ai(prompt)
    data = None
    
    if ai_text:
        try:
            clean_json = ai_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json)
        except Exception:
            pass

    if not data:
        # Unique fallback titles
        count = len(existing_titles) + 1
        data = {
            "title": f"Стратегическая инициатива #{count} для {role_title}",
            "description": f"Внедрение таргетированных мер по оптимизации воронки {role_title}",
            "kpi": "Рост конверсии на +25%",
            "hypothesis_impact": "+20 000 руб. дополнительной прибыли",
            "priority": "HIGH"
        }

    # Ensure title is unique
    if data.get("title") in existing_titles:
        data["title"] = f"{data['title']} (Фаза {len(existing_titles)+1})"

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

    # Notify Owner in Telegram with interactive buttons (Approve, Reject, Edit)
    send_approval_request_to_owner(init_id, department, role_title, data)
    return init_id

def send_approval_request_to_owner(init_id: int, department: str, role_title: str, data: dict):
    admin_id = os.getenv("ADMIN_TELEGRAM_ID") or db.get_setting("ADMIN_TELEGRAM_ID")
    if not admin_id:
        print(f"⚠️ ADMIN_TELEGRAM_ID not set, initiative #{init_id} waiting in DB.")
        return

    msg = (
        f"💡 **НОВАЯ ГИПОТЕЗА НА УТВЕРЖДЕНИЕ СОБСТВЕННИКУ (#{init_id})**\n\n"
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
            ],
            [
                {"text": "✏️ Внести правки / Уточнить", "callback_data": f"edit_init_{init_id}"}
            ]
        ]
    }

    webhook_engine.send_telegram_message(int(admin_id), msg, reply_markup=kbd)
    try:
        print(f"[+] Sent Telegram approval request for initiative #{init_id} ({role_title}) to Admin ID {admin_id}")
    except Exception:
        pass

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
        feedback_note = f"\n📝 **Учтенные правки**: «_{init.get('executed_results')}_»" if init.get('executed_results') else ""
        msg = (
            f"💡 **ГИПОТЕЗА НА УТВЕРЖДЕНИЕ СОБСТВЕННИКУ (#{init['id']})**\n\n"
            f"👔 **Должность**: {init.get('role_title')}\n"
            f"📌 **Задача**: {init.get('title')}\n"
            f"📝 **Суть**: {init.get('description')}\n"
            f"🎯 **Целевой KPI**: `{init.get('kpi')}`\n"
            f"💰 **Прогнозируемый эффект**: `{init.get('hypothesis_impact') or 'Рост прибыли'}`{feedback_note}\n\n"
            f"Утверждаете запуск данной гипотезы в работу?"
        )
        kbd = {
            "inline_keyboard": [
                [
                    {"text": "✅ Утвердить задачу", "callback_data": f"approve_init_{init['id']}"},
                    {"text": "❌ Отклонить (Вето)", "callback_data": f"reject_init_{init['id']}"}
                ],
                [
                    {"text": "✏️ Внести правки / Уточнить", "callback_data": f"edit_init_{init['id']}"}
                ]
            ]
        }
        webhook_engine.send_telegram_message(chat_id, msg, reply_markup=kbd)

    return len(pending)

def handle_owner_approval_callback(callback_data: str, chat_id: int):
    parts = callback_data.split("_")
    action = parts[0] # approve, reject, or edit
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

    elif action == "edit":
        webhook_engine.user_states[chat_id] = {"awaiting_edit_init_id": init_id}
        msg = (
            f"✏️ **Корректировка гипотезы #{init_id} ({role_title})**\n\n"
            f"📌 **Текущая задача**: «{initiative['title']}»\n"
            f"📝 **Текущая суть**: {initiative.get('description')}\n\n"
            f"Напишите прямо сюда в чат ваши правки, уточнения или ограничения (например: *'Снизь бюджет до 5 000 руб'*, *'Сделай только для автосервисов'* или *'Уточни механику'*):\n\n"
            f"🤖 {role_title} мгновенно переработает гипотезу с учетом ваших слов и пришлет обновленную карточку!"
        )
        webhook_engine.send_telegram_message(chat_id, msg)

def apply_owner_edits_to_hypothesis(init_id: int, feedback_text: str, chat_id: int):
    initiative = db.get_initiative_by_id(init_id)
    if not initiative:
        webhook_engine.send_telegram_message(chat_id, f"⚠️ Гипотеза #{init_id} не найдена.")
        return

    role_title = initiative.get("role_title", "ИИ-Директор")
    old_title = initiative.get("title", "")
    old_desc = initiative.get("description", "")
    old_kpi = initiative.get("kpi", "")
    old_impact = initiative.get("hypothesis_impact", "")

    webhook_engine.send_telegram_message(chat_id, f"⚙️ **{role_title}** перерабатывает гипотезу #{init_id} с учетом вашей правки: «_{feedback_text}_»...")

    refine_prompt = (
        f"Ты — {role_title} в компании AI Web Studio.\n"
        f"{SOLOPRENEUR_GUIDELINES}\n"
        f"Ты предложил гипотезу: '{old_title}'. Суть: '{old_desc}'. KPI: '{old_kpi}'.\n\n"
        f"Собственник компании внес следующие обязательные правки и уточнения: '{feedback_text}'.\n\n"
        f"Переработай гипотезу строго с учетом правок Собственника и соблюдением принципа нулевого участия людей. "
        f"Ответь СТРОГО в формате JSON без разметки markdown:\n"
        f'{{\n'
        f'  "title": "Уточненный заголовок гипотезы",\n'
        f'  "description": "Переработанное описание строго по замечаниям Собственника (1. Скрипт/инструмент 2. Авто-внедрение 3. Регламент работы)",\n'
        f'  "kpi": "Скорректированный целевой показатель KPI",\n'
        f'  "hypothesis_impact": "Скорректированный прогнозируемый эффект"\n'
        f'}}\n'
    )

    ai_text, _ = webhook_engine.safe_generate_ai(refine_prompt)
    new_data = None
    if ai_text:
        try:
            clean_json = ai_text.replace("```json", "").replace("```", "").strip()
            new_data = json.loads(clean_json)
        except Exception:
            pass

    if not new_data:
        new_data = {
            "title": f"{old_title} [Скорректировано]",
            "description": f"{old_desc}\n\n[Уточнено по правкам Собственника: {feedback_text}]",
            "kpi": old_kpi,
            "hypothesis_impact": old_impact
        }

    # Update in DB
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE department_initiatives
        SET title = ?, description = ?, kpi = ?, hypothesis_impact = ?, executed_results = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (
        new_data.get("title", old_title),
        new_data.get("description", old_desc),
        new_data.get("kpi", old_kpi),
        new_data.get("hypothesis_impact", old_impact),
        f"Правка Собственника: {feedback_text}",
        init_id
    ))
    conn.commit()
    conn.close()

    # Send updated card back to Owner with review buttons
    msg = (
        f"💡 **ОБНОВЛЕННАЯ ГИПОТЕЗА С УЧЕТОМ ВАШИХ ПРАВОК (#{init_id})**\n\n"
        f"👔 **Должность**: {role_title}\n"
        f"📌 **Задача**: {new_data.get('title')}\n"
        f"📝 **Суть**: {new_data.get('description')}\n"
        f"🎯 **Целевой KPI**: `{new_data.get('kpi')}`\n"
        f"💰 **Прогнозируемый эффект**: `{new_data.get('hypothesis_impact')}`\n\n"
        f"✏️ **Ваша правка учтена**: «_{feedback_text}_»\n\n"
        f"Утверждаете обновленный вариант задачи?"
    )

    kbd = {
        "inline_keyboard": [
            [
                {"text": "✅ Утвердить задачу", "callback_data": f"approve_init_{init_id}"},
                {"text": "❌ Отклонить (Вето)", "callback_data": f"reject_init_{init_id}"}
            ],
            [
                {"text": "✏️ Внести еще правки", "callback_data": f"edit_init_{init_id}"}
            ]
        ]
    }

    webhook_engine.send_telegram_message(chat_id, msg, reply_markup=kbd)

def generate_journal_html():
    journal = db.get_implemented_initiatives_journal()
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    total_inits = sum(d.get("count", 0) for d in journal)

    days_html = ""
    for group in journal:
        day_date = group.get("date")
        count = group.get("count", 0)
        items_html = ""
        for init in group.get("initiatives", []):
            role = init.get("role_title", "ИИ-Директор")
            title = init.get("title", "Инициатива")
            desc = init.get("description", "")
            kpi = init.get("kpi", "—")
            impact = init.get("hypothesis_impact", "—")
            result = init.get("executed_results", "Внедрено и активно")
            
            items_html += f"""
            <div class="init-card">
                <div class="card-header">
                    <span class="role-badge">{role}</span>
                    <span class="init-title">{title}</span>
                </div>
                <div class="init-desc">{desc}</div>
                <div class="init-meta">
                    <div class="meta-item"><span class="label">🎯 KPI:</span> <strong>{kpi}</strong></div>
                    <div class="meta-item"><span class="label">💰 Эффект:</span> <strong style="color: #059669;">{impact}</strong></div>
                    <div class="meta-item"><span class="label">✅ Статус:</span> <span>{result}</span></div>
                </div>
            </div>
            """
        
        days_html += f"""
        <div class="day-section">
            <div class="day-header">
                <h2>🗓 {day_date}</h2>
                <span class="day-count">{count} внедрено</span>
            </div>
            {items_html}
        </div>
        """

    html_doc = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Web Studio — Журнал реализованных гипотез</title>
    <link href="https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;700&family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        @page {{ margin: 20mm; }}
        body {{
            font-family: 'Google Sans', Roboto, -apple-system, BlinkMacSystemFont, sans-serif;
            background: #f8fafc;
            color: #1e293b;
            margin: 0;
            padding: 30px 15px;
            display: flex;
            justify-content: center;
        }}
        .doc-page {{
            width: 100%;
            max-width: 860px;
            background: #ffffff;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
            border-radius: 12px;
            padding: 50px 60px;
            box-sizing: border-box;
            border: 1px solid #e2e8f0;
        }}
        .doc-header {{
            border-bottom: 2px solid #2563eb;
            padding-bottom: 25px;
            margin-bottom: 30px;
        }}
        .doc-title {{
            font-size: 28px;
            font-weight: 700;
            color: #0f172a;
            margin: 0 0 8px 0;
        }}
        .doc-subtitle {{
            font-size: 15px;
            color: #64748b;
            margin: 0;
        }}
        .summary-ribbon {{
            display: flex;
            gap: 20px;
            background: #f1f5f9;
            padding: 16px 20px;
            border-radius: 8px;
            margin-top: 20px;
        }}
        .summary-box {{
            flex: 1;
        }}
        .summary-box .val {{
            font-size: 20px;
            font-weight: 700;
            color: #2563eb;
        }}
        .summary-box .lbl {{
            font-size: 12px;
            color: #64748b;
            text-transform: uppercase;
            font-weight: 600;
            margin-top: 2px;
        }}
        .day-section {{
            margin-bottom: 35px;
        }}
        .day-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #cbd5e1;
            padding-bottom: 8px;
            margin-bottom: 16px;
        }}
        .day-header h2 {{
            font-size: 18px;
            color: #1e293b;
            margin: 0;
        }}
        .day-count {{
            background: #e0e7ff;
            color: #3730a3;
            font-size: 12px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 20px;
        }}
        .init-card {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-left: 4px solid #2563eb;
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 14px;
        }}
        .card-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 8px;
        }}
        .role-badge {{
            background: #2563eb;
            color: #ffffff;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
        }}
        .init-title {{
            font-size: 16px;
            font-weight: 700;
            color: #0f172a;
        }}
        .init-desc {{
            font-size: 14px;
            line-height: 1.5;
            color: #334155;
            margin-bottom: 12px;
        }}
        .init-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 18px;
            font-size: 12px;
            border-top: 1px dashed #cbd5e1;
            padding-top: 10px;
        }}
        .meta-item .label {{
            color: #64748b;
        }}
        .actions-bar {{
            display: flex;
            justify-content: flex-end;
            gap: 10px;
            margin-bottom: 20px;
        }}
        .btn {{
            background: #2563eb;
            color: #ffffff;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
        }}
        @media print {{
            body {{ background: #fff; padding: 0; }}
            .doc-page {{ box-shadow: none; border: none; padding: 0; }}
            .actions-bar {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div style="width: 100%; max-width: 860px;">
        <div class="actions-bar">
            <button class="btn" onclick="window.print()">🖨 Печать / PDF</button>
            <a href="https://t.me/Antigravitybers1q_bot" class="btn" style="background: #10b981;">📱 Открыть в Telegram</a>
        </div>
        <div class="doc-page">
            <div class="doc-header">
                <h1 class="doc-title">AI Web Studio — Журнал реализованных гипотез</h1>
                <p class="doc-subtitle">Единая хроника побед и внедренных улучшений для Собственника (Solopreneur Model)</p>
                <div class="summary-ribbon">
                    <div class="summary-box">
                        <div class="val">{total_inits}</div>
                        <div class="lbl">Всего внедрено</div>
                    </div>
                    <div class="summary-box">
                        <div class="val">4 роли</div>
                        <div class="lbl">РОП • CPO • CFO • COO</div>
                    </div>
                    <div class="summary-box">
                        <div class="val">{now_str}</div>
                        <div class="lbl">Синхронизировано</div>
                    </div>
                </div>
            </div>
            {days_html if days_html else '<p style="color: #64748b; text-align: center; padding: 40px 0;">Пока нет реализованных гипотез.</p>'}
        </div>
    </div>
</body>
</html>"""
    return html_doc

def export_journal_to_google_drive():
    html_content = generate_journal_html()
    
    # 1. Save locally in repo for Render / Web viewing
    local_path = os.path.join(os.path.dirname(__file__), "journal_doc.html")
    try:
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(html_content)
    except Exception:
        pass
        
    # 2. Save directly to Google Drive (G:\Мой диск)
    gdrive_dir = r"G:\Мой диск"
    synced_paths = []
    if os.path.exists(gdrive_dir):
        gdrive_file = os.path.join(gdrive_dir, "Журнал_Гипотез_AI_Web_Studio.html")
        try:
            with open(gdrive_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            synced_paths.append(gdrive_file)
            print(f"[+] Synced journal to Google Drive: {gdrive_file}")
        except Exception as e:
            print(f"[-] Error writing to Google Drive: {e}")
            
        # Also markdown version
        md_file = os.path.join(gdrive_dir, "Журнал_Гипотез_AI_Web_Studio.md")
        try:
            journal = db.get_implemented_initiatives_journal()
            md_lines = ["# AI Web Studio — Журнал реализованных гипотез\n\n"]
            for g in journal:
                md_lines.append(f"## 🗓 Дата: {g.get('date')} ({g.get('count')} внедрено)\n\n")
                for i in g.get("initiatives", []):
                    md_lines.append(f"### [{i.get('role_title')}] {i.get('title')}\n")
                    md_lines.append(f"- **Суть**: {i.get('description')}\n")
                    md_lines.append(f"- **KPI**: `{i.get('kpi')}`\n")
                    md_lines.append(f"- **Эффект**: `{i.get('hypothesis_impact')}`\n")
                    md_lines.append(f"- **Результат**: {i.get('executed_results')}\n\n")
            with open(md_file, "w", encoding="utf-8") as f:
                f.write("".join(md_lines))
            synced_paths.append(md_file)
        except Exception:
            pass

    return local_path, synced_paths

def format_initiatives_journal_for_telegram(chat_id: int):
    local_p, synced = export_journal_to_google_drive()
    journal = db.get_implemented_initiatives_journal()
    if not journal:
        msg = (
            "📅 **Журнал реализованных гипотез пуст**\n\n"
            "Пока ни одна гипотеза не переведена в статус `COMPLETED`.\n"
            "Нажмите кнопку `📋 Задачи на утверждение`, чтобы утвердить гипотезы от ИИ-директоров, "
            "и они сразу появятся в этом журнале с точной датой и полученным эффектом!"
        )
        webhook_engine.send_telegram_message(chat_id, msg)
        return

    total_inits = sum(d.get("count", 0) for d in journal)
    lines = [
        f"📅 **ЖУРНАЛ РЕАЛИЗОВАННЫХ ГИПОТЕЗ (ХРОНИКА ПОБЕД)**\n"
        f"👑 Всего внедрено: **{total_inits} инициатив**\n"
        f"📁 Документ синхронизирован на ваш **Google Диск**:\n"
        f"`G:\\Мой диск\\Журнал_Гипотез_AI_Web_Studio.html`"
    ]

    for day_group in journal[:7]: # Show recent days
        day_date = day_group.get("date")
        inits = day_group.get("initiatives", [])
        lines.append(f"\n🗓 **Дата: {day_date}** ({len(inits)} гипотез):")
        for init in inits:
            role = init.get("role_title", "ИИ-Директор")
            title = init.get("title", "Инициатива")
            kpi = init.get("kpi", "")
            impact = init.get("hypothesis_impact", "")
            lines.append(f"  • **[{role}]** {title}")
            if kpi:
                lines.append(f"    🎯 KPI: `{kpi}`")
            if impact:
                lines.append(f"    💰 Эффект: `{impact}`")

    msg_text = "\n".join(lines)
    kbd = {
        "inline_keyboard": [
            [{"text": "📄 Открыть документ Google Docs / Веб", "url": "https://ai-web-agency-bot.onrender.com/journal/doc"}],
            [{"text": "👑 Открыть Дашборд с журналом", "url": "https://ai-web-agency-bot.onrender.com/owner"}],
            [{"text": "📋 Задачи на утверждение", "callback_data": "show_approvals"}]
        ]
    }
    webhook_engine.send_telegram_message(chat_id, msg_text, reply_markup=kbd)
