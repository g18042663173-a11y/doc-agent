FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LLM_PROVIDER=stub \
    PPT_RENDERER=stub \
    PPT_COMPLIANCE_GATE=warn \
    USE_LANGGRAPH=false \
    DATA_DIR=/app/data \
    OUTPUT_DIR=/app/outputs \
    LOG_DIR=/app/data/logs

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY doc_agent ./doc_agent
COPY templates ./templates
COPY examples ./examples
COPY .env.example README.md ./

RUN mkdir -p /app/data /app/outputs

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
