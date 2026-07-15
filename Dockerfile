# Multi-stage build for Futures Terminal
FROM python:3.11-slim AS builder
WORKDIR /app

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Final image
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies for GUI support (if headless, omit X11 libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxcb-xinerama0 libxkbcommon0 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m terminal
RUN chown -R terminal:terminal /app
USER terminal

# Entrypoint
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]