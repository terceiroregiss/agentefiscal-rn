import os, re, time, random
from typing import List, Dict
from datetime import datetime
from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout
from dotenv import load_dotenv
from captcha import resolver_captcha_imagem

load_dotenv()

UVT_URL     = os.getenv("UVT_URL", "https://uvt.sefaz.rn.gov.br/#/home")
UVT_USUARIO = os.getenv("UVT_USUARIO", "")
UVT_SENHA   = os.getenv("UVT_SENHA", "")
HEADLESS    = os.getenv("HEADLESS", "true").lower() == "true"

MAX_TENTATIVAS = 3  # retry por empresa


def _pausa(minimo=0.8, maximo=2.2):
    """Pausa aleatória humanizada."""
    time.sleep(random.uniform(minimo, maximo))


def _digitar_campo(page, selector, value):
    try:
        el = page.locator(selector).first
        el.click(timeout=5000)
        el.fill("")
        _pausa(0.1, 0.3)
        page.keyboard.type(value, delay=random.randint(60, 120))
        _pausa(0.2, 0.5)
    except Exception as e:
        print(f"  [warn] campo {selector}: {e}")


def _fazer_login(page: Page):
    print("[login] Acessando UVT...")
    page.goto(UVT_URL, wait_until="domcontentloaded", timeout=30000)
    _pausa(3, 5)
    page.locator('button:has-text("Usuário e senha"), a:has-text("Usuário e senha")').first.click()
    _pausa(1.5, 3)
    page.wait_for_selector('#code, input[name="code"]', timeout=10000)
    _pausa(0.8, 1.5)
    for tentativa in range(1, 6):
        print(f"  [login] Tentativa {tentativa}/5...")
        _digitar_campo(page, '#code, input[name="code"]', UVT_USUARIO)
        _pausa(0.3, 0.7)
        _digitar_campo(page, '#password, input[name="password"]', UVT_SENHA)
        _pausa(0.3, 0.7)
        texto_captcha = resolver_captcha_imagem(page)
        _digitar_campo(page, '#captcha, input[name="captcha"]', texto_captcha)
        _pausa(0.3, 0.6)
        print(f"  [login] Captcha: {texto_captcha}")
        page.evaluate("""
(function() {
    var btns = document.querySelectorAll('button');
    for (var i=0; i<btns.length; i++) {
        if (btns[i].textContent.trim().includes('Acessar')) {
            btns[i].removeAttribute('disabled');
            btns[i].click();
            return;
        }
    }
})();
""")
        _pausa(2.5, 4)
        try:
            page.wait_for_selector('text=Selecionar', timeout=5000)
            print("[login] Login OK!")
            return
        except PWTimeout:
            pass
        try:
            page.locator('text=solicitar nova imagem').first.click(timeout=3000)
            _pausa(1, 2)
        except:
            page.reload(wait_until="domcontentloaded", timeout=15000)
            _pausa(2.5, 4)
            page.locator('button:has-text("Usuário e senha")').first.click()
            _pausa(1.5, 2.5)
    raise RuntimeError("Login falhou após 5 tentativas.")


def _listar_empresas(page: Page) -> List[Dict]:
    print("[empresas] Coletando lista...")
    page.locator('text=Selecionar uma empresa').first.click()
    _pausa(1.5, 3)
    empresas = []
    linhas = page.locator("table tbody tr").all()
    for linha in linhas:
        texto = linha.inner_text().strip()
        if not texto or "Razão Social" in texto:
            continue
        partes = [p.strip() for p in re.split(r'\t|\n', texto) if p.strip()]
        if len(partes) >= 2:
            empresas.append({
                "nome": partes[0],
                "ie":   partes[1] if len(partes) > 1 else "",
                "cnpj": partes[2] if len(partes) > 2 else "",
            })
    try:
        page.locator('button:has-text("Fechar")').first.click(timeout=3000)
        _pausa(0.8, 1.5)
    except:
        pass
    print(f"[empresas] {len(empresas)} encontrada(s).")
    return empresas


def _abrir_modal(page: Page):
    try:
        page.locator('button:has-text("Fechar")').first.click(timeout=2000)
        _pausa(0.4, 0.8)
    except:
        pass
    try:
        page.locator('button:has-text("Clique para trocar de empresa")').first.click(timeout=3000)
        _pausa(1.5, 2.5)
        page.wait_for_selector('table tbody tr', timeout=5000)
        return
    except:
        pass
    try:
        page.locator('text=Selecionar uma empresa').first.click(timeout=3000)
        _pausa(1.5, 2.5)
        page.wait_for_selector('table tbody tr', timeout=5000)
        return
    except:
        pass
    raise RuntimeError("Não conseguiu abrir o modal de empresas")


def _tentar_coletar(page: Page, empresa: Dict) -> Dict:
    """Uma tentativa de coletar o status de uma empresa."""
    nome = empresa["nome"]
    cnpj = empresa["cnpj"]
    resultado = {"nome": nome, "cnpj": cnpj, "ie": empresa.get("ie", ""), "status": "ERRO", "obs": ""}

    # Abre modal e seleciona empresa
    _abrir_modal(page)
    try:
        page.locator(f'table tbody tr:has-text("{cnpj}") a').first.click(timeout=5000)
    except:
        page.locator(f'table tbody tr:has-text("{nome[:20]}") a').first.click(timeout=5000)
    _pausa(1.5, 3)

    # Clica no ícone $ (Débitos)
    page.locator('button[uib-tooltip="Débitos"]').first.click(timeout=8000)
    page.wait_for_selector('text=Relatório Sintético de Débitos', timeout=10000)
    _pausa(0.6, 1.2)

    # Clica em Extrato Fiscal
    page.locator('.modal-content a:has-text("Extrato Fiscal"), .modal a:has-text("Extrato Fiscal"), a:has-text("Extrato Fiscal")').first.click(timeout=8000)
    page.wait_for_selector('text=Extrato Fiscal do Contribuinte', timeout=12000)
    _pausa(0.8, 1.5)

    # Captura status
    html = page.content()
    if re.search(r'CRITICADO', html, re.IGNORECASE):
        resultado["status"] = "CRITICADO"
    elif re.search(r'\bOK\b', html, re.IGNORECASE):
        resultado["status"] = "OK"

    try:
        page.locator('button:has-text("Fechar")').first.click(timeout=3000)
        _pausa(0.4, 0.8)
    except:
        pass

    return resultado


def _coletar_status(page: Page, empresa: Dict) -> Dict:
    """Coleta status com retry humanizado em caso de erro."""
    nome = empresa["nome"]
    cnpj = empresa["cnpj"]
    print(f"[{datetime.now().strftime('%H:%M:%S')}]  -> {nome} ({cnpj})")

    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            resultado = _tentar_coletar(page, empresa)
            print(f"    Status: {resultado['status']} [{datetime.now().strftime('%H:%M:%S')}]")
            return resultado

        except PWTimeout as e:
            obs = f"Timeout: {str(e)[:80]}"
            if tentativa < MAX_TENTATIVAS:
                espera = random.uniform(4, 8) * tentativa
                print(f"     [retry {tentativa}/{MAX_TENTATIVAS}] Timeout — aguardando {espera:.1f}s...")
                time.sleep(espera)
                # Fecha qualquer modal aberto antes de tentar de novo
                try:
                    page.locator('button:has-text("Fechar")').first.click(timeout=2000)
                    _pausa(0.5, 1)
                except:
                    pass
            else:
                print(f"     ERRO: {nome}: timeout após {MAX_TENTATIVAS} tentativas")
                return {"nome": nome, "cnpj": cnpj, "ie": empresa.get("ie", ""), "status": "ERRO", "obs": obs}

        except Exception as e:
            obs = str(e)[:100]
            if tentativa < MAX_TENTATIVAS:
                espera = random.uniform(3, 7) * tentativa
                print(f"     [retry {tentativa}/{MAX_TENTATIVAS}] Erro — aguardando {espera:.1f}s...")
                time.sleep(espera)
                try:
                    page.locator('button:has-text("Fechar")').first.click(timeout=2000)
                    _pausa(0.5, 1)
                except:
                    pass
            else:
                print(f"     ERRO: {nome}: {e}")
                return {"nome": nome, "cnpj": cnpj, "ie": empresa.get("ie", ""), "status": "ERRO", "obs": obs}

    # Nunca deve chegar aqui, mas por segurança
    return {"nome": nome, "cnpj": cnpj, "ie": empresa.get("ie", ""), "status": "ERRO", "obs": "Max tentativas atingido"}


def coletar_todas_empresas() -> List[Dict]:
    resultados = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()
        try:
            _fazer_login(page)
            empresas = _listar_empresas(page)
            for i, emp in enumerate(empresas):
                print(f"[{i+1}/{len(empresas)}]", end=" ")
                resultados.append(_coletar_status(page, emp))
                # Pausa humanizada entre empresas
                _pausa(0.8, 2.0)
        except Exception as e:
            print(f"[ERRO CRITICO] {e}")
            try:
                page.screenshot(path="/tmp/erro.png")
            except:
                pass
        finally:
            browser.close()
    return resultados
