# ============================================================
# DevOps Incident Response Environment
# OpenEnv Hackathon | Meta PyTorch 2026
# ============================================================

FROM python:3.11-slim

# Metadata
LABEL maintainer="aryanosh"
LABEL description="DevOps Incident Response RL Environment"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY server/requirements.txt ./requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project into container
COPY . .

# Set PYTHONPATH so imports work
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Health check (important for HF)
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start FastAPI server
CMD ["uvicorn", "devops_incident_env.server.app:app", "--host", "0.0.0.0", "--port", "8000"]