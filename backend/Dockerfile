FROM python:3.11-slim-bookworm

WORKDIR /app

# System deps for psycopg / lxml.
# Pinned to Debian bookworm above (rather than floating to whatever
# python:3.11-slim currently resolves to) because the newer trixie release
# has had intermittent package-mirror hash mismatches. The retry below is
# extra insurance against a transient bad mirror hit either way.
RUN apt-get update && apt-get install -y --no-install-recommends \
    -o Acquire::Retries=3 \
    build-essential \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Invoked via `sh` rather than as an executable because docker-compose.yml
# bind-mounts ./backend over /app at runtime — that masks any build-time
# `chmod +x`, and Windows hosts don't carry a Unix execute bit at all, so
# ENTRYPOINT ["./docker-entrypoint.dev.sh"] would fail with "permission
# denied" there.
ENTRYPOINT ["sh", "./docker-entrypoint.dev.sh"]
