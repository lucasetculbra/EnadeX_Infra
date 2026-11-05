# RUNBOOK — EnadeX em produção

| | |
|---|---|
| Site | https://enadex.org. API em https://enadex.org/api e https://api.enadex.org; Swagger em https://api.enadex.org/docs |
| VPS | Hostinger KVM 2 (2 vCPU, 8 GB), Campinas, `187.127.29.195` / `2a02:4780:6e:f18a::1`, compartilhada com o projeto `n8n` |
| Projeto Docker | `enadex` no Docker Manager do hPanel; o compose é `deploy/docker-compose.yml` |
| Banco | Supabase do grupo (us-east-2), administrado pelo Paulo |

As operações abaixo citam o nome no hPanel e, entre parênteses, a ferramenta equivalente da API/MCP da Hostinger.

## Regras que não mudam

1. **O projeto `n8n` não é do EnadeX.** É de terceiros, está em produção, e o Traefik dele também serve o EnadeX. Ele
   nunca é parado, reiniciado, atualizado ou recriado, e o `.env` dele não é aberto.
2. **Segredos ficam só no hPanel** (Docker Manager → `enadex` → variáveis de ambiente). Nunca em repositório, issue,
   chat, log ou chamada de API.
3. **"Criar projeto" só no primeiro deploy.** `VPS_createNewProjectV1` substitui o projeto inteiro, compose e `.env`
   com os segredos. Depois do primeiro deploy, só Atualizar, Reiniciar, Parar e Iniciar.
4. **Restaurar snapshot ou backup da VPS também volta o `n8n` no tempo.** Só em último caso, combinado com o dono
   dele.

## Operações do dia a dia

| Quero | Como | Tempo |
|---|---|---|
| Publicar nova versão do backend ou do frontend | GitHub → `EnadeX_Infra` → Actions → *Imagens do EnadeX* → *Run workflow*. Quando ficar verde, **Atualizar** o projeto `enadex` (`VPS_updateProjectV1`) | CI ~10 min + 1–3 min |
| Voltar uma versão | Actions → *Promover versão* (imagem + sha anterior), depois **Atualizar** | ~2 min |
| Mostrar dados republicados no Supabase | **Reiniciar** o projeto (`VPS_restartProjectV1`): a API recarrega as bases e a borda esvazia o cache | 1–3 min |
| Trocar um segredo | Editar a variável no hPanel e **Atualizar**; só Reiniciar não aplica `.env` novo | 1–3 min |
| Tirar o site do ar | **Parar** o projeto (`VPS_stopProjectV1`); o `n8n` não é afetado | segundos |
| Ver o que está rodando | `VPS_getProjectContainersV1` (estado e health), `VPS_getProjectLogsV1`, `VPS_getMetricsV1` | — |

- **Atualizar** baixa as imagens `:main` e recria os containers que mudaram, inclusive por `.env` novo.
- **Reiniciar** para e sobe os mesmos containers, sem baixar imagem nem aplicar `.env`.

As versões publicadas ficam em https://github.com/orgs/EnadeX/packages; a tag é o sha de 12 caracteres da fonte. Para
fixar uma versão sem o *Promover*, defina `API_TAG`, `WEB_TAG` ou `EDGE_TAG` no hPanel e Atualize.

## Primeiro deploy

Pré-requisitos:

- [ ] Paulo: chave de serviço antiga revogada e `REVOKE` da `truncar_tabela` aplicado (`COMUNICADO_SEGURANCA.md`).
- [ ] CI verde nas 3 imagens.
- [ ] Os 3 pacotes do GHCR públicos (pacote → *Package settings* → *Change visibility* → *Public*), para a VPS
      baixar sem login.
- [ ] Snapshot da VPS (`VPS_createSnapshotV1`). A Hostinger guarda um só, e um novo substitui o anterior.
- [ ] Linha de base do `n8n`: healthz 200 e containers `Up`.

Passos:

1. **DNS** (zona `enadex.org`, `DNS_updateDNSRecordsV1`):

   | Nome | Tipo | Valor | TTL |
   |---|---|---|---|
   | `@` | A | `187.127.29.195` (substitui o estacionamento `2.57.91.91`) | 300 |
   | `@` | AAAA | `2a02:4780:6e:f18a::1` (o Traefik da VPS responde por IPv6; verificado em 04/11/2026) | 300 |
   | `api` | CNAME | `enadex.org` | 300 |
   | `www` | CNAME | `enadex.org` (já existe) | — |
   | `@` | CAA | `0 issue "letsencrypt.org"` | 3600 |

   Espere a propagação **antes** do passo 2, para o Let's Encrypt validar na primeira tentativa:
   `nslookup enadex.org 1.1.1.1`, `nslookup enadex.org 8.8.8.8` e `nslookup api.enadex.org 1.1.1.1` devem responder
   `187.127.29.195`. Depois de 24 h estável, suba o TTL para 3600.
2. **Criar o projeto** `enadex` com o conteúdo de `deploy/docker-compose.yml` e as variáveis de
   `deploy/.env.example` (tags `main`, `SUPABASE_URL` com a referência do projeto, segredos vazios).
3. **Segredos:** o responsável preenche no hPanel; a lista está na seção *Segredos*.
4. **Atualizar** o projeto: aplica o `.env` e recria os containers.
5. **Acompanhar** com `VPS_getProjectContainersV1` até os três ficarem `healthy`. A API leva 1–3 min, porque carrega
   as bases e aquece o cache. Nos logs da `api`, o aquecimento imprime `status tempo rota`.
6. **Verificar** (próxima seção) e conferir o `n8n` de novo: healthz 200 e containers `Up`.

## Verificação

```sh
curl -sI https://enadex.org/ | head -n 1                                    # HTTP/2 200
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' https://www.enadex.org/enade-time   # 301 → https://enadex.org/enade-time
curl -s https://enadex.org/api/health                                       # {"status":"ok"}
curl -s https://enadex.org/api/enade-time/health                            # "fonte": "supabase"
curl -s -o /dev/null -w '%{http_code} %{size_download} B\n' https://enadex.org/api/multienade/relatorio-regressao
curl -s -o /dev/null -w '%{http_code} %{size_download} B\n' https://enadex.org/api/educluster/cursos
curl -sI https://enadex.org/api/educluster/areas | grep -i x-cache          # MISS na 1ª vez, HIT depois
curl -sI -H 'Accept-Encoding: br' https://enadex.org/ | grep -iE 'content-encoding|strict-transport'

# Bloqueios (403) e limite de taxa (deve aparecer 429)
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://enadex.org/api/multienade/reprocessar/teste
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://enadex.org/api/e-xplainenade/dataset/refresh
curl -s -o /dev/null -w '%{http_code}\n' 'https://enadex.org/api/educluster/areas?forcar=true'
seq 1 120 | xargs -P 60 -I{} curl -s -o /dev/null -w '%{http_code}\n' https://enadex.org/api/health | sort | uniq -c

# Tempo até o primeiro byte. Metas: HTML < 200 ms; GET de API em cache < 100 ms
curl -s -o /dev/null -w 'TTFB %{time_starttransfer}s\n' https://enadex.org/
curl -s -o /dev/null -w 'TTFB %{time_starttransfer}s\n' https://enadex.org/api/educluster/areas
```

- As duas rotas de dados (MultiENADE e EduCluster) devem voltar 200 com mais de 200 B: é a prova de que a chave de
  serviço chegou ao container. No MultiENADE, um erro chega como HTTP 200 com `{"erro": ...}` curto.
- Suíte e2e do ENADE-Time contra produção (no repositório do backend):

  ```sh
  cd enade_time/tools/e2e_frontend
  BASE_URL=https://enadex.org API_URL=https://enadex.org/api/enade-time npm run funcional
  BASE_URL=https://enadex.org API_URL=https://enadex.org/api/enade-time npm run acessibilidade
  ```

  A `degradacao` derruba o Postgres local e não se aplica à produção.

## Segredos

| Variável | O que é | Quem fornece |
|---|---|---|
| `SUPABASE_URL` | Referência do projeto Supabase, sem `https://` nem `.supabase.co`. Não é segredo, mas fica fora deste repositório público | Paulo |
| `SUPABASE_KEY` | Chave de serviço. As tabelas do MultiENADE, do EduCluster e do E-XplainENADE têm RLS sem policy | Paulo |
| `ENADE_TIME_DB_URL` | DSN do papel somente leitura `enade_time_reader` pelo Session Pooler (porta 5432) | Lucas |
| `EXPLAINENADE_REFRESH_TOKEN` | Token aleatório da recarga do E-XplainENADE (a rota fica bloqueada na borda de qualquer forma) | gerar: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `GEMINI_API_KEY` | Descrições automáticas do EduCluster; cada texto é gerado uma vez e guardado no volume | responsável pelo EduCluster |

**Rotação:** cole o valor novo no hPanel, Atualize e verifique as rotas de dados. Só então revogue o antigo.

O CI usa um segredo próprio, `FRONTEND_REPO_TOKEN`: token fine-grained só com *Contents: read* no repositório do
frontend. Ele expira na data escolhida ao criá-lo; renove antes disso, ou o job `web` falha no checkout.

## Caches e dados

- **Borda (nginx, em memória):**
  - todo `GET /api/*` fica em cache por 10 min; a estabilidade do EduCluster, por 60 min; os `/health`, por 15 s;
  - só respostas HTTP 200 entram no cache, e as respostas curtas do MultiENADE (erro com HTTP 200) ficam de fora;
  - Reiniciar o projeto esvazia o cache.
- **API:** as bases ficam em memória, sem validade por tempo, e são recarregadas a cada partida pelo aquecimento
  (`api/warmup.py`). Dados novos no Supabase aparecem depois de Reiniciar.
- **Volume `educluster_cache`:** descrições por IA do EduCluster. Sobrevive a deploys. Apagá-lo obriga a gerar tudo de
  novo, com custo no Gemini.

## Rotas bloqueadas na borda

| Rota | Por quê | Como fazer o que ela fazia |
|---|---|---|
| `POST /api/multienade/reprocessar/*` | Retreina modelos e trunca/regrava tabelas com a chave de serviço, sem autenticação | Rodar o reprocessamento fora da produção (máquina do grupo) e depois Reiniciar |
| `POST /api/e-xplainenade/dataset/refresh` | Recarrega as 13 tabelas do módulo | Reiniciar o projeto faz o mesmo |
| `?forcar=true` nas descrições do EduCluster | Uma chamada paga ao Gemini a cada acesso | As descrições se renovam sozinhas quando os dados (o contexto) mudam |

## Limites que protegem o projeto vizinho

| Serviço | CPU | Memória | Observação |
|---|---|---|---|
| api | 1,5 | 3 GB | `oom_score_adj` 500: em falta de memória, o kernel encerra a API antes do `n8n` |
| web | 0,5 | 512 MB | — |
| edge | 0,5 | 256 MB | Cache em tmpfs de até 256 MB |

- Logs em json-file, até 10 MB × 3 arquivos por container.
- Metas 24 h depois de cada mudança grande (`VPS_getMetricsV1`): CPU média < 30 % e RAM < 5 GB.

## Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| 404 do Traefik em `enadex.org` | Borda fora do ar ou fora da rede `n8n_default` | `VPS_getProjectContainersV1`: a `edge` está `Up`? Os logs dela mostram as requisições? |
| Certificado inválido (`TRAEFIK DEFAULT CERT`) | DNS ainda não propagado quando o Traefik pediu o certificado | Conferir os `nslookup` e Reiniciar o projeto: o Traefik relê os rótulos e pede de novo |
| 502 ou 504 em `/api` | API reiniciando ou aquecendo | Aguardar `healthy`; ver os logs da `api` |
| 503 em `/api/enade-time/*` | DSN do leitor errado ou Supabase pausado | Conferir `ENADE_TIME_DB_URL`; ver o painel do Supabase |
| `{"erro": ...}` no MultiENADE ou 500 no EduCluster | Chave de serviço inválida ou revogada | Conferir `SUPABASE_KEY` no hPanel e Atualizar |
| 429 para visitante legítimo | Limite por IP baixo para o uso real | Ajustar `limit_req` em `edge/nginx.conf`, publicar a borda e Atualizar |
| Supabase pausado | O plano gratuito pausa após 7 dias sem uso | O Paulo reativa no painel; o tráfego do site evita a pausa |
