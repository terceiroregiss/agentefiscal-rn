import sys, json, os, time
from datetime import datetime
from scraper import _fazer_login, _listar_empresas, _coletar_status
from report import salvar_log, gerar_pdf, enviar_email, carregar_historico_anterior, comparar_resultados
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv(dotenv_path="/root/agente_fiscal/.env")

CHECKPOINT       = "/root/agente_fiscal/checkpoint.json"
REINICIAR_A_CADA = 50
MAX_PASSAGENS    = 3   # quantas vezes tenta reprocessar ERROs


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
    headless = os.getenv("HEADLESS", "true").lower() == "true"
    browser = p.chromium.launch(headless=headless, args=["--no-sandbox", "--disable-dev-shm-usage"])
    page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()
    return browser, page


def _rodar_passagem(p, lista_empresas, resultados, empresas_total, label=""):
    """Processa uma lista de empresas, atualizando resultados in-place."""
    browser, page = _criar_browser(p)
    try:
        _fazer_login(page)
        for i, emp in enumerate(lista_empresas):
            # reinicia browser a cada REINICIAR_A_CADA empresas
            if i > 0 and i % REINICIAR_A_CADA == 0:
                print(f'\n[browser] Reiniciando browser{label}...')
                for _tr in range(3):
                    try: browser.close()
                    except: pass
                    time.sleep(3)
                    try:
                        browser, page = _criar_browser(p)
                        _fazer_login(page)
                        print('[browser] Reiniciado OK.\n')
                        break
                    except Exception as _e:
                        print(f'[browser] Falha restart ({_tr+1}/3): {_e}')

            idx_global = next(
                (j+1 for j, r in enumerate(resultados) if r["cnpj"] == emp["cnpj"]),
                i + 1
            )
            print(f"[{idx_global}/{empresas_total}]{label}", end=" ")
            novo = _coletar_status(page, emp)

            # substitui entrada existente ou adiciona
            substituiu = False
            for j, r in enumerate(resultados):
                if r["cnpj"] == emp["cnpj"]:
                    resultados[j] = novo
                    substituiu = True
                    break
            if not substituiu:
                resultados.append(novo)

            salvar_checkpoint(resultados)

    except Exception as e:
        print(f"[ERRO CRITICO{label}] {e}")
        try: page.screenshot(path="/tmp/erro_critico.png")
        except: pass
    finally:
        try: browser.close()
        except: pass


def main():
    inicio = datetime.now()
    print("="*60)
    print(f" AGENTE FISCAL RN — {inicio.strftime('%d/%m/%Y %H:%M:%S')}")
    print("="*60)

    resultados    = carregar_checkpoint()
    cnpjs_feitos  = {r["cnpj"] for r in resultados}
    if resultados:
        print(f"[checkpoint] Retomando: {len(resultados)} empresas OK/CRITICADO já feitas.")

    with sync_playwright() as p:

        # ── PASSAGEM PRINCIPAL ──────────────────────────────────
        browser, page = _criar_browser(p)
        empresas_total = None
        try:
            _fazer_login(page)
            empresas = _listar_empresas(page)
            empresas_total = len(empresas)
            pendentes = [e for e in empresas if e["cnpj"] not in cnpjs_feitos]
            print(f"[checkpoint] {len(pendentes)} restantes de {empresas_total} total.")
            browser.close()
        except Exception as e:
            print(f"[ERRO CRITICO] {e}")
            try: browser.close()
            except: pass
            sys.exit(1)

        _rodar_passagem(p, pendentes, resultados, empresas_total)

        # ── PASSAGENS DE RETRY (ERROs) ──────────────────────────
        for passagem in range(2, MAX_PASSAGENS + 1):
            erros = [
                next(e for e in empresas if e["cnpj"] == r["cnpj"])
                for r in resultados if r["status"] == "ERRO"
                if any(e["cnpj"] == r["cnpj"] for e in empresas)
            ]
            if not erros:
                print(f"\n[retry] Nenhum ERRO restante — encerrando passagens.")
                break
            print(f"\n{'='*60}")
            print(f" PASSAGEM {passagem} — {len(erros)} empresa(s) com ERRO")
            print(f"{'='*60}")
            time.sleep(5)
            _rodar_passagem(p, erros, resultados, empresas_total, label=f" [P{passagem}]")

    if not resultados:
        print("[AVISO] Nenhum resultado.")
        sys.exit(1)

    if os.path.exists(CHECKPOINT):
        os.remove(CHECKPOINT)

    # ── RELATÓRIO ───────────────────────────────────────────────
    salvar_log(resultados)
    anterior, data_anterior = carregar_historico_anterior()
    comparacao = None
    if anterior:
        comparacao = comparar_resultados(resultados, anterior)
        print(f"[comparacao] {len(comparacao['piorou'])} pioraram, {len(comparacao['melhorou'])} melhoraram")

    path_pdf = gerar_pdf(resultados, comparacao, data_anterior)
    enviar_email(path_pdf, resultados, comparacao, data_anterior)

    fim    = datetime.now()
    ok_l   = [r for r in resultados if r["status"] == "OK"]
    crit_l = [r for r in resultados if r["status"] == "CRITICADO"]
    erro_l = [r for r in resultados if r["status"] == "ERRO"]

    print()
    print("="*60)
    print(f" CONCLUIDO em {int((fim-inicio).total_seconds())}s")
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
        print("\nEmpresas com ERRO (após todas as passagens):")
        for r in erro_l:
            print(f"  - {r['nome']} | {r['cnpj']} | {r.get('obs','')}")


if __name__ == "__main__":
    main()
