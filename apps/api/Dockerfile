FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir uv

COPY apps/api/pyproject.toml apps/api/uv.lock apps/api/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY apps/api/app ./app

EXPOSE 8000

CMD ["uv", "run", "--no-project", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
