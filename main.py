import sys
from datetime import datetime
from scraper import coletar_todas_empresas
from report import salvar_log, gerar_pdf, enviar_email, carregar_historico_anterior, comparar_resultados

def main():
    inicio = datetime.now()
    print("="*60)
    print(f" AGENTE FISCAL RN — {inicio.strftime('%d/%m/%Y %H:%M:%S')}")
    print("="*60)

    resultados = coletar_todas_empresas()

    if not resultados:
        print("[AVISO] Nenhum resultado. Verifique o log.")
        sys.exit(1)

    # Salva log ANTES de comparar (garante que hoje seja ignorado na busca)
    salvar_log(resultados)

    # Carrega histórico anterior e compara
    anterior, data_anterior = carregar_historico_anterior()
    comparacao = None
    if anterior:
        comparacao = comparar_resultados(resultados, anterior)
        piorou   = len(comparacao["piorou"])
        melhorou = len(comparacao["melhorou"])
        print(f"[comparacao] Em relação a {data_anterior}: {piorou} pioraram, {melhorou} melhoraram")

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
