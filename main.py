import sys, json, os
from datetime import datetime
from scraper import _fazer_login, _listar_empresas, _coletar_status
from report import salvar_log, gerar_pdf, enviar_email, carregar_historico_anterior, comparar_resultados
from playwright.sync_api import sync_playwright

CHECKPOINT       = "/root/agente_fiscal/checkpoint.json"
REINICIAR_A_CADA = 50

def carregar_checkpoint():
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            data = json.load(f)
            return [r for r in data if r.get("status") in ("OK", "CRITICADO")]
    return []

def salvar_checkpoint(resultados):
    sucesso = [r for r in resultados if r.get("status") in ("OK", "CRITICADO")]
    with open(CHECKPOINT, "w") as f:
        json.dump(sucesso, f, ensure_ascii=False, indent=2)

def _criar_browser(p):
    from dotenv import load_dotenv
    load_dotenv()
    headless = os.getenv("HEADLESS", "true").lower() == "true"
    browser = p.chromium.launch(headless=headless, args=["--no-sandbox", "--disable-dev-shm-usage"])
    page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()
    return browser, page

def main():
    inicio = datetime.now()
    print("="*60)
    print(f" AGENTE FISCAL RN — {inicio.strftime('%d/%m/%Y %H:%M:%S')}")
    print("="*60)

    resultados = carregar_checkpoint()
    cnpjs_feitos = {r["cnpj"] for r in resultados}
    if resultados:
        print(f"[checkpoint] Retomando: {len(resultados)} empresas OK/CRITICADO já feitas.")

    with sync_playwright() as p:
        browser, page = _criar_browser(p)
        empresas_total = None
        try:
            _fazer_login(page)
            empresas = _listar_empresas(page)
            empresas_total = len(empresas)
            pendentes = [e for e in empresas if e["cnpj"] not in cnpjs_feitos]
            print(f"[checkpoint] {len(pendentes)} empresas restantes de {empresas_total} total.")

            for i, emp in enumerate(pendentes):
                if i > 0 and i % REINICIAR_A_CADA == 0:
                    print(f'\n[browser] Reiniciando browser após {REINICIAR_A_CADA} empresas...')
                    for _tr in range(3):
                        try:
                            browser.close()
                        except:
                            pass
                        import time as _t; _t.sleep(3)
                        try:
                            browser, page = _criar_browser(p)
                            _fazer_login(page)
                            print('[browser] Reiniciado e logado OK.\n')
                            break
                        except Exception as _e:
                            print(f'[browser] Falha restart ({_tr+1}/3): {_e}')
                            if _tr == 2:
                                print('[browser] Mantendo browser atual e continuando...')
                idx = len(cnpjs_feitos) + i + 1
                print(f"[{idx}/{empresas_total}]", end=" ")
                resultado = _coletar_status(page, emp)
                resultados.append(resultado)
                salvar_checkpoint(resultados)

        except Exception as e:
            print(f"[ERRO CRITICO] {e}")
            try:
                page.screenshot(path="/tmp/erro_critico.png")
            except:
                pass
        finally:
            try:
                browser.close()
            except:
                pass

    if not resultados:
        print("[AVISO] Nenhum resultado. Verifique o log.")
        sys.exit(1)

    if os.path.exists(CHECKPOINT):
        os.remove(CHECKPOINT)

    salvar_log(resultados)
    anterior, data_anterior = carregar_historico_anterior()
    comparacao = None
    if anterior:
        comparacao = comparar_resultados(resultados, anterior)
        print(f"[comparacao] {len(comparacao['piorou'])} pioraram, {len(comparacao['melhorou'])} melhoraram")

    path_pdf = gerar_pdf(resultados, comparacao, data_anterior)
    enviar_email(path_pdf, resultados, comparacao, data_anterior)

    fim = datetime.now()
    ok_l   = [r for r in resultados if r["status"] == "OK"]
    crit_l = [r for r in resultados if r["status"] == "CRITICADO"]
    erro_l = [r for r in resultados if r["status"] == "ERRO"]

    print()
    print("="*60)
    print(f" CONCLUIDO em {(fim-inicio).seconds}s")
    print(f"  Total:     {len(resultados)}")
    print(f"  OK:        {len(ok_l)}")
    print(f"  CRITICADO: {len(crit_l)}")
    print(f"  ERRO:      {len(erro_l)}")
    print("="*60)

    if crit_l:
        print("\nEmpresas CRITICADO:")
        for r in crit_l:
            print(f"  - {r['nome']} | {r['cnpj']}")
    if erro_l:
        print("\nEmpresas com ERRO:")
        for r in erro_l:
            print(f"  - {r['nome']} | {r['cnpj']} | {r.get('obs','')}")

if __name__ == "__main__":
    main()
