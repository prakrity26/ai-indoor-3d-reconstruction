# syntax=docker/dockerfile:1.7
#
# Three images from one file:
#   docker build --target api        -t indoor3d-api .         the whole web app: FastAPI + web platform + walk viewer
#   docker build --target worker     -t indoor3d-worker .      Phases 1–9 mesh pipeline on CPU
#   docker build --target gpu-worker -t indoor3d-gpu-worker .  photoreal splats (COLMAP + Nerfstudio) on an NVIDIA GPU
#
# PostgreSQL and Redis run from their official images (see docker-compose.yml). The GPU worker
# can run next to the app (compose profile "gpu") or on a rented GPU (RunPod, Colab) that reaches
# the app through api.worker_gateway; see docs in README.md → "Photoreal splats".

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

# ---------------------------------------------------------------------------------------------
# Photoreal Gaussian splats: ffmpeg → COLMAP → Nerfstudio splatfacto → PLY, reported to the app
# through the worker gateway. Needs an NVIDIA GPU with ≥ 16 GB (RTX 4090 / A6000 / L4 / A100).
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04 AS gpu-worker
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    QT_QPA_PLATFORM=offscreen \
    # gsplat's CUDA kernels are compiled once at build time for these GPU generations
    # (T4 7.5, A100 8.0, A6000/3090 8.6, L4/4090 8.9, H100 9.0) instead of at every start.
    TORCH_CUDA_ARCH_LIST="7.5;8.0;8.6;8.9;9.0" \
    TORCH_EXTENSIONS_DIR=/opt/torch_extensions \
    MAX_JOBS=4 \
    SPLAT_BACKEND=splatfacto \
    SPLAT_NUM_FRAMES=300 \
    SPLAT_TRAIN_STEPS=30000 \
    SPLAT_MAX_SIDE=1600 \
    SPLAT_WORK_DIR=/work
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 python3-pip python3-dev git build-essential ninja-build \
      colmap ffmpeg libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/* \
 && ln -sf /usr/bin/python3 /usr/local/bin/python
RUN pip install torch==2.4.1 torchvision==0.19.1 --index-url https://download.pytorch.org/whl/cu124 \
 # Ubuntu ships blinker without pip metadata, which makes the nerfstudio install fail.
 && pip install --ignore-installed blinker \
 && pip install nerfstudio \
 && cd /tmp && python -c "from gsplat.cuda._backend import _C; print('gsplat kernels built')"
WORKDIR /app
COPY pyproject.toml README.md ./
COPY model ./model
COPY database ./database
COPY queue ./queue
COPY shared ./shared
COPY api ./api
RUN pip install --no-deps -e . && pip install httpx "sqlalchemy>=2" \
 && groupadd --system app && useradd --system --gid app --home /app --shell /usr/sbin/nologin app \
 && mkdir -p /work && chown -R app:app /work /opt/torch_extensions
USER app
# Needs WORKER_GATEWAY_URL and WORKER_TOKEN (the app's api.worker_gateway).
CMD ["python", "-m", "queue.workers", "--pipeline", "splat"]
