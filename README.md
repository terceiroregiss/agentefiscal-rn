# 🤖 Agente Fiscal RN

Robô Python/Playwright que automatiza a conferência de obrigações fiscais de múltiplas empresas na plataforma **UVT SEFAZ-RN** e envia um **relatório PDF diário por e-mail**.

---

## 📋 O que ele faz

1. Acessa a UVT SEFAZ-RN (`uvt.sefaz.rn.gov.br`) com login único
2. Resolve o captcha de imagem automaticamente via **2Captcha**
3. Varre todas as empresas vinculadas ao login (até 176+)
4. Para cada empresa: acessa modal → clica no link da empresa → acessa **$ Débitos** → acessa **Extrato Fiscal** → captura o status (`OK` ou `CRITICADO`)
5. **Compara com o histórico anterior** e indica se a situação piorou ou melhorou
6. Gera um **relatório PDF** separado por OK / CRITICADO
7. Envia o relatório por **e-mail SMTP** para os destinatários configurados
8. Executa automaticamente todo dia via **cron job**

---

## 🗂️ Estrutura do projeto

```
agentefiscal-rn/
├── main.py              # Ponto de entrada — orquestra todo o fluxo
├── captcha.py           # Integração com 2Captcha para resolução de captcha
├── report.py            # Geração do relatório PDF com ReportLab
├── requirements.txt     # Dependências Python
├── .env                 # Variáveis de ambiente (não versionado)
├── .gitignore
└── erro.png             # Imagem de debug capturada em caso de erro
```

---

## ⚙️ Requisitos

- Python 3.10+
- Conta ativa no [2Captcha](https://2captcha.com) com saldo
- Servidor Linux com acesso SMTP (testado em Ubuntu 24.04)
- Acesso à UVT SEFAZ-RN com empresas vinculadas

### Dependências Python

```
playwright==1.44.0
capsolver==1.0.0
python-dotenv
reportlab
Pillow
```

Instale tudo com:

```bash
pip install -r requirements.txt
playwright install chromium
```

---

## 🚀 Como usar

### 1. Clone o repositório

```bash
git clone https://github.com/terceiroregis/agentefiscal-rn.git
cd agentefiscal-rn
```

### 2. Crie o ambiente virtual

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure as variáveis de ambiente

Copie o modelo e preencha com suas credenciais:

```bash
cp .env.example .env
```

```env
# Credenciais UVT SEFAZ-RN
UVT_LOGIN=seu_login
UVT_SENHA=sua_senha

# 2Captcha
CAPTCHA_API_KEY=sua_chave_2captcha

# SMTP
SMTP_HOST=mail.seudominio.com.br
SMTP_PORT=587
SMTP_USER=remetente@seudominio.com.br
SMTP_PASS=sua_senha_smtp

# Destinatários (separados por vírgula)
EMAIL_DESTINATARIOS=email1@exemplo.com,email2@exemplo.com
```

### 4. Execute manualmente

```bash
python main.py
```

---

## ⏰ Agendamento automático (cron)

Para rodar todo dia às 22h30:

```bash
crontab -e
```

Adicione a linha:

```cron
30 22 * * * /root/agente_fiscal/venv/bin/python /root/agente_fiscal/main.py >> /root/agente_fiscal/logs/cron.log 2>&1
```

---

## 📊 Exemplo de resultado

```
Varredura concluída em 2291s (~38 min)
Total de empresas: 176
✅ OK:         108
⚠️  CRITICADO:  68
❌ ERRO:         0

Relatório enviado para 5 destinatários.
```

O relatório PDF inclui:
- Lista de empresas **OK** (situação regular)
- Lista de empresas **CRITICADO** (com débitos ou pendências)
- Indicação de **melhora/piora** em relação à execução anterior

---

## 🏗️ Stack

| Componente | Tecnologia |
|---|---|
| Automação web | Python + Playwright (Chromium headless) |
| Resolução de captcha | 2Captcha |
| Geração de PDF | ReportLab |
| Envio de e-mail | SMTP via cPanel |
| Agendamento | Linux cron |

---

## 🔒 Segurança

- O arquivo `.env` **não é versionado** (está no `.gitignore`)
- Nunca commite credenciais no repositório
- Recomenda-se criar um usuário UVT com permissão somente de leitura para uso do robô

---

## 👤 Autor

**Terceiro Régis** — [terceiroregis.com.br](https://terceiroregis.com.br)  
Full Stack Developer & AI Specialist | CTO @ BodePay & InforTech

---

## 📄 Licença

Uso privado. Todos os direitos reservados.
