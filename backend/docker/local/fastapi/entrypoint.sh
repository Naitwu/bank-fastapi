#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

python << END
import sys
import time
import psycopg

MAX_WAIT_TIME = 30
RETRY_INTERVAL = 3
start_time = time.time()

def check_database():
    try:
        psycopg.connect(
            dbname="${POSTGRES_DB}",
            user="${POSTGRES_USER}",
            password="${POSTGRES_PASSWORD}",
            host="${POSTGRES_HOST}",
            port="${POSTGRES_PORT}"
        )
        return True
    except psycopg.OperationalError as e:
        elapsed = int(time.time() - start_time)
        sys.stderr.write(f"Database connection attempt after {elapsed} seconds failed: {e}\n")
        return False

while True:
    if check_database():
        break
    if time.time() - start_time > MAX_WAIT_TIME:
        sys.stderr.write("Timed out waiting for the database. Exiting.\n")
        sys.exit(1)
    sys.stderr.write(f"Waiting for {RETRY_INTERVAL} seconds before retrying...\n")
    time.sleep(RETRY_INTERVAL)
END

echo >&2  'PostgreSQL is up - executing command'

alembic upgrade head

exec "$@"