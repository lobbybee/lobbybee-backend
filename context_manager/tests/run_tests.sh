#!/bin/bash
# Test runner script for context_manager tests

echo "Running Context Manager Tests"
echo "============================="

# Navigate to project root
cd /home/darkwebplayer/Documents/Infywork/CRMHotel/lobbybee-backend

# Run tests for the context_manager app
poetry run python manage.py test context_manager

echo ""
echo "Tests completed."
