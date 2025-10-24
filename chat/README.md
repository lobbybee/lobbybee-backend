# LobbyBee Chat System

A real-time WebSocket-based chat system for hotel staff-guest communication in the LobbyBee Hotel CRM.

## Overview

The chat system enables bidirectional communication between hotel guests and department staff through:
- **Guest Webhook**: External applications send messages via HTTP webhook
- **WebSocket Connections**: Real-time messaging for hotel staff
- **Department-based Routing**: Messages routed to appropriate hotel departments

## Architecture

### Core Components

1. **Models** (`models.py`)
   - `Conversation`: Links guest, hotel, and department
   - `Message`: Individual messages with sender tracking
   - `ConversationParticipant`: Staff participation tracking

2. **WebSocket Consumers** (`consumers.py`)
   - `ChatConsumer`: Department staff connections
   - `GuestChatConsumer`: Guest connections for receiving messages

3. **API Views** (`views.py`)
   - Guest webhook endpoint for incoming messages
   - Conversation management APIs
   - Message read status and typing indicators

4. **Serializers** (`serializers.py`)
   - Data serialization for API responses
   - WebSocket message formatting

## Features

### Guest-to-Staff Communication
- Guests send messages via webhook using WhatsApp number
- Automatic conversation creation with Reception department
- Active stay validation required
- Real-time delivery to department staff

### Staff-to-Guest Communication
- Department staff send messages via WebSocket
- Message broadcasting to guest groups
- Read status tracking
- Typing indicators

### Department Management
- Support for multiple departments: Reception, Housekeeping, Room Service, Café, Management
- Staff access based on department assignment
- Group-based message routing

## API Endpoints

### Guest Webhook
```
POST /api/chat/guest-webhook/
```
**Request Body:**
```json
{
  "whatsapp_number": "+1234567890",
  "message": "I need help with my room",
  "message_type": "text",
  "media_url": "optional_url",
  "media_filename": "optional_filename"
}
```

### Conversation Management
```
GET /api/chat/conversations/                    # List conversations
POST /api/chat/conversations/create/             # Create conversation
GET /api/chat/conversations/{id}/               # Get conversation details
POST /api/chat/messages/mark-read/               # Mark messages as read
POST /api/chat/messages/typing/                 # Send typing indicator
```

## WebSocket Connections

### Department Staff
```
ws://host/ws/chat/{department_name}/
```
**Authentication:** JWT token required
**Departments:** Reception, Housekeeping, Room Service, Café, Management

### Guest Connections
```
ws://host/ws/guest/{whatsapp_number}/
```
**Authentication:** None (validated via WhatsApp number and active stay)

## WebSocket Message Format

### Staff Message
```json
{
  "type": "text",
  "conversation_id": 1,
  "content": "Hello! How can I help you?",
  "message_type": "text"
}
```

### Typing Indicator
```json
{
  "type": "typing",
  "conversation_id": 1,
  "is_typing": true
}
```

### Mark as Read
```json
{
  "type": "mark_read",
  "conversation_id": 1
}
```

## Database Schema

### Conversation Model
- `guest`: Foreign key to Guest model
- `hotel`: Foreign key to Hotel model  
- `department`: Foreign key to Department model
- `status`: active, closed, archived
- `last_message_at`: Timestamp of last message
- `last_message_preview`: Preview of last message

### Message Model
- `conversation`: Foreign key to Conversation
- `sender_type`: guest or staff
- `sender`: Foreign key to User (staff only)
- `message_type`: text, image, document, system
- `content`: Message content
- `is_read`: Read status flag

### ConversationParticipant Model
- `conversation`: Foreign key to Conversation
- `staff`: Foreign key to User
- `is_active`: Participation status
- `last_read_at`: Last read timestamp

## Security Features

### Authentication
- JWT-based authentication for staff
- Department access validation
- Guest validation via active stay

### Authorization
- Role-based access control
- Department-specific permissions
- Hotel-level isolation

## Configuration

### Redis Settings
```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}
```

### ASGI Application
```python
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
    ),
})
```

## Testing

Run tests with:
```bash
# Model tests
python manage.py test chat.tests.ChatModelTests

# API tests  
python manage.py test chat.tests.ChatAPITests

# All chat tests
python manage.py test chat
```

## Deployment Notes

### Requirements
- Redis server for channel layer
- ASGI server (Daphne/Uvicorn)
- WebSocket-enabled load balancer

### Environment Variables
- `REDIS_URL`: Redis connection string
- `DJANGO_SETTINGS_MODULE`: Settings module path

### Performance Considerations
- Use Redis cluster for high availability
- Implement connection pooling
- Monitor WebSocket connection limits
- Consider message archiving for long conversations

## Integration Examples

### Frontend JavaScript
```javascript
// Connect to department chat
const ws = new WebSocket('ws://localhost:8000/ws/chat/Reception/');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    if (data.type === 'message') {
        displayMessage(data.data);
    }
};

// Send message
ws.send(JSON.stringify({
    type: 'text',
    conversation_id: 1,
    content: 'Hello from staff!'
}));
```

### External Guest Application
```python
import requests

# Send message to guest webhook
response = requests.post('https://api.lobbybee.com/api/chat/guest-webhook/', {
    'whatsapp_number': '+1234567890',
    'message': 'I need room service',
    'message_type': 'text'
})
```

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failed**
   - Check Redis server status
   - Verify ASGI server configuration
   - Ensure proper authentication headers

2. **Messages Not Broadcasting**
   - Verify channel layer configuration
   - Check group naming consistency
   - Validate Redis connectivity

3. **Guest Webhook Errors**
   - Confirm guest has active stay
   - Verify WhatsApp number format
   - Check department availability

### Debug Mode
Enable debug logging:
```python
LOGGING = {
    'loggers': {
        'chat': {
            'handlers': ['console'],
            'level': 'DEBUG',
        }
    }
}
```

## Future Enhancements

- File/media sharing support
- Message reactions and emojis
- Conversation assignment and transfer
- Automated response templates
- Analytics and reporting
- Multi-language support
- Message encryption
- Offline message queuing