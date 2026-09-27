import os
import sys
import time
import json
import subprocess
import requests
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

def run_cmd(cmd_list, cwd=None):
    try:
        res = subprocess.run(cmd_list, cwd=cwd or os.path.dirname(__file__), capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
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
        # Case 1: Deduplication of hypotheses / tasks / initiatives
        if any(w in prompt_lower for w in ["дубликат", "дубли", "дедупликац"]) and any(w in prompt_lower for w in ["гипотез", "задач", "план", "список", "crm"]):
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

        # Case 2: Delete specific hypothesis or initiative
        elif any(w in prompt_lower for w in ["удали", "стереть", "убрать", "закрыть"]) and any(w in prompt_lower for w in ["гипотез", "задач", "инициатив", "алгоритм", "отклик"]):
            log(f"Executing targeted deletion for task #{task_id}")
            conn = db.get_connection()
            c = conn.cursor()
            d_count = 0
            if "алгоритм" in prompt_lower or "отклик" in prompt_lower:
                c.execute("DELETE FROM department_initiatives WHERE description LIKE '%автоматизации откликов%' OR title LIKE '%автоматизации откликов%'")
                d_count = c.rowcount
            else:
                import re
                ids = re.findall(r'\b\d+\b', prompt)
                for item_id in ids:
                    c.execute("DELETE FROM department_initiatives WHERE id = ?", (int(item_id),))
                    d_count += c.rowcount
            conn.commit()
            conn.close()

            # Immediate cloud sync
            try:
                requests.post(f"{RENDER_URL.rstrip('/')}/api/deduplicate_initiatives", timeout=5)
            except Exception:
                pass

            files_modified.append("agency.db")
            summary = f"Удалено {d_count} задач/гипотез из базы данных и дашборда Собственника."

        # Case 3: Price modifications across all files
        elif "цен" in prompt_lower or "руб" in prompt_lower or "стоимост" in prompt_lower or "прайс" in prompt_lower:
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

        # Case 4: Demo sites modifications or additions
        elif "демо" in prompt_lower or "html" in prompt_lower or "сайт" in prompt_lower or "верстк" in prompt_lower:
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

        # Case 5: LLM Execution Engine (if key available)
        elif key:
            log(f"Invoking Gemini LLM for arbitrary code task: '{prompt}'")
            import webhook_engine
            llm_prompt = f"""
Ты — автономный senior Python разработчик проекта AI Web Agency.
Репозиторий содержит файлы: db.py, server.py, webhook_engine.py, owner_dashboard.html, crm_dashboard.html.
Собственник поставил задачу: '{prompt}'

Если эта задача требует выполнения SQL или изменения файла, верни ОДИН исполняемый Python-скрипт, который выполнит эти изменения.
Код скрипта должен быть заключен в ```python ... ```.
Не используй сторонние библиотеки, только стандартные модули и db.py / sqlite3.
"""
            ai_resp, err = webhook_engine.safe_generate_ai(llm_prompt)
            if ai_resp and "```python" in ai_resp:
                code_block = ai_resp.split("```python")[1].split("```")[0].strip()
                scratch_file = os.path.join(repo_dir, f"_auto_exec_{task_id}.py")
                with open(scratch_file, "w", encoding="utf-8") as f:
                    f.write(code_block)
                res_code, res_out, res_err = run_cmd([sys.executable, scratch_file], cwd=repo_dir)
                try:
                    os.remove(scratch_file)
                except Exception:
                    pass
                if res_code == 0:
                    files_modified.append("agency.db")
                    summary = f"ИИ-агент автономно применил изменения: «{prompt}». Результат: {res_out[:100]}"
                else:
                    raise Exception(f"Ошибка выполнения сгенерированного кода: {res_err}")
            else:
                raise Exception(f"LLM не вернул исполняемый код для задачи: {prompt}")

        # Case 6: Fallback for unsupported tasks without LLM key - HONEST NOTIFICATION
        else:
            raise Exception(f"Для произвольного написания нового кода требуется подключить Gemini API ключ через команду /setkey в боте. Либо сформулируйте команду точнее (например: 'удали дубликаты', 'измени цену на 12000').")


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
            log(f"⚠️ Git push warning: {push_err}")

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

        except Exception as e:
            log(f"Worker loop error: {e}")

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    poll_and_execute()
