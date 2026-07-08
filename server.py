#!/usr/bin/env python3
"""HTTP-сервер для перегляду всіх проєктів Emerald Inc."""
import http.server
import socketserver
import os
import sys
import json
import re
import smtplib
from urllib.parse import quote
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

PORT = 8080
PROJECTS_DIR = "/Users/fedir/Projects"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = ""  # ваш email
SMTP_PASS = ""  # ваш пароль або app password
TO_EMAIL = "hello@emerald.inc"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PROJECTS_DIR, **kwargs)

    def do_GET(self):
        if self.path == "/api/projects":
            self._send_json(200, self._collect_projects())
            return
        super().do_GET()

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

    def _collect_projects(self):
        projects = []
        with os.scandir(PROJECTS_DIR) as entries:
            for entry in sorted(entries, key=lambda item: item.name.lower()):
                if not entry.is_dir() or entry.name.startswith("."):
                    continue
                projects.append(self._build_project_entry(entry.path))
        return projects

    def _build_project_entry(self, project_dir):
        name = os.path.basename(project_dir)
        summary = ""
        description = ""
        tags = []
        readme_path = os.path.join(project_dir, "README.md")

        if os.path.exists(readme_path):
            text = self._read_text(readme_path)
            summary = self._extract_summary(text)
            description = self._extract_description(text)
            tags = self._extract_tags(text)

        if not summary:
            summary = self._extract_html_title(project_dir) or f"Проєкт {name}"
        if not description:
            description = summary
        if not tags:
            tags = self._guess_tags(project_dir)

        return {
            "name": name,
            "icon": self._guess_icon(name, summary),
            "summary": summary,
            "description": description,
            "subtitle": "Проєкт зі складу Projects",
            "tags": tags,
            "openPath": self._resolve_open_path(project_dir),
        }

    def _read_text(self, path):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                return handle.read()
        except FileNotFoundError:
            return ""

    def _extract_summary(self, text):
        lines = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("---") or line.startswith("!"):
                continue
            line = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", line)
            line = line.replace("|", " ")
            if line.startswith("```"):
                continue
            if line.startswith("- ") or line.startswith("* "):
                continue
            if line.startswith("|"):
                continue
            if line.startswith(">"):
                continue
            if line.startswith("##"):
                continue
            if not line:
                continue
            lines.append(re.sub(r"\[(.*?)\]\([^)]+\)", r"\1", line))
            if len(lines) >= 2:
                break
        if lines:
            summary = re.sub(r"\*\*(.*?)\*\*", r"\1", lines[0]).strip()
            return summary
        return ""

    def _extract_description(self, text):
        summary = self._extract_summary(text)
        if summary:
            return summary
        return "Проєкт доступний для перегляду з папки Projects."

    def _extract_tags(self, text):
        tags = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line.startswith(("- ", "* ")):
                continue
            cleaned = re.sub(r"^[-*]\s+", "", line)
            cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
            cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
            cleaned = cleaned.replace("✅", "").strip()
            if cleaned:
                tags.append(cleaned)
            if len(tags) >= 4:
                break
        return tags

    def _guess_tags(self, project_dir):
        name = os.path.basename(project_dir).lower()
        tags = []
        if "game" in name or "play" in name or "гру" in name or "sus" in name:
            tags.append("гра")
        if "web" in name or "site" in name or "inc" in name or "emerald" in name:
            tags.append("веб")
        if not tags:
            tags.append("проєкт")
        return tags

    def _guess_icon(self, name, summary):
        lowered = name.lower()
        if "game" in lowered or "гра" in lowered or "sus" in lowered:
            return "🎮"
        if "emerald" in lowered:
            return "💎"
        if "pay" in lowered or "epay" in lowered:
            return "💳"
        if "yellow" in lowered or "display" in lowered:
            return "📺"
        if "house" in lowered or "flopper" in lowered:
            return "🏚️"
        if "board" in lowered:
            return "🖥️"
        if "web" in lowered or "site" in lowered:
            return "🌐"
        if "mobile" in lowered or "phone" in lowered:
            return "📱"
        return "📦"

    def _extract_html_title(self, project_dir):
        html_candidates = ["index.html", "public/index.html", "frontend/index.html", "jesus.html"]
        for rel_path in html_candidates:
            full_path = os.path.join(project_dir, rel_path)
            if not os.path.exists(full_path):
                continue
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as handle:
                    content = handle.read(20000)
                match = re.search(r"<title[^>]*>(.*?)</title>", content, flags=re.IGNORECASE | re.DOTALL)
                if match:
                    title = re.sub(r"<[^>]+>", "", match.group(1)).strip()
                    return title
            except Exception:
                continue
        return ""

    def _resolve_open_path(self, project_dir):
        name = os.path.basename(project_dir)
        candidates = ["public/index.html", "frontend/index.html", "index.html", "jesus.html", "ePhone.html", "epay.html"]
        for rel_path in candidates:
            full_path = os.path.join(project_dir, rel_path)
            if os.path.exists(full_path):
                return "/" + quote(name, safe="") + "/" + quote(rel_path.replace("\\", "/"), safe="/")
        return "/" + quote(name, safe="") + "/"

    def _send_json(self, status, data):
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
