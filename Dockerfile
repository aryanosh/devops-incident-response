# ============================================================
# DevOps Incident Response Environment
# ============================================================

FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY server/requirements.txt ./requirements.txt

# Install deps
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# 🔥 CRITICAL FIX (THIS LINE FIXES YOUR ERROR)
ENV PYTHONPATH=/app/devops_incident_env

EXPOSE 8000

# Start server
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]