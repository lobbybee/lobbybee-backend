# Use Python 3.12 as the base image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_NO_INTERACTION=1
ENV POETRY_VIRTUALENVS_CREATE=false
ENV POETRY_CACHE_DIR='/var/cache/pypoetry'

# Set work directory
WORKDIR /app

# Install system dependencies, including poetry and zbar
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    zbar-tools \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install poetry

# Copy poetry dependency files
COPY poetry.lock pyproject.toml ./

# Install dependencies using poetry
# --only=main: Install only main dependencies, not dev dependencies
RUN poetry install --no-root --only=main

# Copy project files
COPY . .

# Collect static files (only if DJANGO_SETTINGS_MODULE is set or settings configured)
ENV DISABLE_S3_DURING_BUILD=true
RUN python manage.py collectstatic --noinput
ENV DISABLE_S3_DURING_BUILD=

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Run the application
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "lobbybee.asgi:application"]
