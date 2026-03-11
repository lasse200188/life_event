FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/pyproject.toml ./pyproject.toml
RUN pip install --no-cache-dir -e .

COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY workflows ./workflows
RUN ln -s /app/workflows /workflows
RUN groupadd -g 10001 app && useradd -u 10001 -g app -m -s /usr/sbin/nologin app
RUN chown -R app:app /app

USER app:app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
