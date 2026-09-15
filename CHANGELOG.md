# Changelog — Agente Fiscal RN

## [2.2.0] — 2026-09-14

### Adicionado
- **`watchdog.sh`** — script de vigilância que verifica a cada 1h se o robô já rodou hoje.
  - Critério: existência do arquivo `logs/relatorio_fiscal_YYYY-MM-DD.pdf`.
  - Se não encontrado, inicia `main.py` automaticamente.
  - Usa lock file para evitar execuções simultâneas.
  - Lê `TIMEZONE` do `.env` para operar no fuso correto.

- **`notify_falha.py`** — notificação por e-mail se o robô não rodou no dia.
  - Executa às 23h45 via cron.
  - Envia alerta HTML para todos os destinatários configurados em `EMAIL_DESTINATARIOS`.
  - Loga resultado em `logs/notify_falha.log`.

- **Variável `TIMEZONE`** no `.env` — permite configurar o fuso horário sem alterar o sistema.
  - Padrão: `America/Fortaleza`.
  - Usada pelo `watchdog.sh` e `notify_falha.py`.

### Alterado
- Crontab reorganizado:
  - `35 22 * * *` → execução principal do robô (`main.py`)
  - `0 * * * *`  → watchdog a cada 1h
  - `45 23 * * *` → notificação de falha (`notify_falha.py`)

### Crontab completo atualizado
```
CRON_TZ=America/Fortaleza
35 22 * * * cd /root/agente_fiscal && /root/agente_fiscal/venv/bin/python /root/agente_fiscal/main.py >> /root/agente_fiscal/logs/cron.log 2>&1
0 * * * * /root/agente_fiscal/watchdog.sh
45 23 * * * cd /root/agente_fiscal && /root/agente_fiscal/venv/bin/python /root/agente_fiscal/notify_falha.py
```
