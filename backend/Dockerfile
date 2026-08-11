# syntax=docker/dockerfile:1
FROM python:3.14-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# libpq for psycopg; curl for the container health check; gettext because the
# project ships translations and without it `compilemessages` cannot run --- the
# catalogues stay uncompiled and every string falls back to English.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl gettext \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------- desarrollo
FROM base AS dev

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ /app/requirements/
RUN pip install -r requirements/dev.txt

COPY . /app/

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ---------------------------------------------------------------- producción
FROM base AS prod

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ /app/requirements/
RUN pip install -r requirements/prod.txt \
    && apt-get purge -y build-essential libpq-dev \
    && apt-get autoremove -y

COPY . /app/

# El proceso no corre como root.
RUN useradd --system --create-home --uid 1000 ott \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R ott:ott /app
USER ott

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
