# Context Manager API - Summary

## What Was Implemented

I've added comprehensive API endpoints for hotels to manage conversational flows and scheduled messages in the Context Manager system.

### New Files Created

1. **`context_manager/serializers.py`** - Serializers for FlowStep and ScheduledMessageTemplate models
2. **`context_manager/API_DOCUMENTATION.md`** - Complete documentation for all API endpoints
3. **`context_manager/tests_api.py`** - Tests for the new API endpoints

### Updated Files

1. **`context_manager/views.py`** - Added REST API views for managing flows and templates
2. **`context_manager/urls.py`** - Added URL patterns for the new endpoints
3. **`lobbybee/urls.py`** - Registered the context manager URLs in the main URL configuration

## API Endpoints

### FlowStep Management

- `GET /api/context/hotels/{hotel_id}/flow-steps/` - List all flow steps
- `POST /api/context/hotels/{hotel_id}/flow-steps/` - Create a new flow step
- `GET /api/context/hotels/{hotel_id}/flow-steps/{step_id}/` - Retrieve a flow step
- `PUT /api/context/hotels/{hotel_id}/flow-steps/{step_id}/` - Update a flow step
- `DELETE /api/context/hotels/{hotel_id}/flow-steps/{step_id}/` - Delete a flow step

### ScheduledMessageTemplate Management

- `GET /api/context/hotels/{hotel_id}/message-templates/` - List all message templates
- `POST /api/context/hotels/{hotel_id}/message-templates/` - Create a new message template
- `GET /api/context/hotels/{hotel_id}/message-templates/{template_id}/` - Retrieve a message template
- `PUT /api/context/hotels/{hotel_id}/message-templates/{template_id}/` - Update a message template
- `DELETE /api/context/hotels/{hotel_id}/message-templates/{template_id}/` - Delete a message template

## Key Features

1. **Authentication**: All endpoints require JWT authentication
2. **Hotel-specific**: All endpoints are scoped to a specific hotel using UUID
3. **Validation**: Proper validation for all fields including unique constraints
4. **Error Handling**: Comprehensive error handling with appropriate HTTP status codes
5. **Documentation**: Complete API documentation with examples

## Example Usage

Hotels can now create conversational flows like this:

1. Create a check-in start step:
```json
{
  "step_id": "checkin_start",
  "flow_type": "guest_checkin",
  "message_template": "Welcome! Confirm your name: [Guest Name] (1. Yes, 2. No)",
  "options": {"1": "Yes", "2": "No"}
}
```

2. Create a DOB collection step:
```json
{
  "step_id": "checkin_collect_dob",
  "flow_type": "guest_checkin",
  "message_template": "Please provide your date of birth (DD-MM-YYYY).",
  "options": {}
}
```

3. Link the steps by updating the first step with the next_step reference.

This allows hotels to completely customize their conversational flows for check-in, room service, checkout, and other guest interactions.