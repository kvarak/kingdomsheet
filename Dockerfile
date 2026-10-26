# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

FROM base AS test

COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt -r requirements-dev.txt

COPY . .

CMD ["sh", "-c", "ruff check . && ruff format --check . && python manage.py test"]

FROM base AS runtime

RUN useradd --system --uid 10001 --create-home app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

# collectstatic needs a SECRET_KEY to import settings. This dummy value is never used at runtime.
RUN DJANGO_SECRET_KEY=collectstatic-build-only python manage.py collectstatic --noinput

# Uploaded pictures live in a volume mounted here. The app user must be able to write to it.
ENV DJANGO_MEDIA_ROOT=/data/media
RUN mkdir -p /data/media && chown app:app /data/media

USER app

EXPOSE 8000

ENTRYPOINT ["sh", "docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--config", "gunicorn.conf.py"]
