# Single-service image (used by Render): builds the React app and serves it from FastAPI,
# so the site and API share one origin and auth cookies stay first-party.

FROM node:20-alpine AS frontend
WORKDIR /src
COPY shared ./shared
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci --no-audit --no-fund
COPY frontend ./frontend
RUN cd frontend && npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    SHARED_DIR=/app/shared STATIC_DIR=/app/static PORT=8000
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY shared ./shared
COPY --from=frontend /src/frontend/dist ./static
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
# Render's proxy is the only thing that can reach the container, so trust its forwarded headers.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips '*'"]
