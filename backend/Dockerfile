FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY backend/pyproject.toml ./pyproject.toml
COPY backend/README.md ./README.md
COPY backend/src ./src
COPY data ./data

RUN uv sync --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "alphalens.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
