# HackersBot - HackerNews Summary Web Server
# Multi-stage build for smaller final image

FROM python:3.10-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.10-slim

WORKDIR /app

# Create non-root user for security
RUN groupadd -r hackersbot && useradd -r -g hackersbot hackersbot

# Copy Python packages from builder
COPY --from=builder /root/.local /home/hackersbot/.local

# Make sure scripts in .local are usable
ENV PATH=/home/hackersbot/.local/bin:$PATH

# Copy application code
COPY src/ ./src/
COPY web/ ./web/
COPY summaries/ ./summaries/
COPY serve.py .

# Generate the summaries index at build time
RUN python web/generate_index.py

# Create output directory for runtime
RUN mkdir -p outputs && chown -R hackersbot:hackersbot /app

# Switch to non-root user
USER hackersbot

# Environment variables
ENV PORT=8000
ENV BIND_ADDRESS=0.0.0.0
ENV PYTHONUNBUFFERED=1

# Expose the port
EXPOSE 8000

# Health check - uses 127.0.0.1 which works when BIND_ADDRESS=0.0.0.0 (listens on all interfaces)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${PORT}/')" || exit 1

# Run the web server
CMD ["python", "serve.py"]

