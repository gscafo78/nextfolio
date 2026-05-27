import asyncio
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import partial

from app.core.config import settings


def _send_sync(to: str, subject: str, html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.EMAILS_FROM
    msg["To"] = to
    msg.attach(MIMEText(html, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAILS_FROM, to, msg.as_string())


async def send_email(to: str, subject: str, html: str) -> None:
    if not settings.email_configured:
        raise RuntimeError("Email non configurata (SMTP_HOST, SMTP_USER, EMAILS_FROM mancanti)")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, partial(_send_sync, to, subject, html))


# ── Template ──────────────────────────────────────────────────────────────────

def _base(title: str, body: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="it">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body {{ margin:0; padding:0; background:#f4f6f8; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
  .wrap {{ max-width:560px; margin:32px auto; background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,.08); }}
  .header {{ background:#0f172a; padding:28px 32px; }}
  .header h1 {{ margin:0; color:#fff; font-size:20px; font-weight:700; letter-spacing:-.3px; }}
  .header span {{ color:#6ee7b7; }}
  .body {{ padding:32px; color:#374151; font-size:15px; line-height:1.6; }}
  .body h2 {{ margin:0 0 16px; font-size:18px; color:#111827; }}
  .btn {{ display:inline-block; margin:24px 0 8px; padding:13px 28px; background:#10b981; color:#fff !important; text-decoration:none; border-radius:8px; font-weight:600; font-size:15px; }}
  .note {{ margin-top:20px; font-size:13px; color:#9ca3af; }}
  .footer {{ padding:20px 32px; background:#f9fafb; font-size:12px; color:#9ca3af; border-top:1px solid #f3f4f6; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="header"><h1>Next<span>Folio</span></h1></div>
  <div class="body">
    <h2>{title}</h2>
    {body}
  </div>
  <div class="footer">Nextfolio — gestione portafoglio investimenti personale</div>
</div>
</body>
</html>
"""


async def send_password_reset(to: str, token: str) -> None:
    url = f"{settings.APP_URL}/reset-password?token={token}"
    html = _base(
        "Reimposta la tua password",
        f"""
        <p>Hai richiesto il reset della password per il tuo account Nextfolio.</p>
        <p>Clicca il pulsante qui sotto per scegliere una nuova password. Il link è valido per <strong>1 ora</strong>.</p>
        <a href="{url}" class="btn">Reimposta password</a>
        <p class="note">Se non hai richiesto tu questo reset, ignora questa email.</p>
        <p class="note">Link: <a href="{url}">{url}</a></p>
        """,
    )
    await send_email(to, "Reimposta la tua password — Nextfolio", html)


async def send_welcome(to: str, name: str, temp_password: str) -> None:
    url = settings.APP_URL
    html = _base(
        f"Benvenuto, {name}!",
        f"""
        <p>Il tuo account Nextfolio è stato creato dall'amministratore.</p>
        <p><strong>Email:</strong> {to}<br>
        <strong>Password temporanea:</strong> <code style="background:#f3f4f6;padding:2px 6px;border-radius:4px;font-size:14px">{temp_password}</code></p>
        <a href="{url}" class="btn">Accedi a Nextfolio</a>
        <p class="note">Ti consigliamo di cambiare la password dopo il primo accesso.</p>
        """,
    )
    await send_email(to, "Benvenuto su Nextfolio!", html)


async def send_test(to: str) -> None:
    html = _base(
        "Email di test",
        """
        <p>Questa è un'email di test inviata da Nextfolio per verificare che la configurazione SMTP sia corretta.</p>
        <p style="color:#10b981;font-weight:600;">✓ La configurazione email funziona correttamente.</p>
        """,
    )
    await send_email(to, "Test email — Nextfolio", html)
