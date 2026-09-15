# Deploy — Agente Fiscal RN v2.2.0

## 1. Copiar arquivos para a VPS

```bash
scp watchdog.sh notify_falha.py CHANGELOG.md root@177.136.230.16:~/agente_fiscal/
```

## 2. Dar permissão ao watchdog

```bash
ssh root@177.136.230.16 "chmod +x ~/agente_fiscal/watchdog.sh"
```

## 3. Adicionar TIMEZONE ao .env

```bash
ssh root@177.136.230.16 "echo 'TIMEZONE=America/Fortaleza' >> ~/agente_fiscal/.env"
```

## 4. Atualizar crontab (comando direto, sem nano)

```bash
ssh root@177.136.230.16 "cat > /tmp/cron_novo.txt << 'CRON'
@reboot nohup /root/agente_fiscal/venv/bin/python /root/agente_fiscal/dashboard.py > /tmp/dash.log 2>&1 &
*/5 * * * * /root/agente_fiscal/watchdog.sh
CRON_TZ=America/Fortaleza
35 22 * * * cd /root/agente_fiscal && /root/agente_fiscal/venv/bin/python /root/agente_fiscal/main.py >> /root/agente_fiscal/logs/cron.log 2>&1
0 * * * * /root/agente_fiscal/watchdog.sh
45 23 * * * cd /root/agente_fiscal && /root/agente_fiscal/venv/bin/python /root/agente_fiscal/notify_falha.py
CRON
crontab /tmp/cron_novo.txt && echo 'Crontab atualizado'"
```

## 5. Confirmar

```bash
ssh root@177.136.230.16 "crontab -l"
```

## 6. Commit no GitHub

```bash
git add watchdog.sh notify_falha.py CHANGELOG.md DEPLOY.md
git commit -m "feat: watchdog horário, notify_falha e suporte a TIMEZONE (#v2.2.0)"
git push origin main
```
