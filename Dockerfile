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
# Space). laya is pinned exactly to the version TSD-005 wraps and the
# calibration was fit against: 0.3.26's classifier calls
# torch.is_autocast_enabled(device), which needs torch >= 2.4, and broke
# every classify call on torch 2.2.2 [measured on the first live local
# run]. Bumping laya is a deliberate change that re-runs the calibration
# and the deployment smoke check, not a floating range.
RUN pip install --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    "anyio>=4.15.1" \
    "boto3>=1.43.108" \
    "duckdb>=1.5.6" \
    "fastapi>=0.115" \
    "httpx>=0.28,<1" \
    "langgraph>=1.2.12" \
    "langgraph-checkpoint-sqlite>=3.1.1" \
    "laya==0.3.24" \
    "mcp>=2.2.0" \
    "numpy>=1.26,<2" \
    "pydantic>=2.7,<3" \
    "python-dotenv>=1.2.4" \
    "pyyaml>=6.0.3" \
    "uvicorn>=0.30"

# Bake the multilingual checkpoint into the image at build time; the preload
# at startup then only loads weights that are already on disk.
COPY src ./src
COPY policy ./policy
COPY playbooks ./playbooks
COPY prompts ./prompts
COPY rubrics ./rubrics
# The synthetic bank fixture the hub's tools serve (TSD-010); the API's
# default path resolves it relative to the package, as in development.
COPY tests/fixtures/bank/synthetic_bank.json ./tests/fixtures/bank/synthetic_bank.json
RUN python -c "from laya import Router; Router().preload(['multilingual'])"

RUN chown -R calvino:calvino /app /data /opt/calvino

USER calvino
EXPOSE 7860

CMD ["uvicorn", "calvino.api.server:app", "--host", "0.0.0.0", "--port", "7860"]
