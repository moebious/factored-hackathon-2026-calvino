# Calvino demo backend for a Hugging Face Space (TSD-003).
#
# - python:3.11-slim, non-root user, port 7860 (the port Spaces expect).
# - laya and the multilingual checkpoint are baked into the image at build
#   time (HF_HOME lives in the image), so a restart never re-downloads the
#   model and startup is just the in-memory preload.
# - State (decisions.jsonl, later the hub's checkpoints) lives on the
#   persistent storage mounted at /data, because the Space's own disk is
#   wiped on restart. The location is configuration (CALVINO_DATA_DIR).
# - The calvino package runs from src/ via PYTHONPATH instead of a wheel
#   install, so policy/v1.yaml resolves from the repository root exactly as
#   it does in development.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    HF_HOME=/opt/calvino/hf \
    CALVINO_DATA_DIR=/data

RUN useradd --create-home --uid 1000 calvino \
    && mkdir -p /app /data /opt/calvino/hf

WORKDIR /app

# Third-party dependencies only; laya pulls torch (CPU wheels are fine on a
# Space). Version floor matches what TSD-005 verified (laya 0.3.23/0.3.24).
RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn>=0.30" "laya>=0.3.23,<0.4"

# Bake the multilingual checkpoint into the image at build time; the preload
# at startup then only loads weights that are already on disk.
COPY src ./src
COPY policy ./policy
# The synthetic bank fixture the hub's tools serve (TSD-010); the API's
# default path resolves it relative to the package, as in development.
COPY tests/fixtures/bank/synthetic_bank.json ./tests/fixtures/bank/synthetic_bank.json
RUN python -c "from laya import Router; Router().preload(['multilingual'])"

RUN chown -R calvino:calvino /app /data /opt/calvino

USER calvino
EXPOSE 7860

CMD ["uvicorn", "calvino.api.server:app", "--host", "0.0.0.0", "--port", "7860"]
