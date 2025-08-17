# Context Manager App Documentation

## 1. Overview

The `context_manager` Django app is a sophisticated conversational flow engine designed to manage automated, stateful interactions with users, primarily over WhatsApp. It provides the backend logic for a hotel's automated guest assistant, handling everything from initial contact (e.g., via a QR code scan) to complex, multi-step processes like check-in, guest services, and feedback collection.

The system is built to be highly configurable and template-driven, allowing administrators to define and customize conversational flows without changing the core application code.

## 2. Technical Architecture & Core Components

The app follows a standard Django structure, separating concerns into models, views, and services. The architecture is designed around a central webhook that processes all incoming user messages.

### Data Flow for an Incoming Message:

1.  **Webhook Ingestion (`views/webhook.py`)**:
    *   An external service (like Twilio) sends an HTTP POST request to the `WhatsAppWebhookView` whenever a user sends a message.
    *   This view is the single entry point. It has no authentication to allow public access from the webhook provider.
    *   It immediately creates a `WebhookLog` entry to record the raw payload.
    *   It extracts the user's phone number (`from_no`) and the message content (`message_body`).

2.  **Service Layer Processing (`services.py`)**:
    *   The view delegates all business logic to the `services.py` module.
    *   `handle_initial_message` is called if the message indicates the start of a new conversation (e.g., contains `start-` or `demo`). This function identifies the hotel and the desired flow category (e.g., `guest_checkin`).
    *   `process_webhook_message` is called for all other messages, assuming an ongoing conversation.
    *   The service layer is responsible for all state management.

3.  **State and Context Management (`services.py` & `models.py`)**:
    *   The `ConversationContext` model is the heart of state management. It links a `user_id` (phone number) to a `hotel`, tracks the `current_step` in the flow, maintains a `navigation_stack` (to handle "back" commands), and stores `context_data` (information collected from the user).
    *   Services retrieve the active context for the user. If the context has expired or doesn't exist, it can trigger a "session ended" message or start a new flow.

4.  **Flow Execution (`services.py`)**:
    *   The current `FlowStep` (which is linked to a `FlowStepTemplate`) dictates the expected behavior.
    *   `validate_input`: The user's message is validated against the `options` defined in the current step's template.
    *   `update_accumulated_data`: If the step is designed to collect information, the user's input is stored in the `context_data` JSON field.
    *   `transition_to_next_step`: Based on the user's input and the `conditional_next_steps` or `next_step_template` defined in the current step, the service determines the next step in the flow. The `ConversationContext` is updated to point to this new step.

5.  **Response Generation (`services.py`)**:
    *   `generate_response`: A response message is constructed using the `message_template` from the new `FlowStepTemplate`.
    *   `replace_placeholders`: Placeholders like `{guest_name}` or `{hotel_name}` in the template are replaced with actual data from the `ConversationContext` and related models (`Guest`, `Hotel`, `Stay`).
    *   The final message, including any options for the user to choose from, is returned to the view.

6.  **Webhook Response (`views/webhook.py`)**:
    *   The view receives the generated message from the service layer.
    *   It updates the `WebhookLog` to mark it as processed successfully.
    *   It returns the message in an HTTP 200 OK response, which the webhook provider then delivers to the user's WhatsApp.

### Key Components:

*   **Models (`models.py`)**: Define the database schema for all conversational components. See section 3 for details.
*   **Views (`views/` directory)**:
    *   `webhook.py`: Handles incoming messages.
    *   `flow_steps.py`, `message_templates.py`: Provide REST API endpoints for hotel staff to manage their specific flow configurations.
    *   Admin views (in `urls.py` but likely handled by `generics`): Provide REST API endpoints for superadmins to manage the master templates (`FlowTemplate`, `FlowStepTemplate`).
*   **Services (`services.py`)**: Contains all the business logic for processing messages, managing state, and controlling flow transitions. This keeps the views thin and logic centralized.
*   **Serializers (`serializers.py`)**: Used by the Django Rest Framework views to convert model instances to and from JSON for the API endpoints.
*   **URLs (`urls.py`)**: Maps URLs to views, defining the API structure for both the public webhook and the internal management endpoints.
*   **Tasks (`tasks.py`)**: (Referenced but not provided) Likely contains Celery tasks for asynchronous operations, such as sending scheduled messages from the `MessageQueue`.

## 3. Core Models Deep Dive

*   **`FlowTemplate`**: A master template for a complete conversational flow (e.g., "Guest Check-in", "Main Menu"). It has a `category` which is used to trigger it.
*   **`FlowStepTemplate`**: A template for a single step within a `FlowTemplate`. It defines:
    *   `message_template`: The text to send to the user (with placeholders).
    *   `options`: A dictionary of valid user inputs (e.g., `{"1": "Check In", "2": "Room Service"}`).
    *   `next_step_template`: The default next step to transition to.
    *   `conditional_next_steps`: A dictionary mapping user input to a specific next step, allowing for branching logic.
*   **`FlowStep`**: A concrete instance of a `FlowStepTemplate` for a specific `Hotel`. This links the abstract template to a real-world hotel, allowing for hotel-specific behavior if needed in the future, though most customization is handled by `HotelFlowConfiguration`.
*   **`HotelFlowConfiguration`**: Allows a `Hotel` to customize a `FlowTemplate`. It can enable/disable the flow and override `message_template` or `options` for specific steps via its `customization_data` JSON field. This is the primary mechanism for per-hotel customization.
*   **`ConversationContext`**: The runtime state of a single user's conversation. It tracks the current step, collected data, and session expiry. It is the most critical model for ensuring conversations are stateful.
*   **`ConversationMessage`**: A log of every message sent and received within a `ConversationContext`, providing a complete chat history.
*   **`WebhookLog`**: A raw log of every incoming payload from the webhook provider, used for debugging.
*   **`ScheduledMessageTemplate` & `MessageQueue`**: A system for sending proactive, scheduled messages. Templates define the content and trigger (e.g., "2 hours before checkout"), and `MessageQueue` holds the messages to be sent by a background worker.

## 4. External Dependencies & Integrations

The `context_manager` app is not standalone and relies on several key models from other apps within the project to function correctly. These integrations are crucial for contextualizing conversations and personalizing user interactions.

### `hotel` App:
*   **`Hotel` Model (`hotel.models.Hotel`)**: This is the most fundamental dependency. Every conversation is tied to a specific hotel.
    *   The `ConversationContext` has a direct `ForeignKey` to `Hotel`.
    *   Hotel-specific details like `hotel_name`, `wifi_password`, etc., are pulled from the `Hotel` object to populate message templates.
    *   Flow configurations (`HotelFlowConfiguration`) are linked to a `Hotel`, allowing each hotel to have customized conversational flows.

### `guest` App:
*   **`Guest` Model (`guest.models.Guest`)**: Represents the end-user (the guest).
    *   While there is no direct `ForeignKey` from `ConversationContext` to `Guest`, the link is established via the `user_id` (which is the guest's `whatsapp_number`).
    *   The `services.py` module uses `Guest.objects.get_or_create` to find or create a guest record at the start of a conversation.
    *   The guest's ID is stored in the `context_data` of the `ConversationContext` for easy retrieval.
    *   Guest details like `full_name` and `email` are used to personalize messages.

*   **`Stay` Model (`guest.models.Stay`)**: Represents a guest's booking or stay at a hotel.
    *   This model is queried in `services.py` to fetch dynamic, stay-specific information.
    *   Details like `room_number` (via a relation to `hotel.models.Room`), `checkin_time`, and `checkout_time` are retrieved from the active `Stay` record for a guest. This allows for highly contextual messages, such as "Your checkout time for room {room_number} is...".

## 5. API Endpoints (`urls.py`)

The app exposes several sets of API endpoints:

*   **Public Webhook**:
    *   `POST /webhook/`: The main entry point for all incoming WhatsApp messages.
*   **Admin APIs (`/admin/...`)**:
    *   Endpoints for managing the master templates (`FlowTemplate`, `FlowStepTemplate`, `FlowAction`). These are intended for super-administrators.
*   **Hotel-Specific APIs (`/hotels/<hotel_id>/...`)**:
    *   Endpoints for hotel managers to view their flow configurations, customize flows, and manage their scheduled message templates.

## 6. How to Extend

### Adding a New Conversational Flow:

1.  **Create `FlowTemplate`**: Add a new `FlowTemplate` instance in the database with a unique `category` (e.g., "late_checkout_request").
2.  **Create `FlowStepTemplate`s**: Create all the necessary `FlowStepTemplate` instances for the new flow. Link them together using the `next_step_template` and `conditional_next_steps` fields.
3.  **Trigger the Flow**: Modify the `services.py` logic to trigger this new flow. For example, you could add a "Late Checkout" option to the "Main Menu" flow, which would then transition to the first step of your new "late_checkout_request" flow.
4.  **Customize (Optional)**: A hotel can now see this new flow and use the `/customize` endpoint to tailor messages if needed.
