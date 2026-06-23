# ── Stage: runtime ────────────────────────────────────────────────────────────
FROM python:3.13-slim


LABEL maintainer="ai-research-assistant"
LABEL description="Multi-Agent AI Research Assistant — FastAPI backend"

WORKDIR /app

# Install system dependencies (build-essential for some Python packages)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (maximise layer cache reuse)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code (respects .dockerignore)
COPY . .

# Create reports directory (PDF output destination)
RUN mkdir -p reports

# Expose the FastAPI port
EXPOSE 8080

# Health-check — GCP Cloud Run uses this to verify the service is up
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run FastAPI with uvicorn
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
