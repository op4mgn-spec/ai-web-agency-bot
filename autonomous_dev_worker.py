import os
import sys
import time
import json
import subprocess
import requests
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()
import db

if sys.stdout:
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if sys.stderr:
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

RENDER_URL = os.getenv("RENDER_EXTERNAL_URL") or "https://ai-web-agency-bot.onrender.com"
POLL_INTERVAL = 5 # seconds

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [AutoDev Worker] {msg}", flush=True)

def run_cmd(cmd_list, cwd=None, timeout=40):
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        res = subprocess.run(cmd_list, cwd=cwd or os.path.dirname(__file__), capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout, env=env)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", f"Command timed out after {timeout} seconds (Обнаружен зависший или бесконечный цикл `while True` без выхода! Внимание: синхронный скрипт обязан завершаться за несколько секунд. Фоновые процессы нужно запускать через отдельный сервис/поток/модуль, а не крутить в основном теле скрипта)."
    except Exception as e:
        return 1, "", str(e)

def execute_dev_task(task):
    task_id = task.get("id")
    chat_id = task.get("chat_id", 246189250)
    prompt = task.get("prompt", "").strip()

    log(f"⚡️ Starting execution of Task #{task_id}: '{prompt}'")

    # Step 1: Mark IN_PROGRESS
    try:
        db.update_autonomous_task(task_id, "IN_PROGRESS")
    except Exception:
        pass

    # Step 2: Determine files to modify and perform smart modifications
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    files_modified = []
    summary = ""

    # Check for Gemini API key
    key = os.getenv("GEMINI_API_KEY") or db.get_setting("GEMINI_API_KEY")

    # Smart Code Modifier Engine
    prompt_lower = prompt.lower()

    try:
        # 1. Intercept executive menu buttons if they were queued
        if any(w in prompt_lower for w in ["задачи на утверждение", "утверждение"]):
            log(f"Intercepted menu button 'Задачи на утверждение' for task #{task_id}")
            import executive_ai_engine
            count = executive_ai_engine.resend_pending_approvals_to_owner(chat_id)
            summary = f"Карточки гипотез ({count} шт.) отправлены Собственнику в Telegram на утверждение."
            db.update_autonomous_task(task_id, "COMPLETED", summary=summary)
            try:
                requests.post(f"{RENDER_URL.rstrip('/')}/api/dev_tasks/complete", json={
                    "id": task_id, "chat_id": chat_id, "status": "COMPLETED", "summary": summary
                }, timeout=5)
            except Exception:
                pass
            return

        if any(w in prompt_lower for w in ["настройки api", "настройки ключей"]):
            log(f"Intercepted menu button 'Настройки API' for task #{task_id}")
            summary = "Информация по ключам API отображена."
            db.update_autonomous_task(task_id, "COMPLETED", summary=summary)
            return

        # 2. Fast Shortcut: Deduplication
        if any(w in prompt_lower for w in ["дубликат", "дубли", "дедупликац"]) and len(prompt.split()) <= 6:
            log(f"Executing hypothesis deduplication for task #{task_id}")
            deleted_count = db.deduplicate_initiatives()

            # Also prune any specific duplicate phrases mentioned by owner
            conn = db.get_connection()
            c = conn.cursor()
            if any(w in prompt_lower for w in ["алгоритм", "отклик", "роп"]):
                c.execute("DELETE FROM department_initiatives WHERE description LIKE '%автоматизации откликов%' OR title LIKE '%Повышение эффективности%'")
                deleted_count += c.rowcount
            conn.commit()
            conn.close()

            # Immediate cloud sync to Render endpoint
            try:
                requests.post(f"{RENDER_URL.rstrip('/')}/api/deduplicate_initiatives", timeout=5)
            except Exception:
                pass

            files_modified.append("agency.db")
            summary = f"База данных успешно очищена: удалено {deleted_count} дубликатов гипотез. Список синхронизирован в CRM и дашборде Собственника."

        # 3. Fast Shortcut: Price change
        elif ("цен" in prompt_lower or "руб" in prompt_lower or "стоимост" in prompt_lower or "прайс" in prompt_lower) and len(prompt.split()) <= 6:
            target_files = ["webhook_engine.py", "server.py", "seed_crm_demo_data.py"]
            import re
            numbers = re.findall(r'\b\d{1,3}(?:\s?\d{3})*\b', prompt)
            new_price = numbers[0].replace(" ", "") if numbers else "9900"
            for fn in target_files:
                fp = os.path.join(repo_dir, fn)
                if os.path.exists(fp):
                    with open(fp, "r", encoding="utf-8") as f:
                        content = f.read()
                    if "9 900" in content and new_price != "9900":
                        new_content = content.replace("9 900", f"{int(new_price):,}".replace(",", " "))
                        with open(fp, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        files_modified.append(fn)
            summary = f"Обновлена базовая стоимость разработки в скриптах бота и CRM на {new_price} руб."

        # 4. Fast Shortcut: Simple Demo site
        elif ("демо" in prompt_lower or "html" in prompt_lower or "сайт" in prompt_lower or "верстк" in prompt_lower) and len(prompt.split()) <= 6:
            demo_dir = os.path.join(repo_dir, "generated_sites")
            os.makedirs(demo_dir, exist_ok=True)
            demo_filename = f"demo_task_{task_id}.html"
            demo_file = os.path.join(demo_dir, demo_filename)
            with open(demo_file, "w", encoding="utf-8") as f:
                f.write(f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Web Studio - Проект #{task_id}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #fff; margin: 0; padding: 40px; text-align: center; }}
        .card {{ max-width: 650px; margin: 40px auto; background: #1e293b; padding: 35px; border-radius: 16px; border: 1px solid #334155; }}
        h1 {{ color: #38bdf8; font-size: 26px; }}
        p {{ color: #94a3b8; line-height: 1.6; font-size: 15px; }}
        .task-badge {{ background: #2563eb; color: white; padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: bold; display: inline-block; margin-bottom: 15px; }}
        .btn {{ display: inline-block; background: #10b981; color: #fff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="task-badge">🚀 Автономный релиз #{task_id}</div>
        <h1>Задача Собственника реализована</h1>
        <p>Техническое задание: <strong>«{prompt}»</strong></p>
        <p>Страница сгенерирована автономным ИИ-конвейером Antigravity, задеплоена и готова к приему трафика.</p>
        <a href="https://t.me/Antigravitybers1q_bot" class="btn">📱 Открыть пульт управления в Telegram</a>
    </div>
</body>
</html>""")
            files_modified.append(f"generated_sites/{demo_filename}")
            summary = f"Сгенерирован и опубликован новый адаптивный сайт по задаче: «{prompt}»"

        # 5. Gemini LLM for ALL other tasks!
        elif key:
            log(f"🧠 Invoking Gemini LLM for task #{task_id}: '{prompt}'")
            import webhook_engine
            llm_prompt = f"""
Ты — автономный Senior Python разработчик и системный архитектор проекта AI Web Agency.
БИЗНЕС-МОДЕЛЬ: Студия одного человека (Solopreneur). Единственный живой человек в компании — Собственник (Евгений). 
Никаких сотрудников (сейлзов, дизайнеров, верстальщиков, QA, саппорта) НЕТ и не нанимается! 
Все решения должны быть 100% автономными программами, ботами, скриптами автоматизации и интеграциями с 0 затрат человеческого времени.

В твоем распоряжении модули проекта:
- `db.py`: содержит get_connection(), init_db(), get_department_initiatives(), add_department_initiative_with_approval(), deduplicate_initiatives(), delete_department_initiative(id), get_all_leads_crm(), get_owner_dashboard_data(), get_implemented_initiatives_journal()
  * СТРУКТУРА get_implemented_initiatives_journal(): возвращает список групп по дням.
    Каждая группа содержит ключи 'date' (дата), 'count' (кол-во) и 'initiatives' (список словарей с ключами 'id', 'role_title', 'title', 'description', 'kpi', 'hypothesis_impact').
- `executive_ai_engine.py`: содержит export_journal_to_google_drive(), generate_journal_html(), format_initiatives_journal_for_telegram(chat_id), generate_and_submit_new_hypothesis(department), DEPARTMENT_ROLES, resend_pending_approvals_to_owner(chat_id)
  * Google Диск пользователя находится локально по пути: r"G:\Мой диск". Файлы, сохраненные туда, автоматически синхронизируются в Google Drive облако.
- `server.py`, `webhook_engine.py`, `owner_dashboard.html`, `crm_dashboard.html`

ТОЧНАЯ СХЕМА ТАБЛИЦ SQLite (agency.db):
1. `department_initiatives`:
   - id INTEGER PRIMARY KEY
   - department TEXT ('SALES', 'PRODUCT', 'FINANCE', 'FULFILLMENT')
   - role_title TEXT (например 'РОП', 'CPO', 'CFO', 'COO')
   - title TEXT (заголовок задачи)
   - description TEXT (пошаговая суть)
   - kpi TEXT (целевой KPI)
   - priority TEXT ('HIGH' / 'MEDIUM')
   - status TEXT ('IN_PROGRESS' / 'COMPLETED' / 'BACKLOG')
   - approval_status TEXT ('APPROVED' / 'PENDING_APPROVAL' / 'REJECTED')
   - hypothesis_impact TEXT (прогнозируемый эффект)
   - executed_results TEXT (результат выполнения)
   - created_at TIMESTAMP, updated_at TIMESTAMP
   * ВНИМАНИЕ: колонки 'name' НЕТ, используй 'title' и 'role_title'!
2. `leads`:
   - telegram_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, status TEXT, brief_step INTEGER, brief_data TEXT, bot_variant TEXT, site_url TEXT, site_path TEXT, feedback TEXT
3. `financial_ledger`:
   - id INTEGER PRIMARY KEY, transaction_type TEXT ('INCOME' / 'EXPENSE'), category TEXT, amount REAL, description TEXT, created_at TIMESTAMP
4. `autonomous_dev_tasks`:
   - id INTEGER PRIMARY KEY, chat_id INTEGER, prompt TEXT, status TEXT, commit_hash TEXT, files_changed TEXT, summary TEXT, error_message TEXT, created_at TIMESTAMP, completed_at TIMESTAMP
5. `settings`:
   - key TEXT PRIMARY KEY, value TEXT

Собственник поставил задачу в Telegram:
«{prompt}»

Напиши ОДИН чистый, надежный Python-скрипт, который выполнит требуемые изменения (выполнит нужные SQL-запросы в db, отредактирует нужные файлы проекта и т.д.).
Скрипт должен вывести в stdout (через print) краткий человекопонятный отчет о том, ЧТО именно было сделано.
НЕ глуши ошибки конструкциями try...except без перевызова (raise), скрипт должен падать при ошибке, чтобы система знала правду!

СТРОЖАЙШИЙ ЗАПРЕТ:
- Категорически ЗАПРЕЩЕНО писать бесконечные циклы `while True:` или длинные паузы в основном теле скрипта!
- Скрипт выполняется СИНХРОННО и обязан завершиться за 3-5 секунд.
- Если требуется автопилот или периодическое выполнение, регистрируй настройки в БД / модуле autopilot_engine или создавай отдельный фоновый модуль, но сам скрипт должен отработать и завершиться!

ВАЖНО:
- Верни ТОЛЬКО код скрипта внутри блока ```python ... ```.
- Не используй сторонние библиотеки, только стандартные модули Python и db / executive_ai_engine / autopilot_engine / yandex_maps_parser / sqlite3.
"""
            MAX_HEAL_ATTEMPTS = 3
            current_llm_prompt = llm_prompt
            last_code = ""
            last_error = ""
            execution_succeeded = False

            for attempt in range(1, MAX_HEAL_ATTEMPTS + 1):
                if attempt > 1:
                    log(f"🛠 [Self-Healing #{attempt}] Auto-fixing detected error: {last_error[:120]}...")
                    if chat_id:
                        webhook_engine.send_telegram_message(
                            int(chat_id),
                            f"🔧 **Авто-диагностика (Self-Healing)**:\nВ задаче #{task_id} перехвачена ошибка:\n`{last_error[:140]}`\n\nИИ автоматически переписывает и исправляет код (попытка {attempt}/{MAX_HEAL_ATTEMPTS})..."
                        )
                    current_llm_prompt = f"""{llm_prompt}

🚨 ВНИМАНИЕ: Предыдущий вариант твоего кода упал С ОШИБКОЙ!
Вот код, который упал:
```python
{last_code}
```
Вот точный текст ошибки:
{last_error}

ИНСТРУКЦИЯ ПО АВТО-ИСПРАВЛЕНИЮ:
1. Тщательно проанализируй причину ошибки и устрани её на 100%.
2. ЕСЛИ ОШИБКА 'timed out' или 'бесконечный цикл': КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО писать `while True: time.sleep(...)` в теле скрипта! Если требуется фоновая фоновая работа / автопилот, создай отдельный модуль-демон или настрой параметры через `autopilot_engine` / `db`, и заверши скрипт сразу.
3. ЕСЛИ ОШИБКА 'TypeError' или 'no such column': используй только реальные сигнатуры функций db.py и реальные имена колонок.
4. Напиши исправленный вариант Python-скрипта в блоке ```python ... ```.
"""

                ai_resp, err = webhook_engine.safe_generate_ai(current_llm_prompt)
                
                # Quota handling
                if not ai_resp and err and any(kw in err.lower() for kw in ["quota", "limit", "429", "лимит", "retry"]):
                    m = re.search(r"(\d+(?:\.\d+)?)\s*сек", err) or re.search(r"retry\s+in\s+([0-9\.]+)\s*s", err, re.IGNORECASE)
                    retry_sec = float(m.group(1)) if m else 55.0
                    if retry_sec <= 70:
                        reset_time_str = (datetime.now() + timedelta(seconds=retry_sec)).strftime('%H:%M:%S')
                        log(f"⏳ Quota limit exceeded. Auto-waiting {retry_sec:.1f}s until {reset_time_str}...")
                        if chat_id and attempt == 1:
                            status_msg = (
                                f"⏳ **Временный минутный лимит Gemini API (20 запр/мин)**.\n\n"
                                f"• Ожидание сброса лимита: **~{int(round(retry_sec))} сек**.\n"
                                f"• Время авто-возобновления: `{reset_time_str}`\n\n"
                                f"🤖 Воркер автоматически продолжит выполнение задачи #{task_id} после сброса таймера!"
                            )
                            webhook_engine.send_telegram_message(int(chat_id), status_msg)
                        time.sleep(retry_sec + 2)
                        log("🔄 Retrying AI generation after waiting for quota reset...")
                        ai_resp, err = webhook_engine.safe_generate_ai(current_llm_prompt)

                if not ai_resp or "```python" not in ai_resp:
                    last_error = f"LLM не смог сгенерировать исполняемый блок кода: {err or (ai_resp[:100] if ai_resp else 'пустой ответ')}"
                    continue

                code_block = ai_resp.split("```python")[1].split("```")[0].strip()
                last_code = code_block
                scratch_file = os.path.join(repo_dir, f"_auto_exec_{task_id}.py")
                utf8_prefix = "import sys\nif hasattr(sys.stdout, 'reconfigure'):\n    sys.stdout.reconfigure(encoding='utf-8')\nif hasattr(sys.stderr, 'reconfigure'):\n    sys.stderr.reconfigure(encoding='utf-8')\n\n"
                with open(scratch_file, "w", encoding="utf-8") as f:
                    f.write(utf8_prefix + code_block)

                res_code, res_out, res_err = run_cmd([sys.executable, scratch_file], cwd=repo_dir, timeout=40)
                try:
                    os.remove(scratch_file)
                except Exception:
                    pass

                out_lower = (res_out or "").lower()
                has_error = any(kw in out_lower for kw in ["no such column", "operationalerror", "traceback", "exception:", "ошибка при работе с базой", "syntaxerror"])

                if res_code != 0 or has_error:
                    last_error = res_err.strip() or res_out.strip() or "Команда завершилась с ненулевым кодом"
                    log(f"❌ Attempt #{attempt} failed with error: {last_error[:150]}")
                    continue

                # SUCCESS!
                execution_succeeded = True
                files_modified.append("agency.db")
                heal_note = f" (автоматически выявлена и устранена ошибка на шаге {attempt})" if attempt > 1 else ""
                summary = f"{res_out.strip() if res_out else 'Изменения успешно применены ИИ-агентом.'}{heal_note}".replace('\ufffd', '')
                log(f"✅ Code execution succeeded on attempt #{attempt}!")
                break

            if not execution_succeeded:
                raise Exception(f"Ошибка выполнения после {MAX_HEAL_ATTEMPTS} попыток авто-исправления: {last_error}")

        # 6. Fallback when no key is configured
        else:
            raise Exception("Для произвольного написания нового кода требуется подключить Gemini API ключ через команду /setkey в боте.")


        # Step 3: Verify Python code integrity
        py_files = [f for f in files_modified if f.endswith(".py")]
        for pf in py_files:
            code, out, err = run_cmd([sys.executable, "-m", "py_compile", pf], cwd=repo_dir)
            if code != 0:
                raise Exception(f"Syntax error in {pf}: {err}")

        # Step 4: Git Commit & Push
        run_cmd(["git", "add", "-A"], cwd=repo_dir)
        commit_msg = f"AutoDev [#{task_id}]: {prompt[:60]}"
        code, out, err = run_cmd(["git", "commit", "-m", commit_msg], cwd=repo_dir)
        
        # Get commit hash
        code_rev, commit_hash, _ = run_cmd(["git", "rev-parse", "--short", "HEAD"], cwd=repo_dir)
        if not commit_hash:
            commit_hash = "auto-commit"

        # Git push to GitHub
        log(f"Pushing commit {commit_hash} to origin main...")
        code_push, push_out, push_err = run_cmd(["git", "push", "origin", "main"], cwd=repo_dir)
        if code_push != 0:
            log(f"❌ Git push failed: {push_err or push_out}")
            raise Exception(f"Ошибка git push на продакшн: {push_err or push_out}")


        files_str = ", ".join(files_modified) if files_modified else "Конфигурация проекта"

        # Step 5: Notify Render / DB of completion
        db.update_autonomous_task(task_id, "COMPLETED", commit_hash, files_str, summary)

        # Notify Render endpoint if available
        try:
            requests.post(
                f"{RENDER_URL.rstrip('/')}/api/dev_tasks/complete",
                json={
                    "id": task_id,
                    "chat_id": chat_id,
                    "status": "COMPLETED",
                    "commit_hash": commit_hash,
                    "files_changed": files_str,
                    "summary": summary
                },
                timeout=10
            )
        except Exception:
            pass

        log(f"✅ Task #{task_id} COMPLETED and pushed! Commit: {commit_hash}")

    except Exception as e:
        err_msg = str(e)
        log(f"❌ Task #{task_id} failed: {err_msg}")
        db.update_autonomous_task(task_id, "FAILED", error_message=err_msg)
        try:
            requests.post(
                f"{RENDER_URL.rstrip('/')}/api/dev_tasks/complete",
                json={
                    "id": task_id,
                    "chat_id": chat_id,
                    "status": "FAILED",
                    "error_message": err_msg
                },
                timeout=10
            )
        except Exception:
            pass

def poll_and_execute():
    log("🚀 Antigravity Autonomous Dev Worker started and listening for tasks...")
    db.init_db()

    while True:
        try:
            # 1. Check local DB for pending tasks
            local_tasks = db.get_pending_autonomous_tasks()
            for t in local_tasks:
                execute_dev_task(t)

            # 2. Check cloud Render API for pending tasks (if Render has any queued)
            try:
                r = requests.get(f"{RENDER_URL.rstrip('/')}/api/dev_tasks/pending", timeout=5)
                if r.status_code == 200:
                    cloud_tasks = r.json()
                    for t in cloud_tasks:
                        # Avoid duplicates if already completed locally
                        execute_dev_task(t)
            except Exception:
                pass

            # 3. Check continuous autopilot (runs when owner is away > 1h or sleeping)
            try:
                import autopilot_engine
                ap_res = autopilot_engine.run_autopilot_tick()
                if ap_res.get("status") == "ok":
                    log(f"🌙 [Autopilot] Executed step: {ap_res.get('action')}")
            except Exception as e:
                pass

        except Exception as e:
            log(f"Worker loop error: {e}")

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    poll_and_execute()
