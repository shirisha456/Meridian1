FROM python:3.12-slim

WORKDIR /app

COPY libs/events /libs/events
RUN pip install --no-cache-dir /libs/events

COPY services/anomaly-service/pyproject.toml ./pyproject.toml
COPY services/anomaly-service/app ./app
RUN pip install --no-cache-dir .

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8081/health', timeout=2)" || exit 1

CMD ["python", "-m", "app.main"]
