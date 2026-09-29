FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt requirements.txt
RUN pip wheel --no-cache-dir --wheel-dir=/wheels \
    torch --index-url https://download.pytorch.org/whl/cpu
RUN pip wheel --no-cache-dir --wheel-dir=/wheels \
    -r requirements.txt --find-links=/wheels

FROM python:3.12-slim-bookworm

WORKDIR /app

COPY --from=builder /wheels /wheels
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir --no-index --find-links=/wheels \
    -r backend/requirements.txt \
    && rm -rf /wheels

COPY backend backend
RUN chmod +x backend/entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["backend/entrypoint.sh"]
