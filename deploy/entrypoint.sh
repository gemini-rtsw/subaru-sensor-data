#!/bin/sh
# Entrypoint of the app image: pick the IOC or the web server.
set -e

case "${1:-web}" in
    ioc)
        cd /app/ioc
        exec python3 ioc_server.py
        ;;
    web)
        # The web server reads templates/ relative to the working directory.
        cd /app/web
        exec uvicorn web_server:app --host "${WEB_HOST:-0.0.0.0}" --port "${WEB_PORT:-8000}"
        ;;
    *)
        exec "$@"
        ;;
esac
