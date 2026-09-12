import os, json, smtplib, glob
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Dict, Optional
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST      = os.getenv("SMTP_HOST","")
SMTP_PORT      = int(os.getenv("SMTP_PORT","587"))
SMTP_USER      = os.getenv("SMTP_USER","")
SMTP_PASS      = os.getenv("SMTP_PASS","")
SMTP_FROM      = os.getenv("SMTP_FROM", SMTP_USER)
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME","Agente Fiscal RN")
EMAIL_DEST_RAW = os.getenv("EMAIL_DESTINATARIOS","")
LOG_DIR        = os.getenv("LOG_DIR", os.path.expanduser("~/agente_fiscal/logs"))
DESTINATARIOS  = [e.strip() for e in EMAIL_DEST_RAW.split(",") if e.strip()]

COR_VERDE    = colors.HexColor("#1a7f37")
COR_VERMELHO = colors.HexColor("#c0392b")
COR_LARANJA  = colors.HexColor("#e67e22")
COR_AZUL     = colors.HexColor("#2980b9")
COR_CINZA    = colors.HexColor("#555555")
COR_HEADER   = colors.HexColor("#1a3a5c")
COR_ZEBRA    = colors.HexColor("#f0f4f8")


# ─────────────────────────────────────────────
# HISTÓRICO E COMPARAÇÃO
# ─────────────────────────────────────────────

def salvar_log(resultados: List[Dict]) -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, f"relatorio_{datetime.now().strftime('%Y-%m-%d')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print(f"[log] Salvo em {path}")
    return path


def carregar_historico_anterior() -> Optional[List[Dict]]:
    """Carrega o JSON do dia anterior mais recente (ignora o de hoje)."""
    hoje = datetime.now().strftime("%Y-%m-%d")
    padrao = os.path.join(LOG_DIR, "relatorio_*.json")
    arquivos = sorted(glob.glob(padrao), reverse=True)
    for arq in arquivos:
        nome = os.path.basename(arq)
        data = nome.replace("relatorio_", "").replace(".json", "")
        if data != hoje:
            try:
                with open(arq, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                print(f"[historico] Carregado: {arq}")
                return dados, data
            except Exception as e:
                print(f"[historico] Erro ao ler {arq}: {e}")
    print("[historico] Nenhum relatório anterior encontrado.")
    return None, None


def comparar_resultados(atual: List[Dict], anterior: List[Dict]) -> Dict:
    """
    Retorna dict com:
      - piorou:   OK → CRITICADO
      - melhorou: CRITICADO → OK
      - novo:     empresa que não existia antes
      - sumiu:    empresa que sumiu
    """
    map_atual    = {r["cnpj"]: r for r in atual}
    map_anterior = {r["cnpj"]: r for r in anterior}

    piorou   = []
    melhorou = []
    novo     = []
    sumiu    = []

    for cnpj, r in map_atual.items():
        if cnpj not in map_anterior:
            novo.append(r)
        else:
            ant = map_anterior[cnpj]
            if ant["status"] == "OK" and r["status"] == "CRITICADO":
                piorou.append(r)
            elif ant["status"] == "CRITICADO" and r["status"] == "OK":
                melhorou.append(r)

    for cnpj, r in map_anterior.items():
        if cnpj not in map_atual:
            sumiu.append(r)

    return {
        "piorou":   piorou,
        "melhorou": melhorou,
        "novo":     novo,
        "sumiu":    sumiu,
    }


# ─────────────────────────────────────────────
# HELPERS PDF
# ─────────────────────────────────────────────

def _header_secao(story, texto, cor):
    t = Table([[texto]], colWidths=[17*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), cor),
        ("TEXTCOLOR",    (0,0), (-1,-1), colors.white),
        ("FONTNAME",     (0,0), (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 12),
        ("TOPPADDING",   (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,0), (-1,-1), 6),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.2*cm))


def _tabela(lista, cor):
    dados = [["Razão Social", "CNPJ", "IE"]]
    for r in lista:
        dados.append([r["nome"], r["cnpj"], r.get("ie", "")])
    t = Table(dados, colWidths=[9*cm, 5*cm, 3*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), cor),
        ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 9),
        ("FONTNAME",     (0,1), (-1,-1), "Helvetica"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, COR_ZEBRA]),
        ("GRID",         (0,0), (-1,-1), 0.3, colors.HexColor("#cccccc")),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
    ]))
    return t


def _tabela_variacao(lista, cor_seta, seta):
    """Tabela para seção de variações — inclui coluna de ícone."""
    dados = [[seta + " Variação", "Razão Social", "CNPJ"]]
    for r in lista:
        dados.append([seta, r["nome"], r["cnpj"]])
    t = Table(dados, colWidths=[1.2*cm, 11.3*cm, 4.5*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), cor_seta),
        ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 9),
        ("FONTNAME",     (0,1), (-1,-1), "Helvetica"),
        ("TEXTCOLOR",    (0,1), (0,-1), cor_seta),
        ("FONTNAME",     (0,1), (0,-1), "Helvetica-Bold"),
        ("ALIGN",        (0,0), (0,-1), "CENTER"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, COR_ZEBRA]),
        ("GRID",         (0,0), (-1,-1), 0.3, colors.HexColor("#cccccc")),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
    ]))
    return t


# ─────────────────────────────────────────────
# GERAR PDF
# ─────────────────────────────────────────────

def gerar_pdf(resultados: List[Dict], comparacao: Optional[Dict] = None, data_anterior: Optional[str] = None) -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    agora  = datetime.now().strftime("%d/%m/%Y %H:%M")
    path   = os.path.join(LOG_DIR, f"relatorio_fiscal_{datetime.now().strftime('%Y-%m-%d')}.pdf")
    ok_l   = [r for r in resultados if r["status"] == "OK"]
    crit_l = [r for r in resultados if r["status"] == "CRITICADO"]
    erro_l = [r for r in resultados if r["status"] == "ERRO"]

    doc   = SimpleDocTemplate(path, pagesize=A4,
                              leftMargin=2*cm, rightMargin=2*cm,
                              topMargin=2*cm, bottomMargin=2*cm)
    story = []

    # Cabeçalho
    story.append(Paragraph("AGENTE FISCAL — SEFAZ-RN",
                            ParagraphStyle("t", fontSize=16, fontName="Helvetica-Bold",
                                           textColor=COR_HEADER, spaceAfter=4)))
    story.append(Paragraph(f"Relatório de Situação Fiscal — {agora}",
                            ParagraphStyle("s", fontSize=10, fontName="Helvetica",
                                           textColor=COR_CINZA, spaceAfter=12)))
    story.append(HRFlowable(width="100%", thickness=1, color=COR_HEADER))
    story.append(Spacer(1, 0.4*cm))

    # Resumo geral
    resumo = Table([
        ["Total",      str(len(resultados))],
        ["Fiscal OK",  str(len(ok_l))],
        ["Criticado",  str(len(crit_l))],
        ["Erro",       str(len(erro_l))],
    ], colWidths=[9*cm, 3*cm])
    resumo.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",  (0,0), (-1,-1), 10),
        ("FONTNAME",  (0,0), (0,-1),  "Helvetica-Bold"),
        ("TEXTCOLOR", (0,1), (-1,1),  COR_VERDE),
        ("TEXTCOLOR", (0,2), (-1,2),  COR_VERMELHO),
        ("TEXTCOLOR", (0,3), (-1,3),  colors.orange),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.white, COR_ZEBRA]),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
        ("TOPPADDING",     (0,0), (-1,-1), 5),
    ]))
    story.append(resumo)
    story.append(Spacer(1, 0.6*cm))

    # ── SEÇÃO DE VARIAÇÕES (novo) ──
    if comparacao and data_anterior:
        piorou   = comparacao.get("piorou",   [])
        melhorou = comparacao.get("melhorou", [])
        novo     = comparacao.get("novo",     [])
        sumiu    = comparacao.get("sumiu",    [])

        tem_variacao = piorou or melhorou or novo or sumiu

        # Cabeçalho da seção
        _header_secao(story, f"VARIAÇÕES EM RELAÇÃO A {data_anterior}", COR_AZUL)

        if not tem_variacao:
            story.append(Paragraph("Nenhuma variação de status detectada.",
                                   ParagraphStyle("nv", fontSize=10, fontName="Helvetica",
                                                  textColor=COR_CINZA, spaceAfter=6)))
        else:
            # Resumo das variações
            resumo_var = Table([
                ["Pioraram (OK → CRITICADO)",   str(len(piorou))],
                ["Melhoraram (CRITICADO → OK)", str(len(melhorou))],
                ["Novas empresas",              str(len(novo))],
                ["Removidas",                   str(len(sumiu))],
            ], colWidths=[9*cm, 3*cm])
            resumo_var.setStyle(TableStyle([
                ("FONTNAME",  (0,0), (-1,-1), "Helvetica"),
                ("FONTSIZE",  (0,0), (-1,-1), 10),
                ("FONTNAME",  (0,0), (0,-1),  "Helvetica-Bold"),
                ("TEXTCOLOR", (0,0), (-1,0),  COR_VERMELHO),
                ("TEXTCOLOR", (0,1), (-1,1),  COR_VERDE),
                ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.white, COR_ZEBRA]),
                ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
                ("TOPPADDING",     (0,0), (-1,-1), 5),
            ]))
            story.append(resumo_var)
            story.append(Spacer(1, 0.4*cm))

            if piorou:
                story.append(Paragraph("Pioraram — OK → CRITICADO",
                                       ParagraphStyle("ph", fontSize=10, fontName="Helvetica-Bold",
                                                      textColor=COR_VERMELHO, spaceAfter=4)))
                story.append(_tabela_variacao(piorou, COR_VERMELHO, "▼"))
                story.append(Spacer(1, 0.3*cm))

            if melhorou:
                story.append(Paragraph("Melhoraram — CRITICADO → OK",
                                       ParagraphStyle("mh", fontSize=10, fontName="Helvetica-Bold",
                                                      textColor=COR_VERDE, spaceAfter=4)))
                story.append(_tabela_variacao(melhorou, COR_VERDE, "▲"))
                story.append(Spacer(1, 0.3*cm))

            if novo:
                story.append(Paragraph("Novas empresas detectadas",
                                       ParagraphStyle("nh", fontSize=10, fontName="Helvetica-Bold",
                                                      textColor=COR_AZUL, spaceAfter=4)))
                story.append(_tabela_variacao(novo, COR_AZUL, "★"))
                story.append(Spacer(1, 0.3*cm))

            if sumiu:
                story.append(Paragraph("Empresas removidas da lista",
                                       ParagraphStyle("sh", fontSize=10, fontName="Helvetica-Bold",
                                                      textColor=COR_CINZA, spaceAfter=4)))
                story.append(_tabela_variacao(sumiu, COR_CINZA, "✕"))
                story.append(Spacer(1, 0.3*cm))

        story.append(Spacer(1, 0.3*cm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=COR_CINZA))
        story.append(Spacer(1, 0.4*cm))

    # ── SEÇÕES NORMAIS ──
    if crit_l:
        _header_secao(story, "SITUACAO FISCAL: CRITICADO", COR_VERMELHO)
        story.append(_tabela(crit_l, COR_VERMELHO))
        story.append(Spacer(1, 0.5*cm))

    if ok_l:
        _header_secao(story, "SITUACAO FISCAL: OK", COR_VERDE)
        story.append(_tabela(ok_l, COR_VERDE))
        story.append(Spacer(1, 0.5*cm))

    if erro_l:
        _header_secao(story, "ERROS / TIMEOUT", colors.orange)
        d = [["Razão Social", "CNPJ", "Obs"]]
        for r in erro_l:
            d.append([r["nome"], r["cnpj"], r.get("obs", "")[:50]])
        t = Table(d, colWidths=[7*cm, 4.5*cm, 5.5*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (-1,0), colors.orange),
            ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
            ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",     (0,0), (-1,-1), 8),
            ("FONTNAME",     (0,1), (-1,-1), "Helvetica"),
            ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, COR_ZEBRA]),
            ("GRID",         (0,0), (-1,-1), 0.3, colors.HexColor("#cccccc")),
            ("BOTTOMPADDING",(0,0), (-1,-1), 4),
            ("TOPPADDING",   (0,0), (-1,-1), 4),
            ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ]))
        story.append(t)

    # Rodapé
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=COR_CINZA))
    story.append(Paragraph(
        f"Gerado automaticamente — Agente Fiscal RN v1.1 — {agora}",
        ParagraphStyle("r", fontSize=7, textColor=COR_CINZA)
    ))

    doc.build(story)
    print(f"[pdf] {path}")
    return path


# ─────────────────────────────────────────────
# ENVIAR E-MAIL
# ─────────────────────────────────────────────

def enviar_email(path_pdf: str, resultados: List[Dict], comparacao: Optional[Dict] = None, data_anterior: Optional[str] = None):
    if not DESTINATARIOS:
        print("[email] Sem destinatários — pulando.")
        return

    hoje   = datetime.now().strftime("%d/%m/%Y")
    ok_c   = sum(1 for r in resultados if r["status"] == "OK")
    crit_c = sum(1 for r in resultados if r["status"] == "CRITICADO")
    erro_c = sum(1 for r in resultados if r["status"] == "ERRO")

    assunto = f"[Agente Fiscal RN] {hoje} — OK:{ok_c} | CRITICADO:{crit_c}" + \
              (f" | ERRO:{erro_c}" if erro_c else "")

    # Bloco HTML de variações
    html_variacoes = ""
    if comparacao and data_anterior:
        piorou   = comparacao.get("piorou",   [])
        melhorou = comparacao.get("melhorou", [])

        def _linhas(lista):
            return "".join(f"<tr><td>{r['nome']}</td><td style='color:#555'>{r['cnpj']}</td></tr>" for r in lista)

        partes = []
        if piorou:
            partes.append(f"""
            <h3 style="color:#c0392b;margin-bottom:4px">▼ Pioraram — OK → CRITICADO ({len(piorou)})</h3>
            <table cellpadding="4" style="border-collapse:collapse;width:100%;font-size:13px">
              <tr style="background:#c0392b;color:white"><th align="left">Razão Social</th><th align="left">CNPJ</th></tr>
              {_linhas(piorou)}
            </table>""")

        if melhorou:
            partes.append(f"""
            <h3 style="color:#1a7f37;margin-bottom:4px">▲ Melhoraram — CRITICADO → OK ({len(melhorou)})</h3>
            <table cellpadding="4" style="border-collapse:collapse;width:100%;font-size:13px">
              <tr style="background:#1a7f37;color:white"><th align="left">Razão Social</th><th align="left">CNPJ</th></tr>
              {_linhas(melhorou)}
            </table>""")

        if partes:
            html_variacoes = f"""
            <hr style="margin:16px 0">
            <h2 style="color:#2980b9">Variações em relação a {data_anterior}</h2>
            {"".join(partes)}"""
        elif not piorou and not melhorou:
            html_variacoes = f"""
            <hr style="margin:16px 0">
            <p style="color:#555"><b>Sem variações</b> de status em relação a {data_anterior}.</p>"""

    html = f"""<html><body style="font-family:Arial,sans-serif">
    <h2 style="color:#1a3a5c">Relatório Fiscal SEFAZ-RN — {hoje}</h2>
    <table cellpadding="4">
      <tr><td><b>Total</b></td><td>{len(resultados)}</td></tr>
      <tr><td style="color:#1a7f37"><b>OK</b></td><td>{ok_c}</td></tr>
      <tr><td style="color:#c0392b"><b>Criticado</b></td><td>{crit_c}</td></tr>
      {"" if not erro_c else f"<tr><td style='color:orange'><b>Erro</b></td><td>{erro_c}</td></tr>"}
    </table>
    {html_variacoes}
    <p style="margin-top:16px">Relatório completo em anexo.</p>
    </body></html>"""

    msg            = MIMEMultipart("mixed")
    msg["From"]    = f"{SMTP_FROM_NAME} <{SMTP_FROM}>"
    msg["To"]      = ", ".join(DESTINATARIOS)
    msg["Subject"] = assunto
    msg.attach(MIMEText(html, "html", "utf-8"))

    with open(path_pdf, "rb") as f:
        parte = MIMEBase("application", "octet-stream")
        parte.set_payload(f.read())
    encoders.encode_base64(parte)
    parte.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(path_pdf)}"')
    msg.attach(parte)

    print(f"[email] Enviando para {DESTINATARIOS}...")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
        s.ehlo(); s.starttls(); s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(SMTP_FROM, DESTINATARIOS, msg.as_bytes())
    print("[email] Enviado!")
