# Use Python 3.12 as the base image
FROM python:3.12-slim

# Set environment variables
# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_NO_INTERACTION=1
ENV POETRY_VIRTUALENVS_CREATE=false
ENV POETRY_CACHE_DIR='/var/cache/pypoetry'

# Set work directory
WORKDIR /app

# Install system dependencies, including poetry and zbar
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev zbar-tools && rm -rf /var/lib/apt/lists/* && pip install poetry

# Copy poetry dependency files
COPY poetry.lock pyproject.toml ./

# Install dependencies using poetry
# --no-root: Do not install the project itself, only dependencies.
# --no-dev: Do not install development dependencies.
RUN poetry install --no-root --no-dev

# Copy project files
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
