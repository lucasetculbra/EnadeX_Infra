# Borda do EnadeX: nginx com cache de API, bloqueios e limite de taxa (configuração em edge/nginx.conf).
# nginx >= 1.27.3: `server ... resolve` nos upstreams (reresolve api/web quando os containers são recriados).
FROM nginx:1.29-alpine
COPY edge/nginx.conf /etc/nginx/nginx.conf
RUN mkdir -p /var/cache/nginx/api
EXPOSE 8080
