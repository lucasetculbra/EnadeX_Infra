#!/bin/sh
# Sobe a API única em UM processo: os caches em memória dos módulos (a base do EduCluster passa de 1 GB) não se
# duplicam e o aquecimento acontece uma vez só. Quedas ficam com o restart e o healthcheck do Docker.
set -eu

if [ "${WARMUP:-1}" = "1" ]; then
  python /opt/enadex/warmup.py &
fi

exec uvicorn api_main:app \
  --host 0.0.0.0 --port 8000 \
  --proxy-headers --forwarded-allow-ips '*' \
  --limit-concurrency "${API_LIMIT_CONCURRENCY:-64}" \
  --timeout-keep-alive 5 \
  --no-server-header
