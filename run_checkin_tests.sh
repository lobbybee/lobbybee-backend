#!/bin/bash
# Simple test runner for check-in flow with Poetry

echo "🏨 Check-in Flow Test Runner"
echo "============================"

# Check if Poetry is available
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry is not installed or not in PATH"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ pyproject.toml not found. Please run from project root."
    exit 1
fi

echo "✅ Poetry found and in project directory"

# Run AADHAR integration test
echo ""
echo "🔍 Running AADHAR QR extraction test..."
poetry run python chat/tests/test_aadhar_integration.py

# Run Django unit tests
echo ""
echo "🧪 Running Django unit tests..."
poetry run python manage.py test chat.tests.test_checkin_flow --verbosity=2

echo ""
echo "✅ Test run completed!"
echo ""
echo "💡 For individual test runs:"
echo "   poetry run python manage.py test chat.tests.test_checkin_flow.CheckinFlowTestCase"
echo "   poetry run python manage.py test chat.tests.test_checkin_flow.CheckinFlowIntegrationTestCase"