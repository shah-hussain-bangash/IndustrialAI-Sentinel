FROM node:24-alpine AS frontend
WORKDIR /app
RUN npm install -g pnpm@11.25.0
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY index.html tsconfig.json vite.config.ts ./
COPY public ./public
COPY src ./src
RUN pnpm build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SENTINEL_DATA_DIR=/app/data
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt && useradd -m sentinel
COPY backend ./backend
COPY scripts ./scripts
COPY migrations ./migrations
COPY alembic.ini ./
COPY --from=frontend /app/dist ./dist
RUN mkdir -p /app/data && chown -R sentinel:sentinel /app
USER sentinel
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
