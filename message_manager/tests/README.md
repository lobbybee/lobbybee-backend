# Message Manager Tests

This directory contains tests for the message_manager Django app.

## Test Files

1. `test_webhook.py` - Tests for the WhatsApp webhook endpoint
2. `test_conversation.py` - Tests for conversation flows
3. `test_demo.py` - Tests for demo conversations (work in progress)
4. `test_websocket.py` - Tests for WebSocket consumers
5. `test_websocket_utils.py` - Tests for WebSocket utility functions

## Running Tests

To run all tests:
```bash
poetry run python manage.py test message_manager.tests
```

To run specific test files:
```bash
poetry run python manage.py test message_manager.tests.test_webhook
poetry run python manage.py test message_manager.tests.test_conversation
poetry run python manage.py test message_manager.tests.test_websocket
poetry run python manage.py test message_manager.tests.test_websocket_utils
```

## Test Coverage

The tests verify:
- Webhook endpoint functionality
- Conversation creation for guests with stays
- Message processing through the webhook
- WebSocket consumer functionality
- WebSocket utility functions for department notifications