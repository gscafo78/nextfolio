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
    loop = asyncio.get_running_loop()
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


async def send_verification_code(to: str, code: str, name: str) -> None:
    html = _base(
        f"Verifica il tuo account, {name}!",
        f"""
        <p>Hai richiesto la registrazione su Nextfolio. Inserisci il codice qui sotto per completare la verifica.</p>
        <div style="margin:28px 0;text-align:center">
          <span style="display:inline-block;background:#f0fdf4;border:2px solid #10b981;border-radius:12px;
                       padding:16px 32px;font-size:36px;font-weight:700;letter-spacing:12px;color:#065f46">
            {code}
          </span>
        </div>
        <p>Il codice è valido per <strong>15 minuti</strong>.</p>
        <p class="note">Se non hai richiesto tu questa registrazione, ignora questa email.</p>
        """,
    )
    await send_email(to, "Codice di verifica — Nextfolio", html)


async def send_price_alert(
    to: str,
    asset_name: str,
    asset_symbol: str,
    alert_type: str,
    threshold: float,
    current_value: float,
    is_pct: bool,
) -> None:
    fmt = lambda v: f"{v:+.2f}%" if is_pct else f"€ {v:.4f}"
    label_map = {
        "PRICE_ABOVE":    "Prezzo sopra soglia",
        "PRICE_BELOW":    "Prezzo sotto soglia",
        "CHANGE_PCT_UP":  "Variazione giornaliera positiva oltre soglia",
        "CHANGE_PCT_DOWN": "Variazione giornaliera negativa oltre soglia",
    }
    label = label_map.get(alert_type, alert_type)
    url = f"{settings.APP_URL}/alert"
    html = _base(
        f"Alert scattato: {asset_symbol}",
        f"""
        <p>Il tuo alert su <strong>{asset_name}</strong> ({asset_symbol}) è appena scattato.</p>
        <table style="width:100%;border-collapse:collapse;margin:20px 0;font-size:14px">
          <tr>
            <td style="padding:8px 0;color:#6b7280;border-bottom:1px solid #f3f4f6">Condizione</td>
            <td style="padding:8px 0;font-weight:600;text-align:right;border-bottom:1px solid #f3f4f6">{label}</td>
          </tr>
          <tr>
            <td style="padding:8px 0;color:#6b7280;border-bottom:1px solid #f3f4f6">Soglia impostata</td>
            <td style="padding:8px 0;font-weight:600;text-align:right;border-bottom:1px solid #f3f4f6">{fmt(threshold)}</td>
          </tr>
          <tr>
            <td style="padding:8px 0;color:#6b7280">Valore attuale</td>
            <td style="padding:8px 0;font-weight:700;font-size:18px;text-align:right;color:#111827">{fmt(current_value)}</td>
          </tr>
        </table>
        <a href="{url}" class="btn">Gestisci alert</a>
        <p class="note">Questo alert non si riattiverà per le prossime 4 ore.</p>
        """,
    )
    await send_email(to, f"Alert Nextfolio: {asset_symbol} — {label}", html)


async def send_bond_sell_signal(to: str, asset_name: str, isin: str | None, asset_id: int, ev: dict) -> None:
    """Avviso: vendere l'obbligazione ora rende più che tenerla fino a scadenza (valori netti)."""
    eur = lambda v: f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")  # noqa: E731
    pct = f"{ev['tax_rate'] * 100:.1f}".replace(".0", "").replace(".", ",")
    row = lambda label, val, bold=False: (  # noqa: E731
        f'<tr><td style="padding:7px 0;color:#6b7280;border-bottom:1px solid #f3f4f6">{label}</td>'
        f'<td style="padding:7px 0;text-align:right;border-bottom:1px solid #f3f4f6;{"font-weight:700;" if bold else ""}">{val}</td></tr>'
    )
    maturity = ev.get("maturity_date") or ""
    url = f"{settings.APP_URL}/transazioni"
    html = _base(
        f"Conviene vendere: {asset_name}",
        f"""
        <p>Con il prezzo di oggi, <strong>vendere {asset_name}</strong>{f" ({isin})" if isin else ""} rende
        <strong>{eur(ev['advantage_eur'])}</strong> in più (al netto delle imposte, {pct}%) rispetto a tenerlo fino a scadenza
        ({maturity}) incassando il rimborso e le cedole rimanenti.</p>
        <table style="width:100%;border-collapse:collapse;margin:20px 0;font-size:14px">
          {row("Prezzo attuale (corso secco)", f"{ev['price']:.3f}")}
          {row("Prezzo di pareggio", f"{ev['break_even_price']:.3f}" if ev.get('break_even_price') is not None else "—")}
          {row("Costo medio di carico", f"{ev['avg_cost']:.3f}")}
          {row(f"Vendi ora (ricavo netto, incluso rateo)", eur(ev['sell_net_eur']))}
          {row(f"Tieni a scadenza (rimborso + {ev['future_coupons']} cedole nette)", eur(ev['hold_net_eur']))}
          {row("Vantaggio di vendere", eur(ev['advantage_eur']), True)}
          {row("Cedole già incassate (nette)", eur(ev['collected_coupons_net_eur']))}
          {row("Guadagno totale se vendi", eur(ev['total_gain_sell_eur']))}
          {row("Guadagno totale se tieni", eur(ev['total_gain_hold_eur']))}
        </table>
        <a href="{url}" class="btn">Apri Nextfolio</a>
        <p class="note">Confronto indicativo: nessuna attualizzazione né commissione di vendita; non valuta come reinvestiresti
        il ricavato. Riceverai un nuovo avviso solo se la convenienza rientra e poi si ripresenta.</p>
        """,
    )
    await send_email(to, f"Nextfolio: conviene vendere {asset_name}", html)


async def send_test(to: str) -> None:
    html = _base(
        "Email di test",
        """
        <p>Questa è un'email di test inviata da Nextfolio per verificare che la configurazione SMTP sia corretta.</p>
        <p style="color:#10b981;font-weight:600;">✓ La configurazione email funziona correttamente.</p>
        """,
    )
    await send_email(to, "Test email — Nextfolio", html)
