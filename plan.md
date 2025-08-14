# Implementation Plan for Context Manager Views and Services

## Overview
Based on the contextManager.md and existing code structure, we need to implement missing views and services for the context manager. The system handles WhatsApp-based hotel CRM with structured conversations through database-defined flows.

## Missing Components to Implement

### 1. Services Module (`context_manager/services.py`)
This module will contain the core business logic for processing incoming messages and managing conversation contexts.

**Core Functions to implement:**
- `process_incoming_message(payload)`: Main function to process incoming WhatsApp messages
  - Extract `from_no` and `message` from payload
  - Retrieve active conversation context for the guest
  - Handle navigation commands (back, main menu)
  - Validate user input against current step requirements
  - Transition to next step based on user input
  - Generate response message with placeholders replaced
  - Update context with accumulated data
  - Handle error counting and cooloff mechanism
  - Finalize conversation when flow is complete

- `get_active_context(whatsapp_number)`: Retrieve active conversation context for a guest
- `get_flow_step(step_id)`: Retrieve a flow step by its ID
- `generate_response(context, flow_step)`: Generate response message based on current context and step
- `transition_step(context, user_input, current_step)`: Handle transitions between flow steps
- `replace_placeholders(template, context)`: Replace placeholders in message templates with actual data
- `validate_input(context, user_input, current_step)`: Validate user input against current step requirements
- `handle_navigation(context, command)`: Handle navigation commands (back, main menu)
- `update_accumulated_data(context, user_input, current_step)`: Update accumulated data in context

### 2. Flow Steps Views (`context_manager/views/flow_steps.py`)
REST API views for managing FlowStep records.

**Views to implement:**
- `FlowStepListView`: Handle GET (list) and POST (create) operations
- `FlowStepDetailView`: Handle GET (retrieve), PUT (update), and DELETE operations

### 3. Message Templates Views (`context_manager/views/message_templates.py`)
REST API views for managing ScheduledMessageTemplate records.

**Views to implement:**
- `ScheduledMessageTemplateListView`: Handle GET (list) and POST (create) operations
- `ScheduledMessageTemplateDetailView`: Handle GET (retrieve), PUT (update), and DELETE operations

### 4. WhatsApp Webhook View (`context_manager/views/webhook.py`)
View to handle incoming WhatsApp messages from the WhatsApp Business API.

**Functions to implement:**
- `WhatsAppWebhookView`: Main webhook view class
  - `post()`: Handle incoming POST requests from WhatsApp API
  - `handle_initial_message(whatsapp_number, message_body)`: Handle initial QR code scan messages
  - `send_whatsapp_message(recipient, message)`: Send response messages via WhatsApp API

## Simple Implementation Steps

### Phase 1: Core Services (Priority)
1. Create `context_manager/services.py`
2. Implement `process_incoming_message` with basic functionality:
   - Extract message data
   - Retrieve context
   - Handle simple responses
3. Implement `get_active_context` function
4. Implement basic `validate_input` function
5. Test with simple cases

### Phase 2: Flow Management
1. Implement `transition_step` function
2. Implement `generate_response` function
3. Implement `replace_placeholders` function
4. Implement navigation handling
5. Test flow transitions

### Phase 3: Views Implementation
1. Create `context_manager/views/flow_steps.py`
2. Implement FlowStep views using existing serializers
3. Create `context_manager/views/message_templates.py`
4. Implement ScheduledMessageTemplate views
5. Test API endpoints

### Phase 4: Webhook Integration
1. Create `context_manager/views/webhook.py`
2. Implement WhatsAppWebhookView
3. Integrate with services module
4. Test webhook processing

### Phase 5: Refinement and Testing
1. Add error handling and logging
2. Implement error cooloff mechanism
3. Add comprehensive tests
4. Run all tests to ensure no regression
5. Document implementation

## Core Flow Processing Logic

The core functionality works as follows:

1. **Receive Message**: When a message like `{from_no: "123guestphone", message: "next step"}` arrives:
   - Extract the phone number and message content
   - Look up the active conversation context for this guest

2. **Context Retrieval**: 
   - Find the ConversationContext record for this guest
   - If no active context exists, handle as a new conversation
   - If context exists, use it to determine the current flow and step

3. **Input Validation**:
   - Check if the message is a navigation command (back, main menu)
   - Validate the input against the current step's requirements
   - Handle invalid inputs by incrementing error count

4. **Step Transition**:
   - Based on the validated input, determine the next step
   - Update the context with accumulated data
   - Handle conditional next steps if defined

5. **Response Generation**:
   - Retrieve the next step's message template
   - Replace placeholders with actual data from Guest/Stay models
   - Generate the final response message

6. **Context Update**:
   - Update the conversation context with new step and data
   - Reset error count if appropriate
   - Deactivate context if flow is complete

## File Structure After Implementation
```
context_manager/
├── services.py
├── views/
│   ├── __init__.py
│   ├── flow_steps.py
│   ├── message_templates.py
│   └── webhook.py
├── models.py
├── serializers.py
├── urls.py
└── tests_*.py
```

## Dependencies and Considerations
1. Maintain consistency with existing code style and patterns
2. Follow Django REST framework best practices
3. Ensure proper error handling and logging
4. Maintain backward compatibility with existing migrations
5. Ensure proper rate limiting for spam protection
6. Handle placeholder replacement from Guest/Stay models:
   - `{guest_name}` → Guest.full_name
   - `{room_number}` → Stay.room.room_number  
   - `{wifi_password}` → Hotel.wifi_password
   - `{checkin_time}` → Stay.check_in_date
   - `{checkout_time}` → Stay.check_out_date
   - `{hotel_name}` → Hotel.name
   - `{total_guests}` → Stay.number_of_guests