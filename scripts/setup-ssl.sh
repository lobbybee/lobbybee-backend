#!/bin/bash

# SSL Certificate Setup Script
# Run this once on the server to generate initial SSL certificates

set -e

echo "Setting up SSL certificates for backend.lobbybee.com..."

# Navigate to app directory
cd ~/app

# Start core services (without SSL)
echo "Starting core services..."
docker compose -f docker-compose.prod.yml up -d db redis web

# Wait for web service to be ready
echo "Waiting for web service..."
sleep 30

# Start nginx (for HTTP -> HTTPS redirect and ACME challenges)
echo "Starting nginx..."
docker compose -f docker-compose.prod.yml up -d nginx

# Generate SSL certificates
echo "Generating SSL certificates..."
docker compose -f docker-compose.prod.yml run --rm --entrypoint "\
  certbot certonly --webroot \
  --webroot-path=/var/www/certbot \
  --email admin@lobbybee.com \
  --agree-tos \
  --no-eff-email \
  -d backend.lobbybee.com" certbot

# Start all services including certbot for automatic renewal
echo "Starting all services with SSL..."
docker compose -f docker-compose.prod.yml up -d

# Verify certificates
echo "Verifying SSL certificates..."
docker compose -f docker-compose.prod.yml exec nginx ls -la /etc/letsencrypt/live/backend.lobbybee.com/

echo "SSL setup complete! Your certificates will be automatically renewed."
echo "You can now access https://backend.lobbybee.com"