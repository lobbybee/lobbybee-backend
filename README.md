# Lobbybee Backend - Docker Setup & Chat System

This project includes Docker configuration for running the Lobbybee Django application in a containerized environment with Celery for background tasks, Redis for message queuing, and a comprehensive real-time chat system.

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

- `web`: Django application with WebSocket support
- `db`: PostgreSQL database
- `redis`: Redis for Celery message broker and WebSocket channel layer
- `celery`: Celery worker for background tasks
- `celery-beat`: Celery scheduler for periodic tasks
- `nginx`: Nginx reverse proxy (production only)

## Chat System Overview

The Lobbybee backend includes a comprehensive real-time chat system that enables communication between hotel guests and staff across different departments. The system supports:

- **Real-time messaging** via WebSockets
- **Department-based chat routing** (Reception, Housekeeping, Room Service, Restaurant, Management)
- **Guest webhooks** for external messaging integration
- **Conversation management** with status tracking
- **Message types** (text, image, document, system)
- **Typing indicators** and read receipts
- **Media file support** with AWS S3 integration

### Chat System Architecture

The chat system consists of:
- **Models**: `Conversation`, `Message`, `ConversationParticipant`
- **WebSocket Consumers**: `ChatConsumer` (staff), `GuestChatConsumer` (guests)
- **API Views**: RESTful endpoints for conversation and message management
- **Serializers**: Data validation and serialization for different use cases

## WebSocket Endpoints

### Staff Chat Connection
```bash
ws://localhost:8000/ws/chat/<department_name>/
```

**Connection Requirements:**
- JWT authentication via query parameter or header
- User must be authenticated and have `user_type = 'department_staff'`
- User must belong to the specified department

**Example:**
```javascript
// Connect to Reception department chat
const ws = new WebSocket('ws://localhost:8000/ws/chat/reception/?token=YOUR_JWT_TOKEN');
```

### Guest Chat Connection
```bash
ws://localhost:8000/ws/guest/<whatsapp_number>/
```

**Connection Requirements:**
- Guest must exist in the database
- Guest must have an active stay at the hotel

**Example:**
```javascript
// Guest connects with their WhatsApp number
const ws = new WebSocket('ws://localhost:8000/ws/guest/+1234567890/');
```

## WebSocket Message Formats

### Staff Sending Messages
```json
{
  "type": "text",
  "conversation_id": 123,
  "content": "Hello! How can I help you today?"
}
```

### Typing Indicator
```json
{
  "type": "typing",
  "conversation_id": 123,
  "is_typing": true
}
```

### Mark Messages as Read
```json
{
  "type": "mark_read",
  "conversation_id": 123
}
```

### Incoming Message Format
```json
{
  "type": "message",
  "data": {
    "id": 456,
    "conversation_id": 123,
    "sender_type": "guest",
    "sender_name": "John Doe",
    "sender_id": null,
    "message_type": "text",
    "content": "I need help with my room",
    "is_read": false,
    "created_at": "2024-01-01T12:00:00Z",
    "guest_info": {
      "id": 789,
      "name": "John Doe",
      "whatsapp_number": "+1234567890",
      "room_number": "101"
    }
  }
}
```

## REST API Endpoints

### Guest Webhook (External Integration)
```http
POST /api/chat/guest-webhook/
Content-Type: application/json

{
  "whatsapp_number": "+1234567890",
  "message": "Hello, I need assistance",
  "message_type": "text",
  "department": "Reception",
  "conversation_id": 123
}
```

### Get Conversations
```http
GET /api/chat/conversations/
Authorization: Bearer <JWT_TOKEN>

Response:
[
  {
    "id": 123,
    "guest": 789,
    "hotel": 1,
    "department": "Reception",
    "status": "active",
    "guest_info": {
      "id": 789,
      "full_name": "John Doe",
      "whatsapp_number": "+1234567890"
    },
    "hotel_name": "Grand Hotel",
    "unread_count": 3,
    "last_message_at": "2024-01-01T12:00:00Z",
    "last_message_preview": "Hello, I need assistance",
    "created_at": "2024-01-01T10:00:00Z"
  }
]
```

### Get Conversation Details
```http
GET /api/chat/conversations/<conversation_id>/
Authorization: Bearer <JWT_TOKEN>

Response:
{
  "conversation": {
    "id": 123,
    "guest": 789,
    "hotel": 1,
    "department": "Reception",
    "status": "active"
  },
  "messages": [
    {
      "id": 456,
      "conversation": 123,
      "sender_type": "guest",
      "sender": null,
      "sender_name": "John Doe",
      "message_type": "text",
      "content": "Hello, I need assistance",
      "is_read": false,
      "time_ago": "2 minutes ago",
      "created_at": "2024-01-01T12:00:00Z"
    }
  ]
}
```

### Create New Conversation
```http
POST /api/chat/conversations/create/
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
  "guest_whatsapp_number": "+1234567890",
  "department_type": "Reception"
}
```

### Mark Messages as Read
```http
POST /api/chat/messages/mark-read/
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
  "conversation_id": 123,
  "message_ids": [456, 457]
}
```

### Send Typing Indicator
```http
POST /api/chat/messages/typing/
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
  "conversation_id": 123,
  "is_typing": true
}
```

## Chat Models

### Conversation
- Tracks conversations between guests and hotel departments
- Status: active, closed, archived
- Types: service, demo, checkin, checked_in, general
- Unique constraints prevent duplicate conversations

### Message
- Individual messages within conversations
- Sender types: guest, staff
- Message types: text, image, document, system
- Media support with AWS S3 integration
- Read status tracking

### ConversationParticipant
- Tracks which staff members participate in conversations
- Active status and read receipt tracking

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

# Run chat system tests
docker-compose run --rm web python manage.py test chat.tests
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

## Chat System Testing

The chat system includes comprehensive tests covering:
- WebSocket connections and authentication
- Message creation and broadcasting
- Department-based access control
- Guest webhook processing
- Conversation management
- Typing indicators and read receipts

To run chat-specific tests:
```bash
docker-compose run --rm web python manage.py test chat.tests
```

## WebSocket Authentication

The chat system uses JWT authentication for WebSocket connections. Include the JWT token as a query parameter:

```javascript
const token = 'your_jwt_token_here';
const ws = new WebSocket(`ws://localhost:8000/ws/chat/reception/?token=${token}`);
```

## Department Access Control

Staff users can only access chat rooms for departments they are assigned to. This is enforced both at the WebSocket connection level and API endpoint level through middleware and permission checks.

## Conversation Types and Routing

The system automatically determines conversation types based on guest status:
- `checkin`: Guests with pending checkin status
- `service`: Guests who are checked in
- `general`: Guests who have checked out
- `demo`: Special demo conversations for management department

Only `service` type conversations are broadcast to department staff in real-time. Other types are logged for later processing by reply systems.