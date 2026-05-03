FROM python:3.11-slim

# System deps for Whisper + audio + PDF
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Pre-download Whisper base model (runs at build time, faster startup)
RUN python -c "import whisper; whisper.load_model('base')" || true

# Expose port (for health check only — bot uses polling)
EXPOSE 8080

CMD ["python", "main.py"]
