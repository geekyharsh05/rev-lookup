# Build stage
FROM python:3.13.7-slim AS builder

# Copy UV binary
COPY --from=ghcr.io/astral-sh/uv:0.7.20 /uv /uvx /bin/

# Set UV cache directory
ENV UV_CACHE_DIR=/tmp/.uv-cache

# Install build dependencies
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies to a virtual environment
RUN uv sync --locked --no-dev

# Production stage
FROM python:3.13.7-slim AS production

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libnspr4 \
    libnss3 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxrender1 \
    libxshmfence1 \
    libxss1 \
    libxtst6 \
    lsb-release \
    xdg-utils \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Set Chrome environment variables
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER=/usr/bin/chromedriver

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy UV binary from builder stage
COPY --from=ghcr.io/astral-sh/uv:0.7.20 /uv /uvx /bin/

# Copy virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Set UV cache directory for runtime
ENV UV_CACHE_DIR=/app/.uv-cache

EXPOSE 8000

CMD ["/app/.venv/bin/uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
