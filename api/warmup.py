"""Aquecimento da API única do EnadeX logo depois que ela sobe.

1. Espera o /api/health responder.
2. Chama, direto na API, as rotas que carregam bases para a memória: EduCluster (~490 mil linhas, ~60 s a frio),
   E-XplainENADE (13 tabelas) e as listas fixas do ENADE-Time e do MultiENADE. Assim nenhum visitante paga a
   carga a frio.
3. Repete as mesmas rotas pelo `edge` (nginx) para deixar as respostas no cache de borda.

Erros só vão para o log; o aquecimento nunca derruba a API. Para trocar a lista: WARMUP_PATHS (separada por espaço).
"""
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.getenv("WARMUP_BASE", "http://127.0.0.1:8000")
EDGE = os.getenv("WARMUP_EDGE", "http://edge:8080")

PADRAO = [
    # EduCluster primeiro: é a carga mais pesada e destrava várias páginas.
    "/api/educluster/cursos",
    "/api/educluster/cursos/clusters",
    "/api/educluster/estudantes/clusters",
    "/api/educluster/estudantes/calibracao",
    "/api/educluster/estudantes/discursivas",
    "/api/educluster/cursos/clusters/estabilidade",
    "/api/educluster/areas",
    "/api/educluster/dimensoes",
    "/api/educluster/espacos-desempenho",
    # E-XplainENADE.
    "/api/e-xplainenade/opcoes",
    "/api/e-xplainenade/dataset/resumo",
    # MultiENADE.
    "/api/multienade/relatorio-regressao",
    "/api/multienade/relatorio-cluster",
    "/api/multienade/relatorio-associacao",
    "/api/multienade/relatorio-shap",
    # ENADE-Time.
    "/api/enade-time/dim/regioes",
    "/api/enade-time/dim/ufs",
    "/api/enade-time/dim/anos",
    "/api/enade-time/dim/grupos",
    "/api/enade-time/dim/modalidades",
    "/api/enade-time/dim/categorias-adm",
    "/api/enade-time/dim/organizacoes-academicas",
    "/api/enade-time/analises/resumo-anual",
    "/api/enade-time/analises/resumo-regiao",
    "/api/enade-time/analises/resumo-uf",
    "/api/enade-time/benchmark/comparativo",
    "/api/enade-time/benchmark/carga",
]


def log(msg: str) -> None:
    print(f"[warmup] {msg}", file=sys.stdout, flush=True)


def get(url: str, timeout: float, silencioso: bool = False) -> tuple[int, float]:
    inicio = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            resp.read()
            return resp.status, time.monotonic() - inicio
    except urllib.error.HTTPError as erro:
        return erro.code, time.monotonic() - inicio
    except Exception as erro:  # noqa: BLE001 (o aquecimento nunca pode derrubar nada)
        if not silencioso:
            log(f"falha em {url}: {type(erro).__name__}")
        return 0, time.monotonic() - inicio


def esperar_saude(limite_s: float = 180.0) -> bool:
    # Enquanto o uvicorn importa os 4 módulos (~20 s), a conexão é recusada: isso não é erro e não vai para o log.
    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        status, _ = get(f"{BASE}/api/health", timeout=3, silencioso=True)
        if status == 200:
            return True
        time.sleep(2)
    return False


def main() -> None:
    if not esperar_saude():
        log("a API não respondeu ao /api/health em 180 s; aquecimento cancelado")
        return
    caminhos = os.getenv("WARMUP_PATHS", "").split() or PADRAO
    inicio = time.monotonic()
    for caminho in caminhos:
        status, segundos = get(f"{BASE}{caminho}", timeout=240)
        log(f"{status} {segundos:6.1f}s {caminho}")
    log(f"memória da API aquecida em {time.monotonic() - inicio:.0f}s")
    for caminho in caminhos:
        get(f"{EDGE}{caminho}", timeout=60)
    log("cache de borda preenchido")


if __name__ == "__main__":
    main()
