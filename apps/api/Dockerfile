# syntax=docker/dockerfile:1
# PokeQuant API + data/ML core.
# Multi-stage build: builder installs deps, runtime is minimal + non-root.

# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# Install build tools.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into a virtualenv for clean copy.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# INSTALL_EXTRAS controls optional dependency groups.
#   ""          -> lightweight install (heuristic grader; fits Render free-tier RAM)
#   "[vision]"  -> include torch + torchvision for the CNN card-grader
# Default is lightweight; override with: --build-arg INSTALL_EXTRAS="[vision]"
ARG INSTALL_EXTRAS=""

COPY pyproject.toml README.md ./
COPY pokequant ./pokequant
RUN pip install --upgrade pip && pip install ".${INSTALL_EXTRAS}"

# =============================================================================
# Stage 2: Runtime (minimal, non-root)
# =============================================================================
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ARTIFACT_DIR=/data/artifacts \
    PATH="/opt/venv/bin:$PATH"

# Runtime system deps: libgomp1 (LightGBM), curl (healthchecks).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Copy application code.
COPY pyproject.toml README.md alembic.ini ./
COPY pokequant ./pokequant
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Create artifact directory and non-root user.
RUN useradd -r -m -s /bin/false appuser \
    && mkdir -p "$ARTIFACT_DIR" \
    && chown -R appuser:appuser "$ARTIFACT_DIR" /app /home/appuser

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=600s --retries=12 \
    CMD curl -fsS "http://localhost:${PORT:-8000}/health" || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
