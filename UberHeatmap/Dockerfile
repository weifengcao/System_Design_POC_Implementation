FROM python:3.11-slim

WORKDIR /app

# Copy repo subset
COPY UberHeatmap /app/UberHeatmap

# No external dependencies, but ensure UTF-8 locale
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 LANG=C.UTF-8

EXPOSE 8080

CMD ["python", "-m", "UberHeatmap.heatmap_server", "--port", "8080"]
