# Backend image: trains nothing at build time. Model artifacts are produced by
# `python -m ml.train` and mounted or copied in, so the image stays small and
# the evaluation stays reproducible outside the container.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ml ./ml
COPY backend ./backend
COPY data ./data
COPY model_artifacts ./model_artifacts
COPY evaluation ./evaluation

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
