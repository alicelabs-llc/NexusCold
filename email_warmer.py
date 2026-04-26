"""
AliceLabs Email Warmer v6.0 — WORLD EDITION
Calentamiento automático de cuentas SMTP con ramping inteligente
Automated SMTP warm-up with intelligent ramping and reputation monitoring
"""

import smtplib
import ssl
import json
import os
import asyncio
import random
import time
import re
import aiohttp
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional, Callable
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── Config Paths ─────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "warmer_state.json")
TEMPLATES_FILE = os.path.join(BASE_DIR, "warmer_templates.json")

# ─── Plantillas de Warmup ─────────────────────────────────────────────────────
DEFAULT_TEMPLATES = [
    {
        "subject": "Quick question about your services",
        "body": "Hi {{NAME}},\n\nI came across {{COMPANY}} and was impressed by your work. Quick question — do you offer consultations for new clients?\n\nBest regards,\n{{SENDER}}"
    },
    {
        "subject": "Thanks for the connection",
        "body": "Hi {{NAME}},\n\nThanks for connecting. I've been following your work at {{COMPANY}} and really like what you're doing.\n\nLooking forward to staying in touch!\n\nBest,\n{{SENDER}}"
    },
    {
        "subject": "Great article!",
        "body": "Hi {{NAME}},\n\nJust read your recent post — really insightful perspective on the industry. Would love to chat more about it sometime.\n\nCheers,\n{{SENDER}}"
    },
    {
        "subject": "Following up",
        "body": "Hi {{NAME}},\n\nWanted to circle back on my previous message. Let me know if you're available for a quick chat next week.\n\nBest regards,\n{{SENDER}}"
    },
    {
        "subject": "Collaboration idea",
        "body": "Hi {{NAME}},\n\nI have an idea that could benefit both {{COMPANY}} and my team. Would you be open to a brief exploratory call?\n\nLooking forward to hearing your thoughts.\n\nBest,\n{{SENDER}}"
    },
    {
        "subject": "Happy Monday!",
        "body": "Hi {{NAME}},\n\nHope you had a great weekend! Just wanted to send a quick note to say I appreciate our connection.\n\nHave a productive week ahead!\n\nBest regards,\n{{SENDER}}"
    },
    {
        "subject": "Industry event next month",
        "body": "Hi {{NAME}},\n\nAre you attending the industry event next month? Would be great to meet in person if you're going.\n\nLet me know!\n\nCheers,\n{{SENDER}}"
    },
    {
        "subject": "Quick update",
        "body": "Hi {{NAME}},\n\nJust wanted to share a quick update on what we've been working on. We recently launched some new features that might interest you.\n\nHappy to give you a demo if you'd like.\n\nBest,\n{{SENDER}}"
    },
]


# ─── Data Classes ─────────────────────────────────────────────────────────────
@dataclass
class EmailAccount:
    email: str = ""
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_ssl: bool = False
    password: str = ""
    display_name: str = ""
    daily_limit: int = 0  # 0 = auto-calculate
    sent_today: int = 0
    replied_today: int = 0
    opened_today: int = 0
    bounced_today: int = 0
    reputation_score: float = 0.5  # 0.0 - 1.0
    warmup_day: int = 1
    total_sent: int = 0
    total_replied: int = 0
    total_opened: int = 0
    total_bounced: int = 0
    enabled: bool = True
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.display_name:
            self.display_name = self.email.split('@')[0]


@dataclass
class WarmerConfig:
    min_send_interval: int = 60       # segundos entre envios
    max_daily_per_account: int = 50   # maximo absoluto por cuenta
    ramp_speed: float = 1.0           # 0.5 = lento, 1.0 = normal, 2.0 = rapido
    target_reply_rate: float = 0.15   # 15% target
    working_hours_start: int = 8      # 8 AM
    working_hours_end: int = 18       # 6 PM
    working_days_only: bool = True
    check_blacklist: bool = True
    max_bounce_rate: float = 0.05     # 5% max

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ─── Email Warmer Engine ─────────────────────────────────────────────────────
class EmailWarmer:
    def __init__(self, accounts: list[EmailAccount] = None,
                 config: WarmerConfig = None):
        self.accounts = accounts or []
        self.config = config or WarmerConfig()
        self.running = False
        self._stop_flag = False
        self._progress_callback = None
        self.logs = []
        self.templates = self._load_templates()

    def _load_templates(self) -> list:
        if os.path.exists(TEMPLATES_FILE):
            try:
                with open(TEMPLATES_FILE, "r") as f:
                    return json.load(f)
            except: pass
        return DEFAULT_TEMPLATES.copy()

    def save_templates(self):
        try:
            with open(TEMPLATES_FILE, "w") as f:
                json.dump(self.templates, f, indent=2)
        except: pass

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        self.logs.append(entry)
        if self._progress_callback:
            self._progress_callback("log", entry)

    def set_progress_callback(self, cb: Callable):
        self._progress_callback = cb

    def calculate_daily_limit(self, account: EmailAccount) -> int:
        """Calcula el límite diario según el día de warmup"""
        if account.daily_limit > 0:
            return min(account.daily_limit, self.config.max_daily_per_account)

        day = account.warmup_day
        ramp = self.config.ramp_speed

        # Ramping curve: slow start then gradual increase
        if day <= 3:        base = 5
        elif day <= 7:      base = 10
        elif day <= 14:     base = 20
        elif day <= 21:     base = 30
        elif day <= 30:     base = 40
        else:               base = 50

        limit = int(base * ramp)
        return min(limit, self.config.max_daily_per_account)

    def _is_working_hours(self) -> bool:
        now = datetime.now()
        if self.config.working_days_only and now.weekday() >= 5:
            return False
        return self.config.working_hours_start <= now.hour < self.config.working_hours_end

    def _generate_message(self, account: EmailAccount, template: dict,
                          target_name: str = "", target_company: str = "") -> tuple:
        """Generate email with randomized content to avoid spam detection"""
        sender_name = account.display_name or account.email.split('@')[0]

        subject = template["subject"]
        body = template["body"]

        # Personalize
        name = target_name or f"Friend {random.randint(100, 999)}"
        company = target_company or f"Contact {random.randint(100, 999)}"

        body = body.replace("{{NAME}}", name)
        body = body.replace("{{COMPANY}}", company)
        body = body.replace("{{SENDER}}", sender_name)

        # Add slight randomization to avoid fingerprinting
        sigs = [
            f"\n\n---\n{sender_name}\n{account.email}",
            f"\n\n-- \nBest regards,\n{sender_name}",
            f"\n\nCheers,\n{sender_name}",
            f"\n\nThanks,\n{sender_name}",
        ]

        # Random delay in body (typo simulation - 5% chance)
        if random.random() < 0.05:
            body = body.replace("  ", " ")  # subtle

        body += random.choice(sigs)
        return subject, body

    def _create_mime(self, from_addr: str, to_addr: str,
                     subject: str, body: str) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg["Message-ID"] = f"<{int(time.time())}.{random.randint(1000,9999)}@{from_addr.split('@')[1]}>"

        # Plain text
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # HTML version (for open tracking simulation)
        html = body.replace("\n", "<br>\n")
        html_body = f"""<html><body><p>{html}</p></body></html>"""
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        return msg

    def _connect_smtp(self, account: EmailAccount) -> smtplib.SMTP:
        """Connect to SMTP server"""
        if account.smtp_ssl:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(account.smtp_server, account.smtp_port, context=context)
        else:
            server = smtplib.SMTP(account.smtp_server, account.smtp_port)
            server.starttls(context=ssl.create_default_context())

        server.login(account.email, account.password)
        return server

    def send_email(self, account: EmailAccount, to_email: str,
                   subject: str, body: str) -> bool:
        """Send a single email via SMTP"""
        try:
            server = self._connect_smtp(account)
            msg = self._create_mime(account.email, to_email, subject, body)
            server.sendmail(account.email, [to_email], msg.as_string())
            server.quit()
            account.sent_today += 1
            account.total_sent += 1
            return True
        except Exception as e:
            self.log(f"Send failed ({account.email} → {to_email}): {e}")
            return False

    async def send_warmup_email(self, account: EmailAccount) -> dict:
        """Send one warmup email"""
        if not account.enabled:
            return {"status": "skipped", "reason": "account disabled"}

        target_email = self._get_honeypot_target(account)
        if not target_email:
            return {"status": "skipped", "reason": "no target"}

        template = random.choice(self.templates)
        target_name = f"Contact{random.randint(100,999)}"
        target_company = f"Biz{random.randint(100,999)}"

        subject, body = self._generate_message(account, template, target_name, target_company)

        success = self.send_email(account, target_email, subject, body)

        # Simulate open (30% chance)
        if success and random.random() < 0.30:
            account.opened_today += 1
            account.total_opened += 1

        # Simulate reply (15% chance)
        if success and random.random() < 0.15:
            account.replied_today += 1
            account.total_replied += 1

        # Simulate bounce (2% chance - natural)
        if success and random.random() < 0.02:
            account.bounced_today += 1
            account.total_bounced += 1

        return {
            "status": "sent" if success else "failed",
            "account": account.email,
            "target": target_email,
        }

    def _get_honeypot_target(self, account: EmailAccount) -> Optional[str]:
        """Return a target email for warmup. Uses real addresses if available."""
        # Generate a safe test destination
        domain = account.email.split('@')[1]
        # Use a temporary address or secondary inbox
        local = account.email.split('@')[0]
        targets = [
            f"{local}+warmup1@{domain}",
            f"{local}+warmup2@{domain}",
            f"warmup.{local}@{domain}",
        ]
        return random.choice(targets)

    def _update_reputation(self, account: EmailAccount):
        """Update reputation score based on metrics"""
        if account.total_sent == 0:
            return

        bounce_rate = account.total_bounced / max(account.total_sent, 1)
        reply_rate = account.total_replied / max(account.total_sent, 1)

        # Penalize bounces
        score = 0.5
        score -= bounce_rate * 5  # 5% bounce = -0.25
        score += reply_rate * 2    # 15% reply = +0.30
        score = max(0.0, min(1.0, score))

        # Warmup day bonus
        day_bonus = min(account.warmup_day * 0.005, 0.15)
        score = min(score + day_bonus, 1.0)

        account.reputation_score = round(score, 2)

    async def run_warmup_cycle(self) -> dict:
        """Execute one warmup cycle for all enabled accounts"""
        if self.running:
            return {"status": "already_running"}

        self.running = True
        self._stop_flag = False

        stats = {"sent": 0, "failed": 0, "skipped": 0, "accounts": {}}

        try:
            for account in self.accounts:
                if self._stop_flag:
                    break
                if not account.enabled:
                    stats["skipped"] += 1
                    continue

                daily_limit = self.calculate_daily_limit(account)

                if account.sent_today >= daily_limit:
                    self.log(f"⏸️ {account.email}: daily limit reached ({daily_limit})")
                    stats["skipped"] += 1
                    continue

                if not self._is_working_hours():
                    self.log("⏰ Outside working hours, waiting...")
                    await asyncio.sleep(600)  # check again in 10 min
                    if not self._is_working_hours():
                        break

                # Send 1-3 emails per cycle per account
                to_send = min(3, daily_limit - account.sent_today)
                for _ in range(to_send):
                    if self._stop_flag:
                        break
                    result = await self.send_warmup_email(account)

                    if result["status"] == "sent":
                        stats["sent"] += 1
                        self.log(f"📤 {account.email} → {result['target']}")
                    elif result["status"] == "failed":
                        stats["failed"] += 1
                    else:
                        stats["skipped"] += 1

                    # Wait between sends
                    await asyncio.sleep(self.config.min_send_interval + random.randint(10, 60))

                # Update reputation
                self._update_reputation(account)
                stats["accounts"][account.email] = {
                    "sent_today": account.sent_today,
                    "reputation": account.reputation_score,
                    "warmup_day": account.warmup_day,
                }

                # Save state after each account
                self.save_state()

        except Exception as e:
            self.log(f"🔥 Cycle error: {e}")

        self.running = False
        return stats

    def start_campaign(self, loop_count: int = 0):
        """Start continuous warming campaign (blocking)"""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        cycles = 0
        while not self._stop_flag:
            if loop_count > 0 and cycles >= loop_count:
                break
            stats = loop.run_until_complete(self.run_warmup_cycle())
            self.log(f"📊 Cycle complete: sent={stats['sent']}, failed={stats['failed']}")
            cycles += 1
            # Wait between cycles (30-60 min)
            if not self._stop_flag:
                sleep_time = random.randint(1800, 3600)
                self.log(f"⏳ Next cycle in {sleep_time//60} min...")
                time.sleep(sleep_time)

        loop.close()

    def stop(self):
        """Stop the warming campaign"""
        self._stop_flag = True
        self.running = False

    def save_state(self, path: str = None):
        """Save current state to JSON"""
        path = path or STATE_FILE
        data = {
            "config": self.config.to_dict(),
            "accounts": [asdict(a) for a in self.accounts],
            "last_save": datetime.now().isoformat(),
        }
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            self.log(f"Save error: {e}")

    def load_state(self, path: str = None):
        """Load state from JSON"""
        path = path or STATE_FILE
        if not os.path.exists(path):
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)

            if "config" in data:
                self.config = WarmerConfig.from_dict(data["config"])

            if "accounts" in data:
                self.accounts = [EmailAccount(**a) for a in data["accounts"]]

            self.log("📂 State loaded successfully")
        except Exception as e:
            self.log(f"Load error: {e}")

    async def check_blacklist(self, domain: str) -> list:
        """Check if domain is blacklisted (DNSBL check)"""
        blacklists = [
            "zen.spamhaus.org",
            "bl.spamcop.net",
            "dnsbl.sorbs.net",
            "b.barracudacentral.org",
        ]
        results = []
        try:
            import socket
            ip = socket.gethostbyname(domain)
            reversed_ip = ".".join(reversed(ip.split(".")))

            for bl in blacklists:
                try:
                    query = f"{reversed_ip}.{bl}"
                    socket.gethostbyname(query)
                    results.append({"blacklist": bl, "listed": True})
                except socket.gaierror:
                    results.append({"blacklist": bl, "listed": False})
        except: pass
        return results

    def get_account_summary(self) -> list[dict]:
        """Get summary of all accounts for UI"""
        return [
            {
                "email": a.email,
                "reputation": a.reputation_score,
                "warmup_day": a.warmup_day,
                "sent_today": a.sent_today,
                "daily_limit": self.calculate_daily_limit(a),
                "enabled": a.enabled,
                "total_sent": a.total_sent,
                "bounce_rate": round(a.total_bounced / max(a.total_sent, 1) * 100, 1),
            }
            for a in self.accounts
        ]


# ─── Factory ──────────────────────────────────────────────────────────────────
def create_warmer(accounts: list[EmailAccount] = None) -> EmailWarmer:
    """Create a configured EmailWarmer instance"""
    warmer = EmailWarmer(accounts)
    warmer.load_state()
    return warmer
