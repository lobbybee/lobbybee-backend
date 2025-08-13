# WhatsApp CRM Context Engine Architecture - Updated Checkpoint

## System Overview
Building a context engine for WhatsApp-based hotel CRM that manages structured conversations across multiple departments and guest workflows, plus a separate message scheduling system for proactive communications.

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
  "user_id": "919876543210",
  "hotel_id": "hotel_123",
  "current_flow": "room_service_ordering",
  "current_step": "select_quantity",
  "step_data": {"item_id": "pizza_margherita"},
  "accumulated_data": {"room": "205", "guest_name": "John"},
  "navigation_stack": ["main_menu", "services", "room_service"],
  "error_count": 2,
  "last_activity": "timestamp",
  "department": "room_service"
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
- Linked list approach for step progression
- Handles branching logic through conditional next steps
- Manages skip options ("n/a", "prefer not to answer")
- Strict step progression with optional step skipping

#### Response Builder
- Combines hotel customizations with flow templates
- Creates final WhatsApp message JSON
- Handles both quick replies and text input uniformly

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
    flow_type = models.CharField(max_length=50)  # 'room_service', 'checkin'
    message_template = models.TextField()
    options = models.JSONField()  # User-facing options
    next_step = models.ForeignKey('self', null=True)
    previous_step = models.ForeignKey('self', null=True)
    conditional_next_steps = models.JSONField(null=True)  # For branching
    is_optional = models.BooleanField(default=False)

class UserContext(models.Model):
    user_id = models.CharField(max_length=20)
    hotel = models.ForeignKey(Hotel)
    context_data = models.JSONField()
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
```

#### Message Scheduler Models
```python
class ScheduledMessageTemplate(models.Model):
    hotel = models.ForeignKey(Hotel)
    message_type = models.CharField(max_length=50)  # 'checkout_reminder', 'promo', 'welcome'
    trigger_condition = models.JSONField()  # {'hours_before_checkout': 2}
    message_template = models.TextField()
    is_active = models.BooleanField(default=True)

class MessageQueue(models.Model):
    user_id = models.CharField(max_length=20)
    hotel = models.ForeignKey(Hotel)
    message_type = models.CharField(max_length=50)
    message_content = models.TextField()
    scheduled_time = models.DateTimeField()
    sent_time = models.DateTimeField(null=True)
    status = models.CharField(max_length=20)  # 'pending', 'sent', 'failed'
    retry_count = models.IntegerField(default=0)
```

### 6. Integration Between Systems

#### Shared Components
- Same WhatsApp API client
- Same message template system
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

#### Hotel Customization Level
- Hotels customize content of predefined flow templates
- Can enable/disable individual steps
- Can add/remove options within steps

#### Input Handling
- Users see friendly options ("1. Continue ordering", "2. Back")
- System maps input to step transitions without exposing technical IDs

#### Error Handling
- 5 consecutive invalid responses triggers cooloff
- Error counter resets on main menu navigation

#### Message Separation Strategy
- **Conversational messages**: Context Engine (stateful, interactive)
- **Scheduled messages**: Separate system (stateless, broadcast)
- **User responses**: Always processed by Context Engine

## Technology Stack
- **Backend**: Django REST API + PostgreSQL
- **Message Queue**: Redis/Celery for async processing
- **Caching**: Redis (future scaling)
- **Storage**: CDN for media files
- **Integration**: WhatsApp Business API

## Implementation Priorities
1. Build Context Engine core functionality
2. Implement basic scheduled messaging
3. Add monitoring/logging infrastructure
4. Optimize database indexing
5. Plan for Redis integration (future scaling)

---
*This architecture maintains clean separation between reactive conversations and proactive messaging while sharing infrastructure efficiently. Designed for current scale with clear growth path.*
