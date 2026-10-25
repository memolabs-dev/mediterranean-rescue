# Production image: the API and the built frontend in one process (gunicorn + WhiteNoise).
# The same image runs the scheduled readers with another command (see deploy/compose.yaml).
# Local development keeps backend/Dockerfile and the Vite dev server.

FROM node:24-bookworm-slim AS frontend
WORKDIR /src/frontend
RUN npm install --global pnpm@12.10.1
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend ./
COPY contracts /src/contracts
RUN pnpm build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy \
    DJANGO_ENV=production FRONTEND_DIST=/app/frontend
RUN apt-get update && apt-get install -y --no-install-recommends libgdal32 libgeos-c1v5 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.12.22
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev
COPY backend ./backend
COPY contracts ./contracts
COPY --from=frontend /src/frontend/dist ./frontend
# Static files are collected at build time; settings demand real secrets, so throwaway values
# serve only this step and never reach the running container.
RUN DJANGO_SECRET_KEY=build-only-collectstatic-key-that-is-long-enough-for-the-check \
    DB_PASSWORD=unused uv run --no-sync python backend/manage.py collectstatic --noinput
RUN useradd --uid 10001 --create-home rescue && chown -R rescue:rescue /app
USER rescue
EXPOSE 8000
# The probe names the served host: Django refuses any Host outside DJANGO_ALLOWED_HOSTS.
HEALTHCHECK --interval=15s --timeout=5s --start-period=90s --start-interval=2s \
  CMD ["python", "-c", "import os, urllib.request as r; host = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost').split(',')[0]; r.urlopen(r.Request('http://127.0.0.1:8000/api/health/', headers={'Host': host}), timeout=4)"]
ENTRYPOINT ["backend/entrypoint.sh"]
CMD ["serve"]
