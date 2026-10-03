FROM node:22-alpine AS web-build
WORKDIR /web
COPY web/package.json ./package.json
RUN npm install --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEB_DIST_DIR=/app/web/dist
WORKDIR /app
COPY server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY server/app ./app
COPY server/alembic.ini ./alembic.ini
COPY server/alembic ./alembic
COPY server/migrate_database.py ./migrate_database.py
COPY --from=web-build /web/dist /app/web/dist
RUN mkdir -p /app/data
EXPOSE 8000
CMD ["sh", "-c", "python migrate_database.py && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
