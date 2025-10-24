# WebSocket API Documentation

## Chat System WebSocket Commands

### Connection
- **URL**: `ws://your-domain/ws/chat/`
- **Authentication**: User must be authenticated and have `user_type = 'department_staff'`
- **Auto-joined groups**: Users are automatically added to their department groups (`department_{department_name}`)

### Client → Server Commands

#### 1. Subscribe to Conversation
```json
{
  "type": "subscribe_conversation",
  "conversation_id": 123
}
```

#### 2. Unsubscribe from Conversation
```json
{
  "type": "unsubscribe_conversation", 
  "conversation_id": 123
}
```

#### 3. Send Text Message
```json
{
  "type": "text",
  "conversation_id": 123,
  "content": "Hello, how can I help you?"
}
```

#### 4. Mark Messages as Read
```json
{
  "type": "mark_read",
  "conversation_id": 123
}
```

#### 5. Typing Indicator
```json
{
  "type": "typing",
  "conversation_id": 123,
  "is_typing": true
}
```

#### 6. Close Conversation
```json
{
  "type": "close_conversation",
  "conversation_id": 123
}
```

### Server → Client Notifications

#### 1. New Message
```json
{
  "type": "message",
  "data": {
    "id": 456,
    "conversation_id": 123,
    "sender_type": "staff",
    "sender_name": "John Doe",
    "content": "Hello!",
    "created_at": "2024-01-01T12:00:00Z",
    "guest_info": {
      "id": 789,
      "name": "Guest Name",
      "room_number": "101"
    }
  }
}
```

#### 2. New Conversation Notification
```json
{
  "type": "new_conversation",
  "data": {
    "id": 123,
    "guest_name": "Guest Name",
    "department": "reception",
    "conversation_type": "general",
    "status": "active",
    "created_at": "2024-01-01T12:00:00Z",
    "last_message_preview": "Hello, I need help"
  }
}
```

#### 3. Conversation Update Notification
```json
{
  "type": "conversation_update",
  "data": {
    "type": "new_message",
    "data": {
      "conversation_id": 123,
      "guest_name": "Guest Name",
      "department": "reception",
      "last_message_preview": "Thank you!",
      "last_message_at": "2024-01-01T12:05:00Z",
      "message_from": "Guest Name"
    }
  }
}
```

#### 4. Conversation Closed
```json
{
  "type": "conversation_update",
  "data": {
    "type": "closed",
    "data": {
      "id": 123,
      "guest_name": "Guest Name",
      "department": "reception",
      "status": "closed",
      "updated_at": "2024-01-01T12:10:00Z"
    }
  }
}
```

#### 5. User Status Updates
```json
{
  "type": "user_status",
  "data": {
    "type": "user_connected",
    "user_id": 456,
    "user_name": "John Doe",
    "department": "reception"
  }
}
```

#### 6. Typing Indicator
```json
{
  "type": "typing",
  "data": {
    "conversation_id": 123,
    "user_id": 456,
    "user_name": "John Doe",
    "is_typing": true
  }
}
```

#### 7. Subscription Confirmations
```json
{
  "type": "subscribed",
  "data": {
    "conversation_id": 123,
    "message": "Successfully subscribed to conversation"
  }
}
```

```json
{
  "type": "unsubscribed",
  "data": {
    "conversation_id": 123,
    "message": "Successfully unsubscribed from conversation"
  }
}
```

#### 8. Error Messages
```json
{
  "type": "error",
  "message": "Error description"
}
```

## REST API Endpoints for WebSocket Integration

### Close Conversation
- **Endpoint**: `POST /chat/conversations/close/`
- **Body**: 
```json
{
  "conversation_id": 123
}
```
- **WebSocket Notification**: Sends `conversation_update` with type `closed` to relevant department members

### Create Conversation
- **Endpoint**: `POST /chat/conversations/create/`
- **WebSocket Notification**: Sends `new_conversation` notification to relevant department members

## Group Structure

### Department Groups
- Format: `department_{department_name}`
- All staff in a department automatically join these groups
- Used for department-wide notifications

### Conversation Groups
- Format: `conversation_{conversation_id}`
- Users manually subscribe/unsubscribe to these
- Used for conversation-specific real-time updates

### Guest Groups
- Format: `guest_{whatsapp_number}`
- Used for sending messages to specific guests

## Notification Logic

1. **New Messages**: 
   - Sent to conversation subscribers (conversation group)
   - Also sent to department members as conversation update notification

2. **New Conversations**: 
   - Sent to all connected staff in the relevant department

3. **Conversation Updates** (status changes, etc.):
   - Sent to all connected staff in the relevant department
   - Users subscribed to the conversation don't receive these (they get real-time updates anyway)

4. **User Status**: 
   - Sent to department members when users connect/disconnect