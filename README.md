# Lobbybee Backend - Docker Setup

This project includes Docker configuration for running the Lobbybee Django application in a containerized environment with Celery for background tasks and Redis for message queuing.

## Prerequisites

- Docker
- Docker Compose

## Quick Start (Development)

1. Clone the repository
2. Copy `.env.example` to `.env` and adjust the values as needed:
   ```bash
   cp .env.example .env
   ```
3. For AWS integration, set the following variables in your `.env` file:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_STORAGE_BUCKET_NAME`
   - `AWS_DEFAULT_REGION`
4. Build and run the containers:
   ```bash
   docker-compose up --build
   ```

The application will be available at `http://localhost:8000`

## Production Deployment

For production deployment, use the production docker-compose file:

```bash
docker-compose -f docker-compose.prod.yml up --build
```

This will start all services including Nginx as a reverse proxy.

### Production Environment Variables

For production, you should set the following environment variables in your `.env` file:
- `SECRET_KEY` - Django secret key
- `DEBUG` - Set to False
- `ALLOWED_HOSTS` - Comma-separated list of allowed hosts
- `DATABASE_URL` - PostgreSQL database URL
- `AWS_ACCESS_KEY_ID` - AWS access key for S3
- `AWS_SECRET_ACCESS_KEY` - AWS secret key for S3
- `AWS_STORAGE_BUCKET_NAME` - S3 bucket name
- `AWS_DEFAULT_REGION` - AWS region
- `EMAIL_HOST` - SMTP server
- `EMAIL_PORT` - SMTP port
- `EMAIL_HOST_USER` - SMTP username
- `EMAIL_HOST_PASSWORD` - SMTP password
- `DEFAULT_FROM_EMAIL` - Default from email address

## Services

- `web`: Django application
- `db`: PostgreSQL database
- `redis`: Redis for Celery message broker
- `celery`: Celery worker for background tasks
- `celery-beat`: Celery scheduler for periodic tasks
- `nginx`: Nginx reverse proxy (production only)

## Development

For development, the project uses volume mapping to allow live code changes without rebuilding the container.

## Running Management Commands

To run Django management commands, use:
```bash
docker-compose run --rm web python manage.py [command]
```

Examples:
```bash
# Create migrations
docker-compose run --rm web python manage.py makemigrations

# Apply migrations
docker-compose run --rm web python manage.py migrate

# Create a superuser
docker-compose run --rm web python manage.py createsuperuser
```

## Running Celery Commands

To run Celery commands, use:
```bash
# Run a Celery worker
docker-compose run --rm celery celery -A lobbybee worker --loglevel=info

# Run the Celery beat scheduler
docker-compose run --rm celery-beat celery -A lobbybee beat --loglevel=info
```

## Testing Celery

To test the Celery setup, you can use the provided management command:
```bash
docker-compose run --rm web python manage.py test_celery
```