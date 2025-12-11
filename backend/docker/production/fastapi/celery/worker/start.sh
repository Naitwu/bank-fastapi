#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

cd /src
exec celery \
 -A backend.app.core.celery_app \
 worker \
 -l INFO
