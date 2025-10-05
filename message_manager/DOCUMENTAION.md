# Message Manager Documentation

This documentation provides comprehensive information on how to use both the WebSocket and REST API interfaces of the message_manager for building a chat interface for hotel staff.

## Table of Contents

1. [Overview](#overview)
2. [REST API Interface](#rest-api-interface)
   - [Authentication](#authentication)
   - [Conversation Endpoints](#conversation-endpoints)
   - [Message Endpoints](#message-endpoints)
3. [WebSocket Interface](#websocket-interface)
   - [Connection](#connection)
   - [WebSocket Commands](#websocket-commands)
   - [WebSocket Events](#websocket-events)
4. [Integration Guide](#integration-guide)
   - [Building a Chat Interface](#building-a-chat-interface)
5. [Models Reference](#models-reference)

## Overview

The message_manager provides two primary interfaces for interacting with conversations and messages:

1. **REST API**: For fetching conversation lists, messages, and sending new messages
2. **WebSocket**: For real-time communication and notifications

Both interfaces are protected by authentication and provide department-based access control.

## REST API Interface

### Authentication

All API endpoints require authentication using JWT tokens. Include the token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

### Base URL

All API endpoints are prefixed with:
```
/api/message_manager/
```

### Conversation Endpoints

#### List Conversations
```
GET /api/message_manager/conversations/
```

**Response:**
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "stay_id": 1,
      "guest_name": "John Doe",
      "room_number": "101",
      "status": "relay",
      "department_name": "Reception",
      "last_message": {
        "content": "Hello, I need help with...",
        "timestamp": "2025-09-23T10:30:00Z",
        "sender_type": "guest"
      },
      "updated_at": "2025-09-23T10:30:00Z"
    }
  ]
}
```

#### Get Conversation Details
```
GET /api/message_manager/conversations/{id}/
```

**Response:**
```json
{
  "id": 1,
  "stay_id": 1,
  "guest_name": "John Doe",
  "room_number": "101",
  "guest_phone": "+1234567890",
  "status": "relay",
  "department_name": "Reception",
  "context_data": {},
  "created_at": "2025-09-23T10:00:00Z",
  "updated_at": "2025-09-23T10:30:00Z"
}
```

#### List Active Conversations
```
GET /api/message_manager/conversations/active_conversations/
```

**Response:**
```json
[
  {
    "id": 2,
    "stay_id": 2,
    "guest_name": "Jane Smith",
    "room_number": "102",
    "status": "active",
    "department_name": null,
    "last_message": null,
    "updated_at": "2025-09-23T09:00:00Z"
  }
]
```

### Message Endpoints

#### List Messages for a Conversation
```
GET /api/message_manager/conversations/{id}/messages/
```

**Response:**
```json
[
  {
    "id": 1,
    "content": "Hello, I need help with my room service.",
    "sender_type": "guest",
    "sender_name": "John Doe",
    "timestamp": "2025-09-23T10:15:00Z"
  },
  {
    "id": 2,
    "content": "Sure, I'm connecting you with our room service team.",
    "sender_type": "staff",
    "sender_name": "Reception Staff",
    "timestamp": "2025-09-23T10:16:00Z"
  }
]
```

#### Send a Message
```
POST /api/message_manager/conversations/{id}/send_message/
```

**Request Body:**
```json
{
  "text": "Hello, how can I help you today?"
}
```

**Response:**
```json
{
  "id": 3,
  "content": "Hello, how can I help you today?",
  "sender_type": "staff",
  "sender_name": "Reception Staff",
  "timestamp": "2025-09-23T10:30:00Z"
}
```

#### End Conversation Relay
```
POST /api/message_manager/conversations/{id}/end_relay/
```

**Response:**
```json
{
  "status": "relay ended"
}
```

## WebSocket Interface

### Connection

Connect to the WebSocket endpoint using the following URL:
```
ws://your-domain/ws/staff/
```

Authentication is handled through Django's session authentication. Make sure the user is logged in before connecting.

### WebSocket Commands

Commands are sent as JSON objects with a `command` field.

#### Subscribe to Conversation
```json
{
  "command": "subscribe_to_conversation",
  "stay_id": 1
}
```

#### Unsubscribe from Conversation
```json
{
  "command": "unsubscribe_from_conversation",
  "stay_id": 1
}
```

#### Send Message
```json
{
  "command": "send_message",
  "stay_id": 1,
  "text": "Hello, how can I help you today?"
}
```

### WebSocket Events

Events are received as JSON objects with a `type` field.

#### New Message
```json
{
  "type": "new_message",
  "stay_id": 1,
  "content": "Guest's message content",
  "sender_type": "guest",
  "sender_name": "John Doe",
  "timestamp": "2025-09-23T10:30:00Z"
}
```

#### New Conversation
```json
{
  "type": "new_conversation",
  "stay_id": 2,
  "conversation_id": 3,
  "message": "New conversation initiated",
  "timestamp": "2025-09-23T10:45:00Z"
}
```

## Integration Guide

### Building a Chat Interface

Here's a step-by-step guide to building a chat interface using both the REST API and WebSocket:

1. **Authenticate the user** and obtain a JWT token
2. **Connect to the WebSocket** endpoint
3. **Fetch conversation lists** using the REST API
4. **Subscribe to conversations** of interest via WebSocket
5. **Display messages** by fetching them through the REST API
6. **Send messages** using either the REST API or WebSocket
7. **Listen for real-time updates** through WebSocket events

### Sample Implementation (JavaScript)

```javascript
// 1. Connect to WebSocket
const ws = new WebSocket('ws://your-domain/ws/staff/');

ws.onopen = function(event) {
  console.log('Connected to WebSocket');
};

// 2. Handle incoming messages
ws.onmessage = function(event) {
  const data = JSON.parse(event.data);
  
  if (data.type === 'new_message') {
    // Add new message to UI
    addMessageToUI(data);
  } else if (data.type === 'new_conversation') {
    // Notify about new conversation
    showNewConversationNotification(data);
  }
};

// 3. Subscribe to a conversation
function subscribeToConversation(stayId) {
  ws.send(JSON.stringify({
    command: 'subscribe_to_conversation',
    stay_id: stayId
  }));
}

// 4. Send a message via WebSocket
function sendWebSocketMessage(stayId, text) {
  ws.send(JSON.stringify({
    command: 'send_message',
    stay_id: stayId,
    text: text
  }));
}

// 5. Send a message via REST API
async function sendRESTMessage(stayId, text) {
  const response = await fetch(`/api/message_manager/conversations/${stayId}/send_message/`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${jwtToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ text: text })
  });
  
  const message = await response.json();
  return message;
}

// 6. Fetch conversation list
async function fetchConversations() {
  const response = await fetch('/api/message_manager/conversations/', {
    headers: {
      'Authorization': `Bearer ${jwtToken}`
    }
  });
  
  const data = await response.json();
  return data.results;
}

// 7. Fetch messages for a conversation
async function fetchMessages(conversationId) {
  const response = await fetch(`/api/message_manager/conversations/${conversationId}/messages/`, {
    headers: {
      'Authorization': `Bearer ${jwtToken}`
    }
  });
  
  const messages = await response.json();
  return messages;
}
```

## Models Reference

### Conversation Model

| Field | Type | Description |
|-------|------|-------------|
| id | BigAutoField | Primary key |
| stay | OneToOneField | Related stay (nullable for demo conversations) |
| status | CharField | Conversation status (demo, checkin, active, relay, closed) |
| current_step | CharField | Current step in the conversation flow |
| department | ForeignKey | Department handling the conversation (nullable) |
| context_data | JSONField | Context data for flow state |
| created_at | DateTimeField | Creation timestamp |
| updated_at | DateTimeField | Last update timestamp |

### Message Model

| Field | Type | Description |
|-------|------|-------------|
| id | BigAutoField | Primary key |
| conversation | ForeignKey | Related conversation |
| content | TextField | Message content |
| sender_type | CharField | Sender type (guest, staff, system) |
| staff_sender | ForeignKey | Staff member who sent the message (nullable) |
| timestamp | DateTimeField | Message timestamp |
| whatsapp_message_id | CharField | WhatsApp message ID (nullable) |

### MessageTemplate Model

| Field | Type | Description |
|-------|------|-------------|
| id | BigAutoField | Primary key |
| name | CharField | Template name |
| content | TextField | Template content |
| department | ForeignKey | Department (nullable) |
| template_type | CharField | Template type (default: text) |