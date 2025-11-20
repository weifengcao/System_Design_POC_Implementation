FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (needed for some ML libs or postgres)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy configuration
COPY pyproject.toml poetry.lock* /app/

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Download Presidio models (en_core_web_lg is standard for PII)
RUN python -m spacy download en_core_web_lg

# Copy application code
COPY . /app

# Expose port
EXPOSE 8000

# Default command (can be overridden in compose)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
