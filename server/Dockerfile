# server/Dockerfile
# ============================================================
# DevOps Incident Response Environment
# OpenEnv Hackathon | Meta PyTorch 2026
# ============================================================
FROM python:3.11-slim

# Metadata labels for HF Spaces
LABEL maintainer="your-username"
LABEL description="DevOps Incident Response RL Environment"

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (layer caching)
COPY server/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy the entire package into /app
COPY . /app/devops_incident_env/

# Set Python path so imports work
ENV PYTHONPATH=/app

# Health check - verify server is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

# Start the FastAPI server
CMD ["uvicorn", "devops_incident_env.server.app:app", "--host", "0.0.0.0", "--port", "8000"]