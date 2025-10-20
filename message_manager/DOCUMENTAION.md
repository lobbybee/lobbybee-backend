# Message Manager Documentation

This documentation provides comprehensive information on how to use both the WebSocket and REST API interfaces of the message_manager for building a chat interface for hotel staff.

## Table of Contents

1. [Overview](#overview)
2. [Department Structure](#department-structure)
3. [REST API Interface](#rest-api-interface)
   - [Authentication](#authentication)
   - [Conversation Endpoints](#conversation-endpoints)
   - [Message Endpoints](#message-endpoints)
4. [Webhook Interface](#webhook-interface)
   - [Webhook Endpoint](#webhook-endpoint)
   - [Payload Format](#payload-format)
   - [Processing Logic](#processing-logic)
   - [Setup and Usage](#setup-and-usage)
   - [Initiating a Conversation](#initiating-a-conversation)
5. [WebSocket Interface](#websocket-interface)
   - [Connection](#connection)
   - [WebSocket Commands](#websocket-commands)
   - [WebSocket Events](#websocket-events)
6. [Migration Notes](#migration-notes)
7. [Integration Guide](#integration-guide)
   - [Building a Chat Interface](#building-a-chat-interface)
8. [Models Reference](#models-reference)

## Overview

The message_manager provides two primary interfaces for interacting with conversations and messages:

1. **REST API**: For fetching conversation lists, messages, and sending new messages
2. **WebSocket**: For real-time communication and notifications

Both interfaces are protected by authentication and provide department-based access control using hardcoded department assignments.

## Department Structure

The message_manager uses a hardcoded department system that aligns with the User model's department assignments. Staff users are assigned departments via the `user.department` JSON field, which can contain multiple department names.

### Available Departments

```python
DEPARTMENT_CHOICES = [
    ('Reception', 'Reception'),
    ('Housekeeping', 'Housekeeping'),
    ('Room Service', 'Room Service'),
    ('Café', 'Café'),
    ('Management', 'Management'),
]
```

### User Department Assignment

Staff users can be assigned to multiple departments:

```json
{
  "department": ["Reception", "Housekeeping"]
}
```

### Conversation Routing

When guests select services:
1. System maps service numbers to department names
2. Sets conversation status to 'relay'
3. Assigns department name to conversation (currently not implemented in actions; status is set to 'relay' for all)
4. Notifies all active staff users

### Real-time Notifications

WebSocket notifications are sent to all active staff users when a new conversation enters 'relay' status:
- Uses `staff_{user_id}` group naming convention
- Each active staff user receives notifications for all relayed conversations

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

## Webhook Interface

The webhook interface handles incoming messages from external services, primarily WhatsApp, to process guest messages and trigger conversation flows. It integrates with the message handler to manage conversation states, flow steps, and relay to staff.

### Webhook Endpoint

**URL:** `POST /api/message_manager/webhook/whatsapp/`

This endpoint receives webhook payloads from WhatsApp's Business API when a guest sends a message. It is not protected by authentication (as it's called by external services), but it should be secured via other means like IP whitelisting or API keys in production. The endpoint processes the payload, updates conversations, and may send automated responses back to the guest via WhatsApp.

### Payload Format

The webhook expects a JSON payload from WhatsApp's Business API. The exact format depends on the message type, but a typical text message payload looks like this:

```json
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "your_business_account_id",
      "changes": [
        {
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {
              "display_phone_number": "your_business_phone_number",
              "phone_number_id": "your_phone_number_id"
            },
            "contacts": [
              {
                "profile": {
                  "name": "John Doe"
                },
                "wa_id": "1234567890"
              }
            ],
            "messages": [
              {
                "id": "wamid.HBgLMTY0MDk5NTIwMDAwE...",
                "from": "1234567890",
                "timestamp": "1640995200",
                "text": {
                  "body": "Hello, I need help with my room."
                },
                "type": "text"
              }
            ]
          },
          "field": "messages"
        }
      ]
    }
  ]
}
```

For media messages (e.g., images), the payload includes additional fields:

```json
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "your_business_account_id",
      "changes": [
        {
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {
              "display_phone_number": "your_business_phone_number",
              "phone_number_id": "your_phone_number_id"
            },
            "contacts": [
              {
                "profile": {
                  "name": "Jane Smith"
                },
                "wa_id": "0987654321"
              }
            ],
            "messages": [
              {
                "id": "wamid.HBgLMTY0MDk5NTIwMDAwE...",
                "from": "0987654321",
                "timestamp": "1640995300",
                "image": {
                  "mime_type": "image/jpeg",
                  "sha256": "hash_value",
                  "id": "media_id",
                  "caption": "My ID document"
                },
                "type": "image"
              }
            ]
          },
          "field": "messages"
        }
      ]
    }
  ]
}
```

### Processing Logic

When a webhook payload is received:

1. **Extract Phone Number**: Parses the guest's WhatsApp number from `entry[0].changes[0].value.messages[0].from` (currently placeholder implementation returns dummy data).
2. **Extract Message Content**: Retrieves the message text from `entry[0].changes[0].value.messages[0].text.body` for text messages, or handles media types accordingly (currently placeholder returns dummy data).
3. **Process Message**: Calls `MessageHandler.process_message()` with the phone number and content.
   - This finds or creates a conversation based on the guest's stay or creates a demo conversation.
   - Saves the incoming message as a guest message.
   - If the conversation is in 'relay' status, logs the relay (no further action in current implementation).
   - Otherwise, processes the message through predefined flows (e.g., DEMO_FLOW, CHECKIN_FLOW, SERVICES_FLOW) to determine the next step, execute actions (like validating guest name or starting relay), and generate a response.
4. **Execute Actions**: Actions such as `start_relay_to_department` set the conversation to 'relay' status and notify all active staff via WebSocket.
5. **Send Response**: If the processing returns a response message, sends it back to the guest via WhatsApp API (placeholder implementation logs the message).
6. **Log and Respond**: Returns a JSON response indicating success (`{'status': 'processed'}`), ignored (`{'status': 'ignored'}`), or error (`{'status': 'error'}`).

The webhook handles errors gracefully, logging issues for debugging. For demo conversations (non-guests), it uses a simplified flow.

### Setup and Usage

To use the webhook:

1. **Configure WhatsApp Business API**:
   - Set up a WhatsApp Business Account and obtain API credentials (access token, phone number ID).
   - Configure the webhook URL in your WhatsApp Business API settings to point to `/api/message_manager/webhook/whatsapp/`.
   - Ensure the webhook is verified (WhatsApp sends a verification request; implement a GET handler if needed).

2. **Secure the Endpoint**:
   - In production, implement security measures like verifying webhook signatures using the WhatsApp app secret, restricting access to known IPs, or using API keys.
   - The current implementation does not include authentication, so ensure external protection.

3. **Handle Different Message Types**:
   - The webhook currently supports text messages. Extend `extract_message_content()` in `WhatsAppWebhookView` for media (e.g., download images using WhatsApp API and store via `context_manager.utils.whatsapp`).
   - For media, parse fields like `image.id` to fetch and process the media.

4. **Testing**:
   - Use WhatsApp's webhook testing tools or send test messages to trigger the endpoint.
   - Monitor logs for processing details. For development, the code includes placeholders that return dummy data; replace with actual parsing.

5. **Integration with Flows**:
   - Incoming messages drive conversation flows defined in `flow_definitions.py` (e.g., check-in, services).
   - Flows use triggers (e.g., "services" or "1") to advance steps and execute actions like relaying to staff.
   - Ensure flows are defined for proper routing; customize `MessageHandler` for additional logic.

6. **Examples**:
   - **Demo Flow Initiation**: A non-guest sends any message. The system creates a demo conversation, responds with "Welcome to our hotel demo! Type "services" to explore.", and sets current_step to 'start'.
   - **Services Trigger**: In demo or active flow, guest sends "services". Matches trigger in SERVICES_FLOW, responds with "How can we assist you today? 1. Room Service 2. Housekeeping 3. Reception 4. Other", and waits for selection.
   - **Relay Initiation**: Guest selects "1" for Room Service. Advances to 'start_relay_room_service', executes `start_relay_to_department`, sets status to 'relay', notifies all active staff via WebSocket, and responds with "Connecting you to Room Service...".
   - **Check-in Flow**: For a pending stay, system prompts for name in 'start' step. Guest replies with name, executes `validate_guest_name`, stores name in context_data, advances to 'collect_documents', responds with "Please upload a photo of your ID document.".
   - **Document Upload**: Guest sends media (placeholder). Executes `save_document`, logs action, advances to 'finalize_checkin' (but flow ends; customize for actual check-in completion).
   - **Relay Message Handling**: In 'relay' status, incoming messages are logged as relayed, no automated response generated.

If a message cannot be processed (e.g., invalid payload), the webhook returns `{'status': 'ignored'}` or `{'status': 'error'}`.

### Initiating a Conversation

To initiate a conversation, a guest must send a message via WhatsApp to your business number. This triggers the webhook with a payload containing the message details.

**Endpoint:** `POST /api/message_manager/webhook/whatsapp/`

**Example Payload (Text Message to Initiate Demo Conversation):**
```json
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "your_business_account_id",
      "changes": [
        {
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {
              "display_phone_number": "your_business_phone_number",
              "phone_number_id": "your_phone_number_id"
            },
            "contacts": [
              {
                "profile": {
                  "name": "John Doe"
                },
                "wa_id": "1234567890"
              }
            ],
            "messages": [
              {
                "id": "wamid.HBgLMTY0MDk5NTIwMDAwE...",
                "from": "1234567890",
                "timestamp": "1640995200",
                "text": {
                  "body": "Hello"
                },
                "type": "text"
              }
            ]
          },
          "field": "messages"
        }
      ]
    }
  ]
}
```

Upon receiving this payload:
- If the phone number matches a guest with an active or pending stay, it initiates the appropriate flow (check-in or services).
- If no matching guest is found, it creates a demo conversation and responds with the demo welcome message.
- The system processes the message, saves it, and sends an automated response back via WhatsApp.

For testing, you can simulate sending this payload to the endpoint using tools like Postman or curl. In production, WhatsApp automatically sends this payload when a guest messages your business.

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

## Migration Notes

### Changes from hotel.Department to Hardcoded Departments

The message_manager has been migrated from using `hotel.Department` model objects to a hardcoded department system. This change provides several benefits:

- **Simplified Architecture**: No dependency on separate department management
- **Better Performance**: No database joins for department lookups
- **Easier Maintenance**: Departments are defined in code, not database
- **Consistent Structure**: Aligns with User model department assignments

### What Changed

1. **Model Fields**: 
   - `conversation.department` changed from `ForeignKey('hotel.Department')` to `CharField` with choices
   - `messagetemplate.department` changed from `ForeignKey` to `CharField` with choices

2. **API Responses**: 
   - `department_name` field now contains the department name directly instead of accessing `department.name`

3. **WebSocket Notifications**: 
   - Notifications now go to all active staff users instead of department groups

4. **User Assignment**: 
   - Staff users are assigned departments via `user.department` JSON field
   - Users can be assigned to multiple departments

### Impact on Existing Code

If you have existing integrations, you may need to update:

1. **API Consumers**: Update any code that expects department objects to handle department names as strings
2. **WebSocket Clients**: Update notification handling to work with user-based groups
3. **Database Migrations**: Run Django migrations to update the database schema

### Backward Compatibility

The API responses maintain the same structure, but the `department_name` field now contains the department name directly rather than accessing a related object's name field.

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
| department | CharField | Department handling the conversation (nullable) - one of: Reception, Housekeeping, Room Service, Café, Management |
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
| department | CharField | Department (nullable) - one of: Reception, Housekeeping, Room Service, Café, Management |
| template_type | CharField | Template type (default: text) |
