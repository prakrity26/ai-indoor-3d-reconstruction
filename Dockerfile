# syntax=docker/dockerfile:1.7
#
# Two images from one file:
#   docker build --target api    -t indoor3d-api .     FastAPI + web platform (small, no ML)
#   docker build --target worker -t indoor3d-worker .  Phases 1–9 mesh pipeline on CPU
#
# The Gaussian-splat trainer needs CUDA + COLMAP and stays on a GPU host / Colab
# (see notebooks/). It is not built here.

ARG PYTHON_VERSION=3.10

# ---------------------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_DIR=/app/data \
    JOBS_DIR=/app/data/jobs \
    FRAMES_DIR=/app/data/frames \
    OUTPUT_DIR=/app/data/outputs \
    UPLOAD_DIR=/app/data/uploads
WORKDIR /app
RUN groupadd --system app && useradd --system --gid app --home /app --shell /usr/sbin/nologin app

# ---------------------------------------------------------------------------------------------
FROM base AS api
COPY pyproject.toml README.md ./
# Install dependencies first so code edits do not invalidate this layer.
RUN mkdir -p api ui model database queue shared \
 && pip install ".[api,db,queue]" \
 && pip uninstall -y ai-indoor-3d-reconstruction
COPY api ./api
COPY ui ./ui
COPY database ./database
COPY queue ./queue
COPY shared ./shared
COPY model/__init__.py ./model/__init__.py
COPY samples ./samples
RUN mkdir -p /app/data/jobs /app/data/frames /app/data/outputs /app/data/uploads \
 && chown -R app:app /app/data
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"
CMD ["python", "-m", "api"]

# ---------------------------------------------------------------------------------------------
FROM base AS worker
# Open3D and OpenCV need these shared libraries on slim images.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 libx11-6 \
 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
# CPU-only PyTorch keeps the image a few GB smaller than the default CUDA wheels.
RUN mkdir -p api ui model database queue shared \
 && pip install --extra-index-url https://download.pytorch.org/whl/cpu ".[depth,cloud,db,queue,api]" \
 && pip uninstall -y ai-indoor-3d-reconstruction
COPY model ./model
COPY database ./database
COPY queue ./queue
COPY shared ./shared
COPY api ./api
ENV HF_HOME=/app/.cache/huggingface \
    COMPUTE_DEVICE=cpu
RUN mkdir -p /app/data /app/.cache/huggingface && chown -R app:app /app/data /app/.cache
USER app
CMD ["python", "-m", "queue.workers", "--pipeline", "mesh"]
