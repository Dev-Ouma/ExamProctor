FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
RUN apt-get update && apt-get install -y --no-install-recommends curl libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY fetch_models.sh ./
RUN ./fetch_models.sh /app/models
COPY examproctor_service ./examproctor_service
RUN uv sync --frozen --no-dev
RUN useradd --system --uid 10001 app
USER app
ENV PATH=/opt/venv/bin:$PATH
EXPOSE 8000
CMD ["uvicorn", "examproctor_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
