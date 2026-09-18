# Dockerfile for GridWise API Service
FROM python:3.12-slim

WORKDIR /app

# Prevent Python from writing pyc files to disc and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8050

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose service port
EXPOSE 8050

# Run uvicorn server binding to 0.0.0.0:8050
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8050"]
