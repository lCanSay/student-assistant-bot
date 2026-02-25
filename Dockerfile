FROM python:3.11-slim

WORKDIR /app

# Force apt to use IPv4 only to prevent IPv6 hangs
RUN apt-get -o Acquire::ForceIPv4=true update && \
    apt-get -o Acquire::ForceIPv4=true install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Prevent pip from hanging on flaky networks
ENV PIP_DEFAULT_TIMEOUT=100

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-base')"

# Run model from local cache at runtime — no network calls to HuggingFace
ENV TRANSFORMERS_OFFLINE=1
ENV HF_HUB_OFFLINE=1

COPY . .