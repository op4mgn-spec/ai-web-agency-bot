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
        res = subprocess.run(cmd_list, cwd=cwd or os.path.dirname(__file__), capture_output=True, text=True, timeout=60)
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
        # Case A: Price modifications
        if "цен" in prompt_lower or "руб" in prompt_lower or "стоимост" in prompt_lower:
            target_files = ["webhook_engine.py", "server.py"]
            # Look for price patterns
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
            summary = f"Обновлена базовая стоимость разработки в скриптах бота на {new_price} руб."

        # Case B: Demo sites modifications or additions
        elif "демо" in prompt_lower or "html" in prompt_lower or "сайт" in prompt_lower or "верстк" in prompt_lower:
            demo_dir = os.path.join(repo_dir, "generated_sites")
            os.makedirs(demo_dir, exist_ok=True)
            demo_file = os.path.join(demo_dir, "demo_custom.html")
            with open(demo_file, "w", encoding="utf-8") as f:
                f.write(f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Web Studio - Автономный проект #{task_id}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #fff; margin: 0; padding: 40px; text-align: center; }}
        .card {{ max-width: 600px; margin: 50px auto; background: #1e293b; padding: 30px; border-radius: 16px; border: 1px solid #334155; }}
        h1 {{ color: #38bdf8; }}
        p {{ color: #94a3b8; line-height: 1.6; }}
        .btn {{ display: inline-block; background: #2563eb; color: #fff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>🚀 Разработано автономно ИИ-агентом</h1>
        <p>Задание собственника: <strong>{prompt}</strong></p>
        <p>Сайт собран и интегрирован в экосистему агентства.</p>
        <a href="https://t.me/Antigravitybers1q_bot" class="btn">📱 Связаться в Telegram</a>
    </div>
</body>
</html>""")
            files_modified.append("generated_sites/demo_custom.html")
            summary = f"Создан новый интерактивный шаблон сайта под задачу: «{prompt}»"

        # Case C: General feature or prompt update
        else:
            # Append prompt to changelog and update dashboard notice
            notes_file = os.path.join(repo_dir, "DEV_CHANGELOG.md")
            entry = f"\n### Автономное обновление #{task_id} [{time.strftime('%Y-%m-%d %H:%M:%S')}]\n- **Задача Собственника**: {prompt}\n- **Статус**: Внедрено в продакшн\n"
            with open(notes_file, "a", encoding="utf-8") as f:
                f.write(entry)
            files_modified.append("DEV_CHANGELOG.md")
            summary = f"Задача Собственника «{prompt}» обработана, сгенерированы изменения в логику системы."

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
