# ── Stage: base Python image ──────────────────────────────────────────────────
# python:3.11-slim = Python 3.11 on Debian with minimal packages
# "slim" is important: full python image is ~900MB, slim is ~130MB
FROM python:3.11-slim

WORKDIR /app

# Install system-level dependencies
# These are needed by some Python packages (psycopg2, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# We will use pip directly to avoid network flakiness with uv binaries
# RUN pip install --default-timeout=1000 --no-cache-dir uv

# ── Copy dependency file BEFORE source code ────────────────────────────────────
# Why? Docker layer caching.
# If pyproject.toml hasn't changed, Docker reuses the cached install layer.
# This makes rebuilds fast when you only change app code, not dependencies.
COPY pyproject.toml .

# Create the minimal package structure needed for editable install
RUN mkdir -p app && touch app/__init__.py

# Install all dependencies into the system Python environment using pip
RUN pip install --default-timeout=1000 --no-cache-dir -e ".[dev]"

# ── Copy source code ────────────────────────────────────────────────────────
# This layer changes often (every code change), so it comes LAST
COPY . .

# The actual start command is specified in docker-compose.yml
# so we don't hardcode it here — same image, different commands
# for API vs worker
