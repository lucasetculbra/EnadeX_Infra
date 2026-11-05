# EnadeX_Infra

Infraestrutura de produção do EnadeX em **https://enadex.org**: as imagens Docker do site e da API, a borda nginx, o
compose da VPS e o CI que publica tudo no GHCR. Este repositório não guarda segredo nenhum; a operação está no
[RUNBOOK](RUNBOOK.md).

O repositório e as imagens ficam na conta `lucasetculbra`. Se o repositório for transferido para a organização
EnadeX, o CI passa a publicar em `ghcr.io/enadex` sozinho. Na VPS, basta trocar a variável `REGISTRO`.

## Como fica no ar

```
navegador ── HTTPS, HTTP/2, brotli ──▶ Traefik da VPS (TLS e certificados Let's Encrypt; já existia na VPS)
  enadex.org, api.enadex.org ──▶ edge (nginx :8080)
       /api/*  ──▶ cache dos GET + bloqueios + limite de taxa ──▶ api (FastAPI api_main.py, :8000)
       /*      ──▶ web (Next.js standalone, :3000)
  www.enadex.org ──▶ 301 para enadex.org
api ──▶ Supabase do grupo (us-east-2): PostgREST com a chave de serviço; ENADE-Time pelo pooler com o papel leitor
```

- VPS Hostinger KVM 2 em Campinas, compartilhada com outro projeto Docker (`n8n`, de terceiros). O projeto `enadex`
  fica separado e só se liga à rede do Traefik pela borda, com rótulos; nada no outro projeto muda.
- Site e API na mesma origem: sem CORS nem preflight, uma conexão só para página e dados. `api.enadex.org` serve a
  mesma API para uso externo e o Swagger (`https://api.enadex.org/docs`).

## Estrutura

| Caminho | O que é |
|---|---|
| `api/` | Imagem da API única (`EnadeX_Backend/api_main.py`, 4 módulos): Dockerfile, dependências, entrada (`uvicorn` em um processo) e aquecimento |
| `web/` | Imagem do frontend (`EnadeX_Frontend`): build standalone com as `NEXT_PUBLIC_*` apontando para `https://enadex.org` |
| `edge/` | Borda nginx: roteamento, cache, rotas bloqueadas e limites de taxa |
| `deploy/docker-compose.yml` | Projeto `enadex` no Docker Manager da Hostinger |
| `deploy/.env.example` | Nomes das variáveis; os segredos são preenchidos só no hPanel |
| `deploy/docker-compose.local.yml` | Sobreposição para testar no PC, sem Traefik |
| `.github/workflows/build.yml` | Gera, testa e publica as três imagens |
| `.github/workflows/promover.yml` | Faz a `:main` de uma imagem apontar para uma versão já publicada (rollback sem rebuild) |
| `RUNBOOK.md` | Operação: primeiro deploy, atualização, rollback, dados, segredos e verificação |

## Imagens

| Imagem | Fonte | Tags |
|---|---|---|
| `ghcr.io/lucasetculbra/enadex-api` | `EnadeX/EnadeX_Backend` (`main`) | `main` e o sha de 12 caracteres do backend |
| `ghcr.io/lucasetculbra/enadex-web` | `Cintriano/EnadeX_Frontend` (`master`; privado, lido com a chave de deploy `FRONTEND_DEPLOY_KEY`, só leitura, ou com o token `FRONTEND_REPO_TOKEN`) | `main` e o sha do frontend |
| `ghcr.io/lucasetculbra/enadex-edge` | este repositório (`edge/`) | `main` e o sha deste repositório |

O CI roda em push na `main` deste repositório, manualmente (Actions → *Imagens do EnadeX* → *Run workflow*, com
branch, tag ou commit de cada fonte) e por `repository_dispatch` (`backend-atualizado`, `frontend-atualizado`). Cada
imagem só é publicada depois de passar num teste de fumaça:

- **api:** sobe sem segredos e responde `/api/health`, o que falha se algum dos 4 módulos não importar. As versões
  resolvidas das dependências ficam no artefato `api-requirements-lock`.
- **web:** 10 páginas respondem 200, `/enade-time/spd` redireciona (307), uma rota inexistente dá o 404 do módulo e a
  URL de produção está no bundle.
- **edge:** `nginx -t`.

Publicar uma imagem não muda o site. A VPS só troca de versão quando o projeto é atualizado (ver RUNBOOK).

## Desempenho

- **Cache dos `GET /api/*` na borda** (em memória): 10 min de validade. Durante a atualização, a borda continua
  servindo a cópia anterior (`stale-while-revalidate`), e só uma requisição por rota vai até a API
  (`proxy_cache_lock`). O cabeçalho `X-Cache` mostra `HIT`, `MISS`, `STALE` ou `UPDATING`.
- **API em um processo**, com as bases em memória e aquecimento automático a cada partida: o primeiro visitante já
  encontra tudo carregado.
- **Next.js standalone**, com compressão brotli/gzip no Traefik e `/_next/static` imutável por 1 ano.
- **Imagens geradas no GitHub Actions**: a VPS só baixa e sobe, sem gastar CPU em build.

## Segurança na borda

- `403` em `POST /api/multienade/reprocessar/*`, em `/api/e-xplainenade/dataset/refresh` e em qualquer `forcar=true`
  (descrição paga do Gemini).
- Limites por IP:
  - 20 req/s na API, com rajada de 40;
  - 6 req/min em `hipotese` e `relatorio` do E-XplainENADE;
  - 10 req/min na estabilidade do EduCluster.

  O corpo máximo é de 64 KB.
- HSTS, `nosniff`, `X-Frame-Options: DENY` e `Referrer-Policy` pelo Traefik.

## Build local (opcional)

Com o Docker Desktop, o backend clonado em `./backend` e o frontend em `./frontend` (os dois são ignorados pelo git):

```sh
docker build -f api/Dockerfile  -t ghcr.io/lucasetculbra/enadex-api:main  .
docker build -f web/Dockerfile  -t ghcr.io/lucasetculbra/enadex-web:main  --build-arg SITE_URL=http://localhost:8080 .
docker build -f edge/Dockerfile -t ghcr.io/lucasetculbra/enadex-edge:main .
cp deploy/.env.example deploy/.env    # preencher os segredos; o arquivo nunca é versionado
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.local.yml --env-file deploy/.env up
```

O site fica em http://localhost:8080 e a API em http://localhost:8080/api/health.
