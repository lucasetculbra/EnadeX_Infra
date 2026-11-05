"""Aquecimento da API única do EnadeX logo depois que ela sobe.

1. Espera o /api/health responder.
2. Carrega as bases para a memória com rotas baratas, chamadas direto na API e em série: EduCluster (arq3 + arq4,
   ~490 mil linhas cada, ~110 s a frio), E-XplainENADE (13 tabelas) e o pool do leitor do ENADE-Time.
3. Chama cada rota da lista UMA vez pela borda (nginx). Ela calcula a resposta, e a borda a guarda no cache.

Cada rota pesada é calculada uma vez só. Em 05/11/2026, a versão anterior chamava tudo direto e depois pela borda: o
segundo cálculo dos clusters de estudantes, sobre a memória já fragmentada, estourava o limite do container.
Se a borda não responder, a rota é chamada direto na API.

Erros só vão para o log; o aquecimento nunca derruba a API. Para trocar a lista da etapa 3: WARMUP_PATHS (separada
por espaço).
"""
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.getenv("WARMUP_BASE", "http://127.0.0.1:8000")
EDGE = os.getenv("WARMUP_EDGE", "http://edge:8080")

# Etapa 2: rotas leves que forçam a carga das bases (o cálculo em si é desprezível).
CARGA = [
    "/api/educluster/areas",
    "/api/e-xplainenade/dataset/resumo",
    "/api/enade-time/dim/anos",
]

# Etapa 3: o que as páginas pedem ao abrir.
PADRAO = [
    "/api/educluster/cursos",
    "/api/educluster/cursos/clusters",
    "/api/educluster/estudantes/clusters",
    "/api/educluster/estudantes/calibracao",
    "/api/educluster/estudantes/discursivas",
    "/api/educluster/cursos/clusters/estabilidade",
    "/api/educluster/areas",
    "/api/educluster/dimensoes",
    "/api/educluster/espacos-desempenho",
    "/api/e-xplainenade/opcoes",
    "/api/e-xplainenade/dataset/resumo",
    "/api/multienade/relatorio-regressao",
    "/api/multienade/relatorio-cluster",
    "/api/multienade/relatorio-associacao",
    "/api/multienade/relatorio-shap",
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
    inicio = time.monotonic()
    for caminho in CARGA:
        status, segundos = get(f"{BASE}{caminho}", timeout=300)
        log(f"base  {status} {segundos:6.1f}s {caminho}")
    log(f"bases carregadas em {time.monotonic() - inicio:.0f}s")

    for caminho in os.getenv("WARMUP_PATHS", "").split() or PADRAO:
        status, segundos = get(f"{EDGE}{caminho}", timeout=300)
        if status == 0:  # borda fora do ar: calcula direto, sem cache
            status, segundos = get(f"{BASE}{caminho}", timeout=300)
        log(f"borda {status} {segundos:6.1f}s {caminho}")
    log(f"aquecimento concluído em {time.monotonic() - inicio:.0f}s (cache de borda preenchido)")


if __name__ == "__main__":
    main()
