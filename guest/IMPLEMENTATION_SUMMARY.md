# Simplified Guest Management API Implementation

## Overview
Successfully replaced the over-engineered guest management system with a clean, minimal approach focused on core functionality.

## Files Created/Modified

### New Files:
1. **`guest/serializers_new.py`** - Minimal serializers for new endpoints
2. **`guest/new_view.py`** - Simplified viewsets with 6 core endpoints  
3. **`guest/urls_new.py`** - URL routing for new endpoints
4. **`guest/api_example.md`** - Complete API usage documentation

### Removed Files:
- **`guest/services.py`** - Unused utility service

## Simplified API Endpoints (6 Total)

### Guest Management (`guest-management/`):
1. **`POST create-guest/`** - Create primary + secondary guests with documents
2. **`GET guests/`** - List all hotel guests
3. **`GET bookings/`** - List all hotel bookings

### Stay Management (`stay-management/`):
4. **`POST checkin-offline/`** - Create pending stays with room assignment
5. **`PATCH {id}/verify-checkin/`** - Verify and activate stays
6. **`GET pending-stays/`** - List stays needing verification

## Key Improvements

### Simplified Workflow:
1. **Create Guests** → Upload all documents in one request
2. **Check-in Offline** → Assign rooms, create pending stays
3. **Verify Check-in** → Final verification, mark as active

### Multi-Guest Support:
- Primary guest linked to WhatsApp/bookings
- Secondary guests for records only (name + documents)
- Multiple rooms per primary guest

### Document Handling:
- Front/back document support
- Primary/secondary document distinction
- Simple file upload naming convention

### Room Management:
- Room assignment during check-in (not verification)
- Automatic status updates (available → occupied)
- Support for room changes during verification

### Transaction Safety:
- Full rollback on any failure
- Atomic operations for data consistency
- Error handling with detailed messages

## Usage Example Flow

```javascript
// 1. Create guests with documents
const guests = await fetch('/api/guest/guest-management/create-guest/', {
    method: 'POST',
    body: formData // primary_guest, accompanying_guests + files
});
// Returns: { primary_guest_id: 123, accompanying_guest_ids: [124, 125] }

// 2. Create offline check-in with room assignment
const checkin = await fetch('/api/guest/stay-management/checkin-offline/', {
    method: 'POST', 
    body: JSON.stringify({
        primary_guest_id: 123,
        room_ids: [101, 102],
        check_in_date: "2024-01-15T14:00:00Z",
        check_out_date: "2024-01-16T11:00:00Z",
        guest_names: ["John Doe", "John Doe"]
    })
});
// Returns: { booking_id: 456, stay_ids: [789, 790] }

// 3. Verify and activate stay
const verify = await fetch('/api/guest/stay-management/789/verify-checkin/', {
    method: 'PATCH',
    body: JSON.stringify({
        register_number: "REG-2024-001",
        guest_updates: { email: "updated@email.com" }
    })
});
// Returns: { stay_id: 789, register_number: "REG-2024-001" }
```

## Installation

Add to your main `urls.py`:
```python
path('api/guest/', include('guest.urls_new')),
```

## Benefits Over Previous System

1. **Reduced Complexity**: 6 endpoints vs 12+ with multiple redundant actions
2. **Clear Separation**: Guest creation vs stay management vs verification
3. **Better File Handling**: Predictable file naming and processing
4. **Flexible Room Assignment**: Room assignment at check-in, changes at verification
5. **Simplified Documents**: Primary guest gets full data, secondary guests minimal
6. **Atomic Operations**: Full transaction safety
7. **Better Error Messages**: Clear feedback for frontend integration

## Next Steps

1. Replace existing `urls.py` with `urls_new.py`
2. Remove old `views.py` and `serializers.py` if no longer needed
3. Update frontend to use new simplified endpoints
4. Add authentication token to all API calls
5. Test with real file uploads and room assignments