# Stage 1: Builder
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install build tools (needed only for compiling dependencies)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential \
#     && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN python -m pip install --upgrade pip

# Copy requirements first for caching
COPY requirements.txt .

# Install dependencies into /install (user site)
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copy the source code (if needed for build-time tasks)
COPY . .

# Stage 2: Minimal runtime
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Make run script executable and set entrypoint
RUN chmod +x run.sh
CMD ["./run.sh"]