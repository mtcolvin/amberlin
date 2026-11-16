# syntax=docker/dockerfile:1
#
# Two images from one file, run together by compose.yaml:
#   api  - the FastAPI backend, holding the record in the /data volume
#   web  - nginx serving the built frontend and proxying /api/ to the backend
#
# Same origin through the proxy, so the browser needs no CORS and the backend is never
# published on a port of its own. The build context is filtered by an ALLOWLIST
# (.dockerignore): a real record living in this folder never reaches an image.

# ---------------------------------------------------------------- frontend build
FROM node:20-alpine AS web-build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# The browser reaches the backend through nginx at /api, on whatever host and port the
# user serves it from. A process env var wins over frontend/.env's dev value.
ENV VITE_API_BASE=/api
RUN npx vite build

# ---------------------------------------------------------------- web
FROM nginx:1.27-alpine AS web
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=web-build /src/frontend/dist /usr/share/nginx/html

# ---------------------------------------------------------------- api
FROM python:3.13-slim AS api
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HEALTH_DB=/data/health.db \
    HEALTH_IMAGING_DIR=/data/imaging_store \
    HEALTH_IMAGING_ARCHIVE=/data/imaging_archive \
    HEALTH_DOCUMENTS_DIR=/data/documents_store \
    GATEWAY_AUDIT_LOG=/data/gateway_audit.log
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py schema.sql ./
# All five stores in one volume. Created here, owned by the unprivileged user, so a fresh
# named volume inherits the right ownership on first mount.
RUN useradd --system --uid 10001 --home /app amberlin \
 && mkdir -p /data/imaging_store /data/imaging_archive /data/documents_store \
 && chown -R amberlin /data
USER amberlin
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/metrics', timeout=4)"
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
