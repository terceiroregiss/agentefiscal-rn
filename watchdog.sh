#!/bin/bash
# watchdog.sh — Agente Fiscal RN
# Verifica a cada 1h se o robô rodou hoje. Se não, inicia.
# Fuso horário lido do .env (TIMEZONE=America/Fortaleza)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
LOG_FILE="$SCRIPT_DIR/logs/watchdog.log"
PYTHON="$SCRIPT_DIR/venv/bin/python"
MAIN="$SCRIPT_DIR/main.py"

# Lê TIMEZONE do .env
if [ -f "$ENV_FILE" ]; then
    TIMEZONE=$(grep -E '^TIMEZONE=' "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
fi
TIMEZONE="${TIMEZONE:-America/Fortaleza}"
export TZ="$TIMEZONE"

TODAY=$(date +%Y-%m-%d)
PDF_FILE="$SCRIPT_DIR/logs/relatorio_fiscal_${TODAY}.pdf"
LOCK_FILE="$SCRIPT_DIR/logs/watchdog.lock"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Evita execução simultânea
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        log "Robô já em execução (PID $PID). Watchdog aguardando."
        exit 0
    else
        log "Lock file órfão encontrado. Removendo."
        rm -f "$LOCK_FILE"
    fi
fi

if [ -f "$PDF_FILE" ]; then
    log "Relatório do dia já existe: $PDF_FILE — nenhuma ação necessária."
    exit 0
fi

log "Relatório do dia NÃO encontrado. Iniciando robô..."
echo $$ > "$LOCK_FILE"

cd "$SCRIPT_DIR"
"$PYTHON" "$MAIN" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

rm -f "$LOCK_FILE"

if [ $EXIT_CODE -eq 0 ]; then
    log "Robô finalizado com sucesso (exit 0)."
else
    log "ERRO: Robô finalizou com exit code $EXIT_CODE."
fi

exit $EXIT_CODE
