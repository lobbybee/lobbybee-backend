# WhatsApp CRM Context Engine Architecture - Updated Checkpoint

## System Overview
Dynamic WhatsApp-based hotel CRM managing structured conversations through database-defined flows with placeholder replacement from guest/stay data, plus a separate message scheduling system for proactive communications.

## Core Message Processing
**Incoming Message Structure**: `{from_no: "919876543210", message: "hello"}`

### New Guest Number Logic
1. **Random message** → Invalid option response
2. **"demo"** → Demo workflow showcasing system capabilities  
3. **"hotel-1234"** → QR code scanned at reception → Initiate check-in flow

### Existing Guest Number Logic
1. **During check-in** → Show existing data, send confirmation to receptionist
2. **Random message** → Show main menu (Previous Stays, Check Room, etc.)

## Dynamic Flow System
- **All logic in database** as FlowStep records
- **Placeholder replacement** from Guest/Stay models: `{guest_name}`, `{room_number}`, `{wifi_password}`
- **Hotel-specific content** (menus, services) defined in flow steps
- **Message customization control** via `is_hotel_customizable` flag
- **Admin dashboard configurable** flows and logic

## Core Flow Examples

### 1. Check-in Flow (New Guest via QR)
```
guest_checkin_start → collect_name → collect_dob → collect_nationality → 
upload_document → verify_documents → assign_room → checkin_complete → main_menu
```
**Data collected**: Full name, DOB, nationality, identity document
**Final action**: Create Stay, update Guest, notify receptionist

### 2. Room Service Flow (Existing Guest)  
```
main_menu → room_service → show_menu → select_item → select_quantity → 
confirm_order → order_placed → main_menu
```
**Data**: Hotel's room service menu from flow steps
**Placeholders**: `{guest_name}`, `{room_number}`

### 3. Service Request Flow
```
main_menu → service_request → select_department → describe_issue → 
confirm_request → request_forwarded → main_menu
```
**Departments**: Housekeeping, Maintenance, Front Desk
**Action**: Route to hotel department WhatsApp

## Core Requirements
- **Structured Conversations Only**: No AI/NLP initially - predefined flows with menu selections
- **Multi-Department Support**: Each hotel department has separate WhatsApp numbers
- **Context Persistence**: Maintain conversation state across message exchanges
- **Navigation Support**: Browser-like back navigation + direct "home/main menu" option
- **Anti-Spam Protection**: Rate limiting and error handling
- **Hotel Customization**: Hotels customize predefined flow templates
- **Scheduled Messaging**: Proactive messages (checkout reminders, promos) separate from conversational flows

## Architecture Components

### 1. Dual System Architecture

#### Context Engine (Reactive/Conversational)
```
Incoming Message → Context Retrieval → Input Validation → State Machine → Response Generation → Message Send
```

#### Message Scheduler (Proactive/Broadcast)
```
Trigger Event → Message Queue → Bulk Processing → WhatsApp API → Logging
```

### 2. Context Data Structure
```json
{
  "whatsapp_number": "919876543210",
  "hotel_id": "hotel_123",
  "guest_id": "guest_456",
  "current_flow": "room_service_ordering",
  "current_step": "select_quantity",
  "accumulated_data": {"room": "205", "guest_name": "John", "selected_item": "pizza"},
  "navigation_stack": ["main_menu", "room_service", "show_menu"],
  "error_count": 2,
  "last_activity": "timestamp"
}
```

### 3. Context Engine Components

#### Message Processor
- Spam detection & rate limiting
- Input validation against current step expectations
- Error counter management (5 consecutive failures → cooloff)
- Error count resets when user navigates to main menu

#### Context Store
- User conversation states
- Navigation history (step IDs, not positions)
- Session data and timeouts (standardized across hotels)

#### Flow Engine
- Database-driven step progression
- Handles branching logic through conditional next steps
- Manages skip options ("n/a", "prefer not to answer")
- Dynamic placeholder replacement

#### Response Builder
- Combines hotel customizations with flow templates
- Creates final WhatsApp message JSON
- Handles both quick replies and text input uniformly
- Processes placeholders from Guest/Stay data

#### Timeout Manager
- Standardized context timeouts for data freshness
- Automatic cleanup of stale contexts

### 4. Message Scheduler Components

#### Scheduler Service
- Trigger-based message queueing
- Bulk message processing
- Hotel-specific scheduling rules

#### Message Queue Manager
- Batches messages for optimal API usage
- Handles retry logic for failed sends
- Rate limiting compliance

#### Template Engine
- Renders dynamic content for scheduled messages
- Hotel customization support
- Variable substitution (guest name, room number, etc.)

### 5. Data Models (Django)

#### Context Engine Models
```python
class FlowStep(models.Model):
    step_id = models.CharField(max_length=100, unique=True)
    hotel = models.ForeignKey(Hotel, null=True)  # Hotel-specific customization
    flow_type = models.CharField(max_length=50)  # 'room_service', 'checkin', 'demo'
    message_template = models.TextField()  # Supports {placeholder} syntax
    options = models.JSONField()  # Dynamic menu options
    next_step = models.ForeignKey('self', null=True)
    previous_step = models.ForeignKey('self', null=True)
    conditional_next_steps = models.JSONField(null=True)  # Branching logic
    action_type = models.CharField(max_length=50, null=True)  # 'create_stay', 'send_notification'
    validation_rules = models.JSONField(null=True)  # Input validation
    is_optional = models.BooleanField(default=False)
    is_hotel_customizable = models.BooleanField(default=True)  # Hotel can customize message content
    is_active = models.BooleanField(default=True)

class ConversationContext(models.Model):
    whatsapp_number = models.CharField(max_length=15)
    hotel = models.ForeignKey(Hotel)
    guest = models.ForeignKey(Guest, null=True)  # Linked after identification
    current_flow = models.CharField(max_length=50)
    current_step = models.ForeignKey(FlowStep)
    accumulated_data = models.JSONField(default=dict)
    navigation_stack = models.JSONField(default=list)
    error_count = models.IntegerField(default=0)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['whatsapp_number', 'hotel', 'is_active']
```

#### Message Scheduler Models
```python
class ScheduledMessageTemplate(models.Model):
    hotel = models.ForeignKey(Hotel)
    message_type = models.CharField(max_length=50)  # 'checkout_reminder', 'promo', 'welcome'
    trigger_condition = models.JSONField()  # {'hours_before_checkout': 2}
    message_template = models.TextField()  # Supports {placeholder} syntax
    is_active = models.BooleanField(default=True)

class MessageQueue(models.Model):
    whatsapp_number = models.CharField(max_length=15)
    hotel = models.ForeignKey(Hotel)
    message_type = models.CharField(max_length=50)
    message_content = models.TextField()
    scheduled_time = models.DateTimeField()
    sent_time = models.DateTimeField(null=True)
    status = models.CharField(max_length=20)  # 'pending', 'sent', 'failed'
    retry_count = models.IntegerField(default=0)
```

## Placeholder System
Dynamic replacement from Guest/Stay models:
- `{guest_name}` → Guest.full_name
- `{room_number}` → Stay.room.room_number  
- `{wifi_password}` → Hotel.wifi_password
- `{checkin_time}` → Stay.check_in_date
- `{checkout_time}` → Stay.check_out_date
- `{hotel_name}` → Hotel.name
- `{total_guests}` → Stay.number_of_guests

## Main Menu Structure (Dynamic)
1. **Room Service** → Hotel's menu items from flow steps
2. **Food & Beverages** → Restaurant/bar menu from flow steps  
3. **Service Request** → Housekeeping, Maintenance, Front Desk
4. **Room Info** → WiFi, amenities, check-in/out times

### 6. Integration Between Systems

#### Shared Components
- Same WhatsApp API client
- Same message template system with placeholder support
- Same hotel customization settings
- Common user identification

#### Interaction Points
1. **Scheduler sends message**: One-way, no context created
2. **User responds to scheduled message**: Context Engine picks up, creates new context
3. **Context Engine can trigger scheduled messages**: e.g., feedback request after service completion

#### Example Flow
```
Day 1: Guest checks in → Context Engine handles check-in flow
Day 2: Scheduler sends "How was breakfast?" → One-way message
Day 2: Guest replies "Great!" → Context Engine detects, starts feedback flow
Day 3: Scheduler sends checkout reminder → One-way message
Day 3: Guest replies "Can I extend?" → Context Engine handles extension request
```

### 7. Scalability Analysis

#### Current Load Capacity (100 hotels, 5 depts, 30 guests/day)
- **15,000 conversations/day**: Easily handled
- **150,000 messages/day**: Well within limits
- **Peak load**: ~31 conversations/minute
- **Architecture verdict**: Massive headroom, no changes needed

#### Future Scaling Triggers
- **1,000+ hotels**: Add Redis caching for context lookups
- **100K+ daily messages**: Consider message queue partitioning
- **Real-time analytics**: Separate read replicas

### 8. Key Design Decisions

#### Department Routing
- Each hotel department has separate WhatsApp number
- Context managed centrally until final confirmation
- Minimal inter-department message passing

#### Flow Management
- **Database-driven flows** with admin dashboard for hotel customization
- All logic, menus, and responses stored as FlowStep records
- **Message customization**: `is_hotel_customizable=True` allows hotel to modify message content
- **Predefined messages**: `is_hotel_customizable=False` keeps messages standardized across platform
- Real-time updates without code deployment
- Hotel-specific flow customization

#### Input Handling
- Users see friendly options ("1. Continue ordering", "2. Back")
- System maps input to step transitions without exposing technical IDs

#### Error Handling
- 5 consecutive invalid responses triggers cooloff
- Error counter resets on main menu navigation

#### Guest Identification
- New numbers require specific triggers (QR code, demo command)
- Existing guests get context-appropriate responses
- Automatic linking to Guest model after identification

#### Message Separation Strategy
- **Conversational messages**: Context Engine (stateful, interactive)
- **Scheduled messages**: Separate system (stateless, broadcast)
- **User responses**: Always processed by Context Engine

## Technology Stack
- **Backend**: Django REST API + PostgreSQL
- **Queue**: Redis/Celery for async processing
- **Integration**: WhatsApp Business API
- **Admin**: Custom dashboard for flow management
- **Storage**: CDN for media files (documents, images)

## Implementation Priorities
1. Build Context Engine core functionality
2. Implement check-in flow with QR code trigger
3. Add main menu and room service flow
4. Create admin dashboard for flow management
5. Implement message scheduler for proactive communications
6. Add monitoring/logging infrastructure

---
*Dynamic flow architecture enabling hotel customization through admin interface while maintaining structured conversations and seamless integration with existing guest management system.*
