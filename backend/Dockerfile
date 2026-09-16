FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for lxml; removed from the final layer to keep the image small.
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libxml2-dev libxslt1-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && apt-get purge -y gcc && apt-get autoremove -y

COPY app ./app

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser \
 && mkdir -p /data/storage && chown -R appuser /data/storage
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
