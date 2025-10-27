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

#### 7. Acknowledgments
Acknowledgments are sent when client actions are successfully processed. They provide immediate feedback that operations completed successfully.

##### Message Received Acknowledgment
```json
{
  "type": "acknowledgment",
  "status": "received",
  "message_id": 456,
  "conversation_id": 123,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

##### Mark as Read Acknowledgment
```json
{
  "type": "acknowledgment",
  "status": "marked_read",
  "conversation_id": 123,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

##### Subscription Acknowledgment
```json
{
  "type": "acknowledgment",
  "status": "subscribed",
  "conversation_id": 123,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

##### Unsubscription Acknowledgment
```json
{
  "type": "acknowledgment",
  "status": "unsubscribed",
  "conversation_id": 123,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

##### Conversation Closed Acknowledgment
```json
{
  "type": "acknowledgment",
  "status": "conversation_closed",
  "conversation_id": 123,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

#### 8. Error Messages
```json
{
  "type": "error",
  "message": "Error description"
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

## Acknowledgment System

### How Acknowledgments Work

The acknowledgment system provides immediate feedback when client actions are successfully processed. This helps create a more responsive user experience and aids in debugging.

### Acknowledgment Flow

1. **Client sends action** → WebSocket message with specific type
2. **Server processes action** → Validates and executes the operation
3. **Server sends acknowledgment** → Confirms successful completion
4. **Server broadcasts updates** → Notifies other relevant users

### Frontend Implementation Guide

#### Quick Start - Basic Pattern
```javascript
// Store pending operations
const pendingOperations = new Map();

// Send message with tracking ID
function sendMessage(conversationId, content) {
  const messageId = Date.now().toString();
  const operationId = `msg_${messageId}`;
  
  // Store pending operation
  pendingOperations.set(operationId, {
    type: 'text',
    conversationId,
    content,
    timestamp: Date.now()
  });
  
  // Send to WebSocket
  websocket.send(JSON.stringify({
    type: 'text',
    conversation_id: conversationId,
    content: content
  }));
  
  // Show loading state
  showMessageStatus(messageId, 'sending');
}

// Handle acknowledgments
function handleAcknowledgment(data) {
  const { status, message_id, conversation_id } = data;
  
  if (status === 'received') {
    // Message was successfully processed
    showMessageStatus(message_id, 'sent');
    
    // Remove from pending after a delay
    setTimeout(() => {
      pendingOperations.delete(`msg_${messageId}`);
    }, 5000);
  }
}
```

#### React Hook Example
```javascript
function useWebSocketAcknowledgments() {
  const [pendingMessages, setPendingMessages] = useState(new Map());
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  
  useEffect(() => {
    const ws = new WebSocket('ws://your-domain/ws/chat/');
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'acknowledgment':
          handleAcknowledgment(data);
          break;
        case 'error':
          handleError(data);
          break;
        // ... other cases
      }
    };
    
    const handleAcknowledgment = (ack) => {
      setPendingMessages(prev => {
        const newPending = new Map(prev);
        
        switch (ack.status) {
          case 'received':
            // Mark message as sent
            updateMessageStatus(ack.message_id, 'sent');
            break;
          case 'marked_read':
            // Update conversation read status
            updateConversationReadStatus(ack.conversation_id);
            break;
          case 'subscribed':
            // Update subscription status
            updateSubscriptionStatus(ack.conversation_id, true);
            break;
          case 'unsubscribed':
            updateSubscriptionStatus(ack.conversation_id, false);
            break;
          case 'conversation_closed':
            updateConversationStatus(ack.conversation_id, 'closed');
            break;
        }
        
        return newPending;
      });
    };
    
    return () => ws.close();
  }, []);
  
  const sendMessage = useCallback((conversationId, content) => {
    const tempId = `temp_${Date.now()}`;
    
    // Add to pending messages
    setPendingMessages(prev => new Map(prev).set(tempId, {
      conversationId,
      content,
      status: 'sending'
    }));
    
    // Send via WebSocket
    websocket.send(JSON.stringify({
      type: 'text',
      conversation_id: conversationId,
      content: content
    }));
    
    return tempId;
  }, []);
  
  return { pendingMessages, sendMessage, connectionStatus };
}
```

#### Vue.js Example
```javascript
// WebSocket acknowledgment mixin
export default {
  data() {
    return {
      pendingOperations: {},
      acknowledgments: {}
    }
  },
  
  methods: {
    sendMessage(conversationId, content) {
      const tempId = `temp_${Date.now()}`;
      
      // Track pending operation
      this.$set(this.pendingOperations, tempId, {
        type: 'text',
        conversationId,
        content,
        status: 'sending',
        timestamp: Date.now()
      });
      
      // Send message
      this.$websocket.send(JSON.stringify({
        type: 'text',
        conversation_id: conversationId,
        content: content
      }));
      
      return tempId;
    },
    
    handleAcknowledgment(data) {
      const { status, message_id, conversation_id } = data;
      
      switch (status) {
        case 'received':
          this.$set(this.acknowledgments, message_id, {
            status: 'sent',
            timestamp: data.timestamp
          });
          break;
        case 'marked_read':
          this.$emit('conversation-read', conversation_id);
          break;
        case 'subscribed':
          this.$emit('conversation-subscribed', conversation_id);
          break;
        case 'unsubscribed':
          this.$emit('conversation-unsubscribed', conversation_id);
          break;
        case 'conversation_closed':
          this.$emit('conversation-closed', conversation_id);
          break;
      }
    }
  }
}
```

### Best Practices

1. **Show Loading States**: Display sending indicators while waiting for acknowledgments
2. **Handle Timeouts**: Implement timeout logic for operations that don't receive acknowledgments
3. **Retry Failed Operations**: Allow users to retry operations that failed
4. **Optimistic Updates**: Update UI optimistically but revert on errors
5. **Track Message IDs**: Use temporary IDs to match acknowledgments with sent messages

### Error Handling

Always handle both acknowledgments and errors:
```javascript
websocket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'acknowledgment') {
    // Success case
    handleSuccess(data);
  } else if (data.type === 'error') {
    // Error case
    handleError(data);
  }
};
```

## Notification Logic

1. **New Messages**: 
   - Sent to conversation subscribers (conversation group)
   - Also sent to department members as conversation update notification
   - Sender receives acknowledgment when message is processed

2. **New Conversations**: 
   - Sent to all connected staff in the relevant department

3. **Conversation Updates** (status changes, etc.):
   - Sent to all connected staff in the relevant department
   - Users subscribed to the conversation don't receive these (they get real-time updates anyway)
   - Action initiator receives acknowledgment

4. **User Status**: 
   - Sent to department members when users connect/disconnect

5. **Acknowledgments**: 
   - Sent only to the user who initiated the action
   - Provides confirmation that the action was processed successfully