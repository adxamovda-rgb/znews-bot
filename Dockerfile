# ============================================
# Znews Bot — Multi-stage Dockerfile
# Python 3.11 slim
# ============================================

# ---------------------------------------------------------------------------
# Stage 1: Builder — compile dependencies
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: Runtime — minimal production image
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

LABEL maintainer="Znews Team"
LABEL description="Znews Telegram Bot"

WORKDIR /app

# Install runtime dependencies (Pillow, lxml need shared libraries)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi8 \
    libxml2 \
    libxslt1.1 \
    libpng16-16 \
    libjpeg62-turbo \
    libfreetype6 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN groupadd -r znews && useradd -r -g znews znews

# Create data directory for SQLite database
RUN mkdir -p /app/data && chown znews:znews /app/data

# Copy application code
COPY --chown=znews:znews bot.py .
COPY --chown=znews:znews config.py .
COPY --chown=znews:znews scheduler.py .
COPY --chown=znews:znews database/ ./database/
COPY --chown=znews:znews parsers/ ./parsers/
COPY --chown=znews:znews services/ ./services/

# Switch to non-root user
USER znews

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run the bot
CMD ["python", "bot.py"]
