# Context Manager API Documentation

This document provides detailed information on how hotels can manage conversational flows and scheduled messages through the Context Manager API.

## Authentication

All endpoints require authentication using JWT tokens. Include the token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

## FlowStep Endpoints

FlowSteps define the individual steps in a conversational flow.

### List All Flow Steps

**Endpoint:** `GET /api/context/hotels/{hotel_id}/flow-steps/`

**Description:** Retrieve all flow steps for a specific hotel.

**Response:**
```json
[
  {
    "id": 1,
    "step_id": "checkin_start",
    "flow_type": "guest_checkin",
    "message_template": "Welcome to [Hotel Name]! We're ready to begin your check-in. Please confirm your full name: [Guest Full Name]. Is this correct? (1. Yes, 2. No)",
    "options": {"1": "Yes", "2": "No"},
    "next_step": 2,
    "previous_step": null,
    "conditional_next_steps": null,
    "is_optional": false
  }
]
```

### Create a Flow Step

**Endpoint:** `POST /api/context/hotels/{hotel_id}/flow-steps/`

**Description:** Create a new flow step for a specific hotel.

**Request Body:**
```json
{
  "step_id": "checkin_collect_dob",
  "flow_type": "guest_checkin",
  "message_template": "Please provide your date of birth (DD-MM-YYYY).",
  "options": {},
  "next_step": null,
  "previous_step": 1,
  "conditional_next_steps": null,
  "is_optional": false
}
```

**Response:**
```json
{
  "id": 2,
  "step_id": "checkin_collect_dob",
  "flow_type": "guest_checkin",
  "message_template": "Please provide your date of birth (DD-MM-YYYY).",
  "options": {},
  "next_step": null,
  "previous_step": 1,
  "conditional_next_steps": null,
  "is_optional": false
}
```

### Retrieve a Flow Step

**Endpoint:** `GET /api/context/hotels/{hotel_id}/flow-steps/{step_id}/`

**Description:** Retrieve a specific flow step by its step_id.

**Response:**
```json
{
  "id": 2,
  "step_id": "checkin_collect_dob",
  "flow_type": "guest_checkin",
  "message_template": "Please provide your date of birth (DD-MM-YYYY).",
  "options": {},
  "next_step": null,
  "previous_step": 1,
  "conditional_next_steps": null,
  "is_optional": false
}
```

### Update a Flow Step

**Endpoint:** `PUT /api/context/hotels/{hotel_id}/flow-steps/{step_id}/`

**Description:** Update a specific flow step.

**Request Body:**
```json
{
  "flow_type": "guest_checkin",
  "message_template": "Please provide your date of birth in DD-MM-YYYY format.",
  "options": {},
  "next_step": 3,
  "previous_step": 1,
  "conditional_next_steps": null,
  "is_optional": false
}
```

**Response:**
```json
{
  "id": 2,
  "step_id": "checkin_collect_dob",
  "flow_type": "guest_checkin",
  "message_template": "Please provide your date of birth in DD-MM-YYYY format.",
  "options": {},
  "next_step": 3,
  "previous_step": 1,
  "conditional_next_steps": null,
  "is_optional": false
}
```

### Delete a Flow Step

**Endpoint:** `DELETE /api/context/hotels/{hotel_id}/flow-steps/{step_id}/`

**Description:** Delete a specific flow step.

**Response:** `204 No Content`

## ScheduledMessageTemplate Endpoints

ScheduledMessageTemplates define templates for proactive messages sent to guests.

### List All Scheduled Message Templates

**Endpoint:** `GET /api/context/hotels/{hotel_id}/message-templates/`

**Description:** Retrieve all scheduled message templates for a specific hotel.

**Response:**
```json
[
  {
    "id": 1,
    "hotel": 1,
    "message_type": "checkout_reminder",
    "trigger_condition": {"hours_before_checkout": 2},
    "message_template": "Your checkout is scheduled for tomorrow at 11:00 AM. Please let us know if you need a late checkout.",
    "is_active": true
  }
]
```

### Create a Scheduled Message Template

**Endpoint:** `POST /api/context/hotels/{hotel_id}/message-templates/`

**Description:** Create a new scheduled message template for a specific hotel.

**Request Body:**
```json
{
  "message_type": "welcome",
  "trigger_condition": {"on_checkin": true},
  "message_template": "Welcome to our hotel! Your room number is [Room Number]. Enjoy your stay!",
  "is_active": true
}
```

**Response:**
```json
{
  "id": 2,
  "hotel": 1,
  "message_type": "welcome",
  "trigger_condition": {"on_checkin": true},
  "message_template": "Welcome to our hotel! Your room number is [Room Number]. Enjoy your stay!",
  "is_active": true
}
```

### Retrieve a Scheduled Message Template

**Endpoint:** `GET /api/context/hotels/{hotel_id}/message-templates/{template_id}/`

**Description:** Retrieve a specific scheduled message template.

**Response:**
```json
{
  "id": 2,
  "hotel": 1,
  "message_type": "welcome",
  "trigger_condition": {"on_checkin": true},
  "message_template": "Welcome to our hotel! Your room number is [Room Number]. Enjoy your stay!",
  "is_active": true
}
```

### Update a Scheduled Message Template

**Endpoint:** `PUT /api/context/hotels/{hotel_id}/message-templates/{template_id}/`

**Description:** Update a specific scheduled message template.

**Request Body:**
```json
{
  "message_type": "welcome",
  "trigger_condition": {"on_checkin": true},
  "message_template": "Welcome to [Hotel Name]! Your room number is [Room Number]. Enjoy your stay!",
  "is_active": true
}
```

**Response:**
```json
{
  "id": 2,
  "hotel": 1,
  "message_type": "welcome",
  "trigger_condition": {"on_checkin": true},
  "message_template": "Welcome to [Hotel Name]! Your room number is [Room Number]. Enjoy your stay!",
  "is_active": true
}
```

### Delete a Scheduled Message Template

**Endpoint:** `DELETE /api/context/hotels/{hotel_id}/message-templates/{template_id}/`

**Description:** Delete a specific scheduled message template.

**Response:** `204 No Content`

## Field Descriptions

### FlowStep Fields

- `step_id` (string, unique): A unique identifier for the step (e.g., "checkin_start")
- `flow_type` (string): The type of flow this step belongs to (e.g., "guest_checkin", "room_service")
- `message_template` (string): The message template to send to the guest
- `options` (JSON object): User-facing options for this step (e.g., {"1": "Yes", "2": "No"})
- `next_step` (integer, optional): ID of the next step in the flow
- `previous_step` (integer, optional): ID of the previous step in the flow
- `conditional_next_steps` (JSON object, optional): Conditional routing logic
- `is_optional` (boolean): Whether this step is optional

### ScheduledMessageTemplate Fields

- `hotel` (integer): ID of the hotel this template belongs to
- `message_type` (string): Type of message (e.g., "checkout_reminder", "welcome")
- `trigger_condition` (JSON object): Conditions that trigger this message
- `message_template` (string): The message template to send
- `is_active` (boolean): Whether this template is active

## Example Usage

### Creating a Complete Check-in Flow

1. Create the start step:
```json
{
  "step_id": "checkin_start",
  "flow_type": "guest_checkin",
  "message_template": "Welcome to [Hotel Name]! We're ready to begin your check-in. Please confirm your full name: [Guest Full Name]. Is this correct? (1. Yes, 2. No)",
  "options": {"1": "Yes", "2": "No"},
  "is_optional": false
}
```

2. Create the DOB collection step:
```json
{
  "step_id": "checkin_collect_dob",
  "flow_type": "guest_checkin",
  "message_template": "Please provide your date of birth (DD-MM-YYYY).",
  "options": {},
  "previous_step": 1,
  "is_optional": false
}
```

3. Link the steps together by updating the first step:
```json
{
  "step_id": "checkin_start",
  "flow_type": "guest_checkin",
  "message_template": "Welcome to [Hotel Name]! We're ready to begin your check-in. Please confirm your full name: [Guest Full Name]. Is this correct? (1. Yes, 2. No)",
  "options": {"1": "Yes", "2": "No"},
  "next_step": 2,
  "is_optional": false
}
```

This creates a simple two-step check-in flow that can be extended with additional steps.