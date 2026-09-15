#!/usr/bin/env python3
# notify_falha.py — Agente Fiscal RN
# Roda às 23h45. Se o relatório do dia não existir, envia e-mail de alerta.

import os
import smtplib
import logging
from datetime import datetime
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# Fuso horário do .env
timezone = os.getenv("TIMEZONE", "America/Fortaleza")
os.environ["TZ"] = timezone

logging.basicConfig(
    filename=BASE_DIR / "logs" / "notify_falha.log",
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def relatorio_existe() -> bool:
    today = datetime.now().strftime("%Y-%m-%d")
    pdf = BASE_DIR / "logs" / f"relatorio_fiscal_{today}.pdf"
    return pdf.exists()

def enviar_alerta():
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    email_from = os.getenv("EMAIL_FROM", smtp_user)
    destinatarios_raw = os.getenv("EMAIL_DESTINATARIOS", "")
    destinatarios = [e.strip() for e in destinatarios_raw.split(",") if e.strip()]

    hoje = datetime.now().strftime("%d/%m/%Y")
    hora = datetime.now().strftime("%H:%M")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"⚠️ AGENTE FISCAL — Robô NÃO executou em {hoje}"
    msg["From"] = email_from
    msg["To"] = ", ".join(destinatarios)

    corpo_texto = f"""
ALERTA — Agente Fiscal RN

O robô fiscal NÃO foi executado hoje ({hoje}).
Verificação realizada às {hora} ({timezone}).

Nenhum relatório encontrado para a data de hoje.

Ação recomendada:
  1. Conecte na VPS: ssh root@177.136.230.16
  2. Rode manualmente: cd ~/agente_fiscal && source venv/bin/activate && python main.py

Este é um e-mail automático do sistema Agente Fiscal RN.
"""

    corpo_html = f"""
<html><body style="font-family:Arial,sans-serif;color:#222;max-width:600px;margin:auto">
  <div style="background:#b91c1c;color:#fff;padding:16px 24px;border-radius:8px 8px 0 0">
    <h2 style="margin:0">⚠️ Agente Fiscal RN — Falha de Execução</h2>
  </div>
  <div style="border:1px solid #e5e7eb;border-top:none;padding:24px;border-radius:0 0 8px 8px">
    <p>O robô fiscal <strong>não foi executado</strong> hoje (<strong>{hoje}</strong>).</p>
    <p>Verificação realizada às <strong>{hora}</strong> — fuso: {timezone}.</p>
    <p>Nenhum arquivo <code>relatorio_fiscal_{datetime.now().strftime('%Y-%m-%d')}.pdf</code> encontrado.</p>
    <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0">
    <p><strong>Ação recomendada:</strong></p>
    <ol>
      <li>Conecte na VPS: <code>ssh root@177.136.230.16</code></li>
      <li>Execute manualmente:<br>
        <code>cd ~/agente_fiscal && source venv/bin/activate && python main.py</code>
      </li>
    </ol>
    <p style="color:#6b7280;font-size:12px;margin-top:24px">
      E-mail automático — Agente Fiscal RN | {hora} {timezone}
    </p>
  </div>
</body></html>
"""

    msg.attach(MIMEText(corpo_texto, "plain"))
    msg.attach(MIMEText(corpo_html, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(email_from, destinatarios, msg.as_string())
        logging.info(f"Alerta enviado para: {', '.join(destinatarios)}")
    except Exception as e:
        logging.error(f"Falha ao enviar alerta: {e}")
        raise

def main():
    logging.info("Verificando se robô executou hoje...")
    if relatorio_existe():
        logging.info("Relatório encontrado. Nenhum alerta necessário.")
        return
    logging.warning("Relatório NÃO encontrado. Enviando alerta por e-mail...")
    enviar_alerta()

if __name__ == "__main__":
    main()
