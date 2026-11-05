# syntax=docker/dockerfile:1.7
# Imagem do frontend do EnadeX (Next.js, saída standalone). Contexto de build: raiz do EnadeX_Infra, com o frontend
# em ./frontend (o CI faz o checkout do repositório privado com um token só de leitura).
FROM node:22-alpine AS build
RUN apk add --no-cache libc6-compat
WORKDIR /src
ENV NEXT_TELEMETRY_DISABLED=1 \
    npm_config_update_notifier=false

# Dependências primeiro (camada cacheada enquanto o lockfile não muda). O pnpm é a versão declarada no campo
# packageManager do package.json, instalada pelo npm (o Corepack do Node 22 valida assinaturas com chaves embutidas e
# quebra o build quando o registro troca de chave). node-linker hoisted: node_modules sem links simbólicos, como o npm.
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN npm install -g "$(node -p "require('./package.json').packageManager.split('+')[0]")" \
 && pnpm install --frozen-lockfile --node-linker=hoisted

COPY frontend/ ./
# A configuração do repositório vira next.config.repo.mjs e é estendida pela de deploy (standalone, sem compressão
# no Node, sem x-powered-by), sem editar o repositório do frontend.
RUN mv next.config.mjs next.config.repo.mjs
COPY web/next.config.deploy.mjs ./next.config.mjs

# As NEXT_PUBLIC_* são embutidas no bundle durante o build. Site e API na mesma origem (o edge roteia /api).
ARG SITE_URL=https://enadex.org
ENV NEXT_PUBLIC_API_URL=${SITE_URL} \
    NEXT_PUBLIC_EXPLAIN_API_URL=${SITE_URL} \
    NEXT_PUBLIC_EDUCLUSTER_API_URL=${SITE_URL} \
    NEXT_PUBLIC_ENADE_TIME_API_URL=${SITE_URL}
RUN pnpm build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
RUN addgroup -S app && adduser -S app -G app
COPY --from=build --chown=app:app /src/.next/standalone ./
COPY --from=build --chown=app:app /src/.next/static ./.next/static
COPY --from=build --chown=app:app /src/public ./public
USER app
EXPOSE 3000
CMD ["node", "server.js"]
