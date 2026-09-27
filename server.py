import http.server
import socketserver
import os
import json
import urllib.parse
import threading
import requests
import db
import webhook_engine

PORT = int(os.getenv("PORT", 8000))
DIRECTORY = os.path.dirname(__file__)

OWNER_BOT_TOKEN = os.getenv("OWNER_BOT_TOKEN") or "8690113233:AAGLX7LTETCuxgfc79T_av0VKEikBBDTJtY"
CLIENT_BOT_TOKEN = os.getenv("CLIENT_BOT_TOKEN") or "8740453272:AAG5MyW2cvsiPaRT3i3V4feM7bRKoGhyFbU"
TELEGRAM_BOT_TOKEN = OWNER_BOT_TOKEN

class CRMHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        raw_path = parsed.path
        path = raw_path.rstrip('/') or "/"
        query = urllib.parse.parse_qs(parsed.query)

        # Diagnostic endpoint: Tests Telegram API for BOTH Owner and Client bots!
        if path == "/test-tg":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            try:
                r_owner = requests.get(f"https://api.telegram.org/bot{OWNER_BOT_TOKEN}/getMe", timeout=5).json()
                r_owner_wh = requests.get(f"https://api.telegram.org/bot{OWNER_BOT_TOKEN}/getWebhookInfo", timeout=5).json()
                r_client = requests.get(f"https://api.telegram.org/bot{CLIENT_BOT_TOKEN}/getMe", timeout=5).json()
                r_client_wh = requests.get(f"https://api.telegram.org/bot{CLIENT_BOT_TOKEN}/getWebhookInfo", timeout=5).json()
                admin_id = db.get_setting("ADMIN_TELEGRAM_ID")
                all_leads = db.get_all_leads_crm()
                recent_leads = [{"id": l["telegram_id"], "name": l.get("full_name"), "user": l.get("username"), "status": l.get("status")} for l in all_leads[:5]]
                data = {
                    "owner_bot": r_owner,
                    "owner_bot_webhook": r_owner_wh,
                    "client_bot": r_client,
                    "client_bot_webhook": r_client_wh,
                    "admin_id": admin_id,
                    "last_received_update": db.get_setting("LAST_RECEIVED_UPDATE"),
                    "last_process_error": db.get_setting("LAST_PROCESS_ERROR"),
                    "last_send_result": db.get_setting("LAST_TELEGRAM_SEND_RESULT"),
                    "recent_leads": recent_leads,
                    "total_leads": len(all_leads),
                    "RENDER_EXTERNAL_URL": os.getenv("RENDER_EXTERNAL_URL")
                }
                self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
            except Exception as e:
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        # Fetch pending updates from Telegram queue directly without dropping
        elif path == "/check-updates":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            try:
                base_url = os.getenv("RENDER_EXTERNAL_URL") or "https://ai-web-agency-bot.onrender.com"
                wh_owner = f"{base_url.rstrip('/')}/webhook?bot=owner"
                wh_client = f"{base_url.rstrip('/')}/webhook?bot=client"
                
                # Check Owner Bot updates
                requests.get(f"https://api.telegram.org/bot{OWNER_BOT_TOKEN}/deleteWebhook?drop_pending_updates=false", timeout=10)
                r_upd_owner = requests.get(f"https://api.telegram.org/bot{OWNER_BOT_TOKEN}/getUpdates?limit=50", timeout=10).json()
                owner_updates = r_upd_owner.get("result", [])
                for upd in owner_updates:
                    threading.Thread(target=webhook_engine.process_telegram_update, args=(upd,), kwargs={"bot_mode": "owner"}, daemon=True).start()
                requests.post(f"https://api.telegram.org/bot{OWNER_BOT_TOKEN}/setWebhook", json={
                    "url": wh_owner,
                    "drop_pending_updates": False,
                    "allowed_updates": ["message", "edited_message", "callback_query", "channel_post", "edited_channel_post"]
                }, timeout=10)

                # Check Client Bot updates
                requests.get(f"https://api.telegram.org/bot{CLIENT_BOT_TOKEN}/deleteWebhook?drop_pending_updates=false", timeout=10)
                r_upd_client = requests.get(f"https://api.telegram.org/bot{CLIENT_BOT_TOKEN}/getUpdates?limit=50", timeout=10).json()
                client_updates = r_upd_client.get("result", [])
                for upd in client_updates:
                    threading.Thread(target=webhook_engine.process_telegram_update, args=(upd,), kwargs={"bot_mode": "client"}, daemon=True).start()
                requests.post(f"https://api.telegram.org/bot{CLIENT_BOT_TOKEN}/setWebhook", json={
                    "url": wh_client,
                    "drop_pending_updates": False,
                    "allowed_updates": ["message", "edited_message", "callback_query", "channel_post", "edited_channel_post"]
                }, timeout=10)

                res = {
                    "owner_updates_found": len(owner_updates),
                    "owner_updates": owner_updates,
                    "client_updates_found": len(client_updates),
                    "client_updates": client_updates
                }
                self.wfile.write(json.dumps(res, ensure_ascii=False, indent=2).encode("utf-8"))
            except Exception as e:
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        # Direct test message send endpoint: /send-msg?chat_id=...&text=...
        elif path.startswith("/send-msg"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            try:
                chat_id = query.get("chat_id", [None])[0]
                text = query.get("text", ["👑 Проверка связи с Собственником!"])[0]
                if not chat_id:
                    self.wfile.write(json.dumps({"error": "Missing chat_id parameter"}).encode("utf-8"))
                    return
                res = webhook_engine.send_telegram_message(int(chat_id), text, reply_markup=webhook_engine.get_persistent_menu(True))
                self.wfile.write(json.dumps({"chat_id": chat_id, "result": res}, ensure_ascii=False, indent=2).encode("utf-8"))
            except Exception as e:
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        # Webhook & Command Menu Reset Endpoint: Sets Webhooks for BOTH Owner and Client bots!
        elif path == "/set-webhook":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            try:
                base_url = os.getenv("RENDER_EXTERNAL_URL") or "https://ai-web-agency-bot.onrender.com"
                wh_owner = f"{base_url.rstrip('/')}/webhook?bot=owner"
                wh_client = f"{base_url.rstrip('/')}/webhook?bot=client"

                r_wh_owner = requests.post(f"https://api.telegram.org/bot{OWNER_BOT_TOKEN}/setWebhook", json={
                    "url": wh_owner,
                    "drop_pending_updates": False,
                    "allowed_updates": ["message", "edited_message", "callback_query", "channel_post", "edited_channel_post"]
                }, timeout=10).json()

                r_wh_client = requests.post(f"https://api.telegram.org/bot{CLIENT_BOT_TOKEN}/setWebhook", json={
                    "url": wh_client,
                    "drop_pending_updates": False,
                    "allowed_updates": ["message", "edited_message", "callback_query", "channel_post", "edited_channel_post"]
                }, timeout=10).json()

                # Owner bot command menu [/]
                owner_cmds = {
                    "commands": [
                        {"command": "start", "description": "🔄 Главный пульт Собственника"},
                        {"command": "hypothesis", "description": "💡 Совет Директоров: Запустить брейншторм"},
                        {"command": "owner", "description": "👑 Дашборд Собственника (P&L, Прибыль)"},
                        {"command": "crm", "description": "📊 CRM-система управления лидами"},
                        {"command": "setkey", "description": "🔑 Установить Gemini API ключ"}
                    ]
                }
                requests.post(f"https://api.telegram.org/bot{OWNER_BOT_TOKEN}/setMyCommands", json=owner_cmds, timeout=10)

                # Client bot command menu [/]
                client_cmds = {
                    "commands": [
                        {"command": "start", "description": "🚀 Главное меню AI Web Studio"},
                        {"command": "demo", "description": "🎨 Примеры сайтов по 6 нишам"},
                        {"command": "brief", "description": "📝 Заполнить бриф на сайт за 24ч"},
                        {"command": "calculator", "description": "🧮 Калькулятор стоимости сайта"},
                        {"command": "promo", "description": "🎟 Активировать промокод"}
                    ]
                }
                requests.post(f"https://api.telegram.org/bot{CLIENT_BOT_TOKEN}/setMyCommands", json=client_cmds, timeout=10)

                res = {"setWebhookOwner": r_wh_owner, "setWebhookClient": r_wh_client}
                self.wfile.write(json.dumps(res, ensure_ascii=False, indent=2).encode("utf-8"))
            except Exception as e:
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        # Healthcheck / Keep-Alive Ping
        elif path in ["/ping", "/health"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # Serve Web CRM Dashboard on homepage or /crm
        elif path in ["/", "/crm", "/admin", "/crm_dashboard", "/crm_dashboard.html"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            crm_path = os.path.join(DIRECTORY, "crm_dashboard.html")
            with open(crm_path, "rb") as f:
                self.wfile.write(f.read())
            return

        # Serve Owner Executive Dashboard on /owner
        elif path in ["/owner", "/executive", "/dashboard", "/owner_dashboard", "/owner_dashboard.html"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            owner_path = os.path.join(DIRECTORY, "owner_dashboard.html")
            with open(owner_path, "rb") as f:
                self.wfile.write(f.read())
            return

        # API: Autonomous Dev Tasks Pending Queue
        elif path == "/api/dev_tasks/pending":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            tasks = db.get_pending_autonomous_tasks()
            self.wfile.write(json.dumps(tasks, ensure_ascii=False).encode("utf-8"))
            return

        # API: All Autonomous Dev Tasks List
        elif path == "/api/dev_tasks/list":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            tasks = db.get_all_autonomous_tasks()
            self.wfile.write(json.dumps(tasks, ensure_ascii=False).encode("utf-8"))
            return

        # API: Deduplicate Departmental Initiatives
        elif path == "/api/deduplicate_initiatives":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            count = db.deduplicate_initiatives()
            self.wfile.write(json.dumps({"status": "ok", "deleted_count": count}, ensure_ascii=False).encode("utf-8"))
            return

        # API: Resend Pending Approvals to Owner in Telegram
        elif path == "/api/resend_approvals":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            import executive_ai_engine
            count = executive_ai_engine.resend_pending_approvals_to_owner(246189250)
            self.wfile.write(json.dumps({"status": "ok", "count": count}, ensure_ascii=False).encode("utf-8"))
            return

        # API: Implemented Initiatives Journal (Chronicle by Day)
        elif path == "/api/initiatives/journal":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            journal = db.get_implemented_initiatives_journal()
            self.wfile.write(json.dumps(journal, ensure_ascii=False).encode("utf-8"))
            return

        # API: Send Implemented Initiatives Journal to Owner in Telegram
        elif path.startswith("/api/send_journal"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            import executive_ai_engine
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            target_chat = query_params.get("chat_id", ["246189250"])[0]
            executive_ai_engine.format_initiatives_journal_for_telegram(int(target_chat))
            self.wfile.write(json.dumps({"status": "ok", "chat_id": target_chat}, ensure_ascii=False).encode("utf-8"))
            return



        # API: Owner Executive Dashboard Combined Data
        elif path == "/api/owner_dashboard":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            data = db.get_owner_dashboard_data()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            return

        # API: CRM Data (Leads + A/B Stats)
        elif path == "/api/crm_data":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            leads = db.get_all_leads_crm()
            ab_stats = db.get_ab_stats()
            data = {"leads": leads, "ab_stats": ab_stats}
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            return

        # API: Full Chat Dialog History for a Lead
        elif path == "/api/chat_history":
            telegram_id = query.get("telegram_id", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            messages = []
            if telegram_id:
                try:
                    messages = db.get_lead_messages(int(telegram_id))
                except Exception as e:
                    print(f"Error fetching chat history: {e}")
            self.wfile.write(json.dumps(messages, ensure_ascii=False).encode("utf-8"))
            return

        # API: Export CRM Leads as CSV (Item 45)
        elif path == "/api/export_crm":
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8-sig")
            self.send_header("Content-Disposition", "attachment; filename=leads_export.csv")
            self.end_headers()
            
            leads = db.get_all_leads_crm()
            lines = ["Telegram ID;Username;Full Name;Status;Bot Variant;Created At;Updated At"]
            for l in leads:
                lines.append(f"{l.get('telegram_id')};{l.get('username')};{l.get('full_name')};{l.get('status')};{l.get('bot_variant')};{l.get('created_at')};{l.get('updated_at')}")
            
            csv_data = "\n".join(lines)
            self.wfile.write(csv_data.encode("utf-8-sig"))
            return

        # Client Portal Link Endpoint (Item 37)
        elif path.startswith("/status/"):
            target_id_str = path.replace("/status/", "").strip()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            
            lead_info = None
            if target_id_str.isdigit():
                leads = db.get_all_leads_crm()
                lead_info = next((l for l in leads if l['telegram_id'] == int(target_id_str)), None)
            
            if lead_info:
                brief_data = json.loads(lead_info.get("brief_data", "{}"))
                status = lead_info.get("status", "NEW")
                status_texts = {
                    "NEW": "🆕 Заказ создан",
                    "BRIEFING": "📝 Заполнение брифа",
                    "INCOMPLETE_BRIEF": "⚠️ Бриф не дозаполнен",
                    "WAITING_PAYMENT": "💰 Ожидает подтверждения",
                    "PAID": "✅ Оплачен / В разработке",
                    "GENERATED": "🔨 Сайт сгенерирован (на проверке арт-директора)",
                    "DELIVERED": "🚀 Сайт утвержден и доставлен!"
                }
                status_str = status_texts.get(status, status)
                site_url = lead_info.get("site_url", "")
                site_btn = f'<p style="margin-top:20px;"><a href="{site_url}" style="background:#3b82f6;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;">🌐 Открыть готовый сайт</a></p>' if site_url else ''

                html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8"><title>Статус заказа | {brief_data.get('company_name', 'Проект')}</title>
    <style>
        body {{ font-family: sans-serif; background: #0f172a; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; }}
        .card {{ background: #1e293b; padding: 40px; border-radius: 16px; max-width: 500px; width: 100%; border: 1px solid #334155; text-align: center; }}
        .status {{ font-size: 20px; font-weight: bold; color: #10b981; margin: 20px 0; background: #064e3b; padding: 10px; border-radius: 8px; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>🏢 {brief_data.get('company_name', 'Ваш Проект')}</h2>
        <p style="color: #94a3b8; margin-top: 5px;">Статус вашего заказа в AI Web Studio:</p>
        <div class="status">{status_str}</div>
        <p style="color: #cbd5e1; font-size: 14px;">Ниша: {brief_data.get('niche', 'Не указана')}</p>
        {site_btn}
    </div>
</body></html>"""
                self.wfile.write(html.encode("utf-8"))
            else:
                self.wfile.write(b"<html><body><h2>Lead not found</h2></body></html>")
            return

        # Fallback to static files
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Handle Telegram Webhook POST requests via Webhook Engine
        if path.startswith("/webhook") or path.startswith("/telegram-webhook"):
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            # Immediately acknowledge webhook to Telegram to avoid 5-second timeout retries!
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")

            try:
                update_data = json.loads(post_data.decode('utf-8'))
                raw_full = self.path
                bot_mode = "owner" if ("bot=owner" in raw_full or "owner" in path) else ("client" if ("bot=client" in raw_full or "client" in path) else "auto")
                threading.Thread(target=webhook_engine.process_telegram_update, args=(update_data,), kwargs={"bot_mode": bot_mode}, daemon=True).start()
            except Exception as e:
                print(f"Error starting async webhook worker: {e}")
            return

        # API: Direct Admin Message to Telegram Client
        elif path == "/api/send_admin_message":
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            telegram_id = body.get('telegram_id')
            text = body.get('text', '').strip()

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()

            if not telegram_id or not text:
                self.wfile.write(json.dumps({"error": "Missing telegram_id or text"}).encode('utf-8'))
                return

            lead = db.get_or_create_lead(int(telegram_id))
            bot_variant = lead.get('bot_variant', 'Variant A (Консультант)')

            # Send directly to client's Telegram chat from Bot
            sent_res = webhook_engine.send_telegram_message(int(telegram_id), text)
            
            # Log as BOT message in dialog history
            db.log_chat_message(int(telegram_id), "BOT", f"✍️ [Менеджер]: {text}", bot_variant)
            
            # If lead was in REJECTED/OBJECTION, advance to ADMIN_NEGOTIATING
            if lead.get('status') in ['REJECTED', 'OBJECTION', 'LOST']:
                db.update_lead_status(int(telegram_id), 'ADMIN_NEGOTIATING')

            res_data = {"status": "ok", "message": "Сообщение отправлено клиенту в Telegram!", "sent": sent_res}
            self.wfile.write(json.dumps(res_data, ensure_ascii=False).encode('utf-8'))
            return

        # API: Verify / Simulate Payment for Lead
        elif path == "/api/verify_payment":
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            telegram_id = body.get('telegram_id')

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()

            if not telegram_id:
                self.wfile.write(json.dumps({"error": "Missing telegram_id"}).encode('utf-8'))
                return

            db.update_lead_status(int(telegram_id), "PAID")
            
            # Notify client in Telegram
            msg = "✅ **Оплата 9 900 руб. официально подтверждена!**\n\nВаш заказ зафиксирован в системе. Арт-директор приступил к сборке и утверждению макета!"
            webhook_engine.send_telegram_message(int(telegram_id), msg)
            db.log_chat_message(int(telegram_id), "BOT", msg, "Система")

            self.wfile.write(json.dumps({"status": "ok", "message": "Оплата подтверждена!"}).encode('utf-8'))
            return

        # API: Update Lead Status from CRM
        elif path == "/api/update_lead_status":
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            telegram_id = body.get('telegram_id')
            new_status = body.get('status')

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()

            if not telegram_id or not new_status:
                self.wfile.write(json.dumps({"error": "Missing args"}).encode('utf-8'))
                return

            db.update_lead_status(int(telegram_id), new_status)
            self.wfile.write(json.dumps({"status": "ok", "new_status": new_status}).encode('utf-8'))
            return

        # API: Update Departmental Initiative Status from Owner Dashboard
        elif path == "/api/update_initiative_status":
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            init_id = body.get('id')
            new_status = body.get('status')

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()

            if not init_id or not new_status:
                self.wfile.write(json.dumps({"error": "Missing args"}).encode('utf-8'))
                return

            db.update_initiative_status(int(init_id), new_status)
            self.wfile.write(json.dumps({"status": "ok", "id": init_id, "new_status": new_status}).encode('utf-8'))
            return

        # API: Delete Departmental Initiative
        elif path == "/api/delete_initiative":
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            init_id = body.get('id')

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()

            if not init_id:
                self.wfile.write(json.dumps({"error": "Missing id"}).encode('utf-8'))
                return

            deleted = db.delete_department_initiative(int(init_id))
            self.wfile.write(json.dumps({"status": "ok", "id": init_id, "deleted": deleted}).encode('utf-8'))
            return

        # API: Deduplicate Departmental Initiatives (POST)
        elif path == "/api/deduplicate_initiatives":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            count = db.deduplicate_initiatives()
            self.wfile.write(json.dumps({"status": "ok", "deleted_count": count}, ensure_ascii=False).encode('utf-8'))
            return


        # API: Approve / Reject Initiative directly from Owner Web Dashboard
        elif path == "/api/approve_initiative":
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            init_id = body.get('id')
            action = body.get('action') # approve or reject

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()

            if not init_id or not action:
                self.wfile.write(json.dumps({"error": "Missing args"}).encode('utf-8'))
                return

            import executive_ai_engine
            admin_id = os.getenv("ADMIN_TELEGRAM_ID") or db.get_setting("ADMIN_TELEGRAM_ID")
            chat_id = int(admin_id) if admin_id and str(admin_id).isdigit() else 0
            executive_ai_engine.handle_owner_approval_callback(f"{action}_init_{init_id}", chat_id)
            
            self.wfile.write(json.dumps({"status": "ok", "id": init_id, "action": action}).encode('utf-8'))
            return

        # API: Trigger Hypothesis Generation from Owner Web Dashboard
        elif path == "/api/generate_hypotheses":
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8')) if content_length > 0 else {}
            department = body.get('department', 'ALL')

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()

            import executive_ai_engine
            generated_ids = []
            if department in ["SALES", "PRODUCT", "FINANCE", "FULFILLMENT"]:
                init_id = executive_ai_engine.generate_and_submit_new_hypothesis(department)
                generated_ids.append(init_id)
            else:
                for d in ["SALES", "PRODUCT", "FINANCE", "FULFILLMENT"]:
                    init_id = executive_ai_engine.generate_and_submit_new_hypothesis(d)
                    generated_ids.append(init_id)

            self.wfile.write(json.dumps({"status": "ok", "generated_ids": generated_ids}).encode('utf-8'))
            return

        # API: Create Autonomous Dev Task
        elif path == "/api/dev_tasks/create":
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            chat_id = body.get('chat_id', 246189250)
            prompt = body.get('prompt', '').strip()

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()

            if not prompt:
                self.wfile.write(json.dumps({"error": "Missing prompt"}).encode('utf-8'))
                return

            task_id = db.create_autonomous_task(int(chat_id), prompt)
            self.wfile.write(json.dumps({"status": "ok", "task_id": task_id}).encode('utf-8'))
            return

        # API: Complete / Update Autonomous Dev Task from Worker
        elif path == "/api/dev_tasks/complete":
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            task_id = body.get('id')
            status = body.get('status', 'COMPLETED')
            commit_hash = body.get('commit_hash', '')
            files_changed = body.get('files_changed', '')
            summary = body.get('summary', '')
            error_msg = body.get('error_message', '')
            chat_id = body.get('chat_id', 246189250)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()

            if not task_id:
                self.wfile.write(json.dumps({"error": "Missing task_id"}).encode('utf-8'))
                return

            db.update_autonomous_task(int(task_id), status, commit_hash, files_changed, summary, error_msg)

            # Send Telegram notification directly to Owner via Bot!
            if status == "COMPLETED":
                base_url = os.getenv("RENDER_EXTERNAL_URL") or "https://ai-web-agency-bot.onrender.com"
                base = base_url.rstrip('/')
                
                links_section = ""
                if files_changed:
                    links = []
                    for f in files_changed.split(","):
                        f = f.strip()
                        if f.startswith("generated_sites/"):
                            fname = f.replace("generated_sites/", "")
                            links.append(f"• 🌐 [{f}]({base}/generated_sites/{fname})")
                    if links:
                        links_section = "\n\n📱 **Ссылки для открытия с телефона**:\n" + "\n".join(links)

                tg_msg = (
                    f"🚀 **Автономная задача #{task_id} ВЫПОЛНЕНА и ЗАДЕПЛОЕНА!**\n\n"
                    f"📝 **Результат**: {summary}\n"
                    f"📄 **Файлы**: `{files_changed}`\n"
                    f"📌 **Коммит**: `{commit_hash}`"
                    f"{links_section}\n\n"
                    f"🌐 Сервер перезапущен с изменениями: {base}"
                )
            else:
                tg_msg = f"⚠️ **Ошибка при выполнении задачи #{task_id}**:\n`{error_msg}`"

            webhook_engine.send_telegram_message(int(chat_id), tg_msg, reply_markup=webhook_engine.get_persistent_menu(True))
            self.wfile.write(json.dumps({"status": "ok", "task_id": task_id}).encode('utf-8'))
            return

        self.send_response(404)
        self.end_headers()

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

def run_server():
    db.init_db()
    try:
        pruned = db.deduplicate_initiatives()
        if pruned:
            print(f"[+] Pruned {pruned} duplicate initiatives on server start.")
    except Exception as e:
        print(f"Warning during startup deduplication: {e}")

    with ThreadedTCPServer(("", PORT), CRMHandler) as httpd:
        print(f"Web CRM & Health Server running at http://0.0.0.0:{PORT}")
        httpd.serve_forever()


if __name__ == "__main__":
    run_server()
