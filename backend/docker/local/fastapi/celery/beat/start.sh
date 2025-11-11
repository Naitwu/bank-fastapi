#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

cd /src
exec watchfiles --filter python celery.__main__.main backend --args '-A backend.app.core.celery_app beat -l INFO'