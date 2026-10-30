"""
reprocessar_erros.py - Reprocessa só empresas com ERRO do dia
"""
import sys, json, os
from datetime import datetime
from scraper import _fazer_login, _listar_empresas, _coletar_status
from report import salvar_log, gerar_pdf, enviar_email, carregar_historico_anterior, comparar_resultados
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()
LOG_DIR = "/root/agente_fiscal/logs"
hoje = datetime.now().strftime("%Y-%m-%d")
RELATORIO = os.path.join(LOG_DIR, f"relatorio_{hoje}.json")

def main():
    with open(RELATORIO) as f:
        resultados = json.load(f)
    erros = [r for r in resultados if r["status"] == "ERRO"]
    print(f"[reprocessar] {len(erros)} empresas com ERRO.")
    if not erros:
        print("Nenhum ERRO. Saindo.")
        sys.exit(0)
    cnpjs_erro = {r["cnpj"] for r in erros}
    with sync_playwright() as p:
        headless = os.getenv("HEADLESS","true").lower()=="true"
        browser = p.chromium.launch(headless=headless, args=["--no-sandbox","--disable-dev-shm-usage"])
        page = browser.new_context(viewport={"width":1280,"height":800}).new_page()
        try:
            _fazer_login(page)
            empresas = _listar_empresas(page)
            pendentes = [e for e in empresas if e["cnpj"] in cnpjs_erro]
            print(f"[reprocessar] {len(pendentes)} na lista do site.")
            novos = {}
            for i, emp in enumerate(pendentes):
                print(f"[{i+1}/{len(pendentes)}]", end=" ")
                novos[emp["cnpj"]] = _coletar_status(page, emp)
        except Exception as e:
            print(f"[ERRO CRITICO] {e}")
            sys.exit(1)
        finally:
            browser.close()
    for r in resultados:
        if r["cnpj"] in novos:
            r["status"] = novos[r["cnpj"]]["status"]
            r["obs"] = novos[r["cnpj"]].get("obs","")
    with open(RELATORIO,"w") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    anterior, data_anterior = carregar_historico_anterior()
    comparacao = comparar_resultados(resultados, anterior) if anterior else None
    path_pdf = gerar_pdf(resultados, comparacao, data_anterior)
    enviar_email(path_pdf, resultados, comparacao, data_anterior)
    ok_l=[r for r in resultados if r["status"]=="OK"]
    crit_l=[r for r in resultados if r["status"]=="CRITICADO"]
    erro_l=[r for r in resultados if r["status"]=="ERRO"]
    print(f"\nCONCLUÍDO: {len(ok_l)} OK | {len(crit_l)} CRITICADO | {len(erro_l)} ERRO")

if __name__=="__main__":
    main()
