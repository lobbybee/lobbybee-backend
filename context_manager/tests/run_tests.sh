#!/bin/bash
# Test runner script for context_manager tests

echo "Running Context Manager Tests"
echo "============================="

# Navigate to project root
cd /home/darkwebplayer/Documents/Infywork/CRMHotel/lobbybee-backend

# Run tests
python -m context_manager.tests.runtests

echo ""
echo "Test Summary"
echo "============"
echo "Check context_manager/tests/TEST_SUMMARY.md for detailed results"
echo "Check conversationLog.md for conversation logs"