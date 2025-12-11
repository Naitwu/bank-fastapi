#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

exec /usr/local/bin/gunicorn backend.app.main:app \\
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --forwarded-allow-ips "*"