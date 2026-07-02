#!/usr/bin/env python3
"""HTTP-сервер для перегляду всіх проєктів Emerald Inc."""
import http.server
import socketserver
import os
import sys
import json
import smtplib
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

PORT = 8080
# Запускаємо з папки Projects, щоб були доступні всі проєкти
PROJECTS_DIR = "/Users/fedir/Projects"

# Налаштування email (можна змінити на реальні)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = ""  # ваш email
SMTP_PASS = ""  # ваш пароль або app password
TO_EMAIL = "hello@emerald.inc"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PROJECTS_DIR, **kwargs)

    def do_POST(self):
        """Обробка POST-запитів (відправка email)"""
        if self.path == "/api/send-email":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode("utf-8"))

            name = data.get("name", "")
            email = data.get("email", "")
            message = data.get("message", "")

            if not name or not email or not message:
                self._send_json(400, {"error": "Будь ласка, заповніть всі поля"})
                return

            # Якщо SMTP не налаштовано, просто логуємо
            if not SMTP_USER or not SMTP_PASS:
                print(f"\n📧 Отримано повідомлення від {name} ({email}):")
                print(f"   {message}\n")
                self._send_json(200, {"success": True, "message": "Дякуємо! Ваше повідомлення отримано."})
                return

            try:
                msg = MIMEMultipart()
                msg["From"] = SMTP_USER
                msg["To"] = TO_EMAIL
                msg["Subject"] = f"Повідомлення від {name} ({email})"

                body = f"Ім'я: {name}\nEmail: {email}\n\nПовідомлення:\n{message}"
                msg.attach(MIMEText(body, "plain", "utf-8"))

                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                    server.starttls()
                    server.login(SMTP_USER, SMTP_PASS)
                    server.send_message(msg)

                self._send_json(200, {"success": True, "message": "Дякуємо! Ваше повідомлення відправлено."})
            except Exception as e:
                print(f"[ERROR] Помилка відправки email: {e}")
                self._send_json(500, {"error": "Помилка відправки. Спробуйте пізніше."})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_OPTIONS(self):
        """CORS preflight"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _send_json(self, status, data):
        """Відправити JSON-відповідь"""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        if len(args) >= 3:
            print(f"[SERVER] {args[0]} {args[1]} {args[2]}")
        else:
            print(f"[SERVER] {' '.join(str(a) for a in args)}")

if __name__ == "__main__":
    os.chdir(PROJECTS_DIR)
    print(f"🌐 Emerald Inc. — сервер запущено!")
    print(f"   Сайт:        http://localhost:{PORT}/EMERALD.inc/index.html")
    print(f"   E-suslya:    http://localhost:{PORT}/e-suslya/index.html")
    print(f"   Emerald:     http://localhost:{PORT}/Emerald/public/index.html")
    print(f"   Натисніть Ctrl+C для зупинки\n")
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Сервер зупинено.")
            httpd.server_close()
            sys.exit(0)
