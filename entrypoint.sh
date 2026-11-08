#!/bin/sh
set -e

for file in /iptv-api-config/*; do
  filename=$(basename "$file")
  target_file="$APP_WORKDIR/config/$filename"
  if [ ! -e "$target_file" ]; then
    cp -r "$file" "$target_file"
  fi
done

. $APP_WORKDIR/.venv/bin/activate

# Multiple processes share Docker stdout; use stable line-oriented progress there.
export IPTV_API_PLAIN_OUTPUT=1

: "${APP_PORT:=$APP_PORT}"
: "${NGINX_HTTP_PORT:=$NGINX_HTTP_PORT}"
: "${NGINX_RTMP_PORT:=$NGINX_RTMP_PORT}"
if [ -n "${SERVICE_PORT:-}" ]; then
  NGINX_HTTP_PORT="$SERVICE_PORT"
fi

if [ -f /proc/net/if_inet6 ]; then
  IPV6_HTTP_LISTEN="listen [::]:${NGINX_HTTP_PORT};"
else
  IPV6_HTTP_LISTEN=""
fi

sed -e "s/\${APP_PORT}/${APP_PORT}/g" \
    -e "s/\${NGINX_HTTP_PORT}/${NGINX_HTTP_PORT}/g" \
    -e "s/\${NGINX_RTMP_PORT}/${NGINX_RTMP_PORT}/g" \
    -e "s|\${IPV6_HTTP_LISTEN}|${IPV6_HTTP_LISTEN}|g" \
    /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

nginx -g 'daemon off;' &

python -u $APP_WORKDIR/main.py &

# Stream bookkeeping lives in this process, so keep a single worker and gain
# concurrency from threads: a viewer waiting on a stream start must not block
# every other request (see /hls_proxy).
exec env IPTV_API_SKIP_VERSION_CHECK=1 python -u -m gunicorn service.app:app \
  -b 127.0.0.1:$APP_PORT \
  --worker-class=gthread \
  --workers=1 \
  --threads="${GUNICORN_THREADS:-8}" \
  --timeout=60 \
  --graceful-timeout=10 \
  --access-logfile - \
  --error-logfile -
