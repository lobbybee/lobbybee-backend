# Simplified Guest Management API Usage Examples

## 1. Create Guest with Documents

**Endpoint**: `POST /api/guest/guest-management/create-guest/`
**Content-Type**: `multipart/form-data`

### Form Data:
```
primary_guest: {
    "full_name": "John Doe",
    "whatsapp_number": "+1234567890",
    "email": "john@email.com",
    "document_type": "aadhar_id",
    "document_number": "123456789012"
}

accompanying_guests: [
    {
        "full_name": "Jane Doe",
        "document_type": "aadhar_id",
        "document_number": "987654321098"
    },
    {
        "full_name": "Child Doe",
        "document_type": "other"
    }
]
```

### Files:
```
primary_documents_0: [Aadhaar front file]
primary_documents_back_0: [Aadhaar back file]

guest_0_documents_0: [Jane's ID front]
guest_0_documents_back_0: [Jane's ID back]

guest_1_documents_0: [Child's document]
```

### Response:
```json
{
    "primary_guest_id": 123,
    "accompanying_guest_ids": [124, 125],
    "message": "Guests created successfully"
}
```

## 2. Create Offline Check-in

**Endpoint**: `POST /api/guest/stay-management/checkin-offline/`

### Request Body:
```json
{
    "primary_guest_id": 123,
    "room_ids": [101, 102],
    "check_in_date": "2024-01-15T14:00:00Z",
    "check_out_date": "2024-01-16T11:00:00Z",
    "guest_names": ["John Doe", "John Doe"]
}
```

### Response:
```json
{
    "booking_id": 456,
    "stay_ids": [789, 790],
    "message": "Check-in created successfully. Pending verification."
}
```

## 3. Verify Check-in

**Endpoint**: `PATCH /api/guest/stay-management/789/verify-checkin/`

### Request Body:
```json
{
    "register_number": "REG-2024-001",
    "room_ids": [103, 104],
    "guest_updates": {
        "email": "updated@email.com"
    }
}
```

### Response:
```json
{
    "stay_id": 789,
    "activated_stay_ids": [789, 790],
    "room_ids": [103, 104],
    "register_number": "REG-2024-001",
    "message": "Check-in verified and activated successfully for 2 stay(s)"
}
```

## 4. List Pending Stays

**Endpoint**: `GET /api/guest/stay-management/pending-stays/`

### Response:
```json
[
    {
        "id": 791,
        "guest": {
            "id": 126,
            "whatsapp_number": "+9876543210",
            "full_name": "Another Guest",
            "email": "guest@email.com",
            "status": "pending_checkin",
            "is_primary_guest": true
        },
        "status": "pending",
        "check_in_date": "2024-01-15T14:00:00Z",
        "check_out_date": "2024-01-16T11:00:00Z",
        "room": 103,
        "room_details": {
            "id": 103,
            "room_number": "A103",
            "floor": 1,
            "category": "Deluxe"
        },
        "register_number": null,
        "identity_verified": false
    }
]
```

## 5. List All Guests

**Endpoint**: `GET /api/guest/guest-management/guests/`

## 6. List Checked-in Users (Grouped by Guest)

**Endpoint**: `GET /api/guest/stay-management/checked-in-users-grouped/`

### Response:
```json
{
    "count": 1,
    "next": null,
    "previous": null,
    "results": [
        {
            "guest": {
                "id": 123,
                "full_name": "John Doe"
            },
            "is_checked_in": true,
            "active_stay_ids": [789, 790],
            "pending_stay_ids": [],
            "completed_stay_ids": [],
            "billing": {
                "current_bill_total": 2000.0,
                "expected_bill_total": 3000.0,
                "rooms": [
                    {"stay_id": 789, "room_id": 101, "current_bill": 1000.0, "expected_bill": 1500.0},
                    {"stay_id": 790, "room_id": 102, "current_bill": 1000.0, "expected_bill": 1500.0}
                ]
            },
            "stays": []
        }
    ]
}
```

## 7. Stay History Grouped (All Statuses)

**Endpoint**: `GET /api/guest/stay-management/stays-history-grouped/?search=John&page=1&page_size=10`

### Notes:
- Returns grouped rows by booking transaction (not by guest).
- Includes active + pending + completed stays in each booking row.
- Useful for historical search/audit.
- Search supports guest name, WhatsApp, document number, room number, and stay register number.

### Response:
```json
{
    "count": 2,
    "next": null,
    "previous": null,
    "results": [
        {
            "booking": {
                "id": 456,
                "status": "confirmed",
                "check_in_date": "2024-01-15T14:00:00Z",
                "check_out_date": "2024-01-16T11:00:00Z",
                "total_amount": "3000.00",
                "is_via_whatsapp": false,
                "guest_names": ["John Doe", "Jane Doe"],
                "booking_date": "2024-01-15T09:30:00Z"
            },
            "guest": {
                "id": 123,
                "full_name": "John Doe"
            },
            "is_checked_in": true,
            "active_stay_ids": [789, 790],
            "pending_stay_ids": [],
            "completed_stay_ids": [],
            "billing": {
                "current_bill_total": 2000.0,
                "expected_bill_total": 3000.0,
                "rooms": [
                    {"stay_id": 789, "room_id": 103, "current_bill": 1000.0, "expected_bill": 1500.0},
                    {"stay_id": 790, "room_id": 104, "current_bill": 1000.0, "expected_bill": 1500.0}
                ]
            },
            "stays": []
        },
        {
            "booking": {
                "id": 410,
                "status": "completed",
                "check_in_date": "2024-01-10T14:00:00Z",
                "check_out_date": "2024-01-12T11:00:00Z",
                "total_amount": "2500.00",
                "is_via_whatsapp": false,
                "guest_names": ["John Doe"],
                "booking_date": "2024-01-09T08:30:00Z"
            },
            "guest": {
                "id": 123,
                "full_name": "John Doe"
            },
            "is_checked_in": false,
            "active_stay_ids": [],
            "pending_stay_ids": [],
            "completed_stay_ids": [700],
            "billing": {
                "current_bill_total": 2500.0,
                "expected_bill_total": 2500.0,
                "rooms": [
                    {"stay_id": 700, "room_id": 101, "current_bill": 2500.0, "expected_bill": 2500.0}
                ]
            },
            "stays": []
        }
    ]
}
```

## 8. Bulk Checkout for Single Guest

**Endpoint**: `POST /api/guest/stay-management/checkout-bulk/`

### Request Body:
```json
{
    "guest_id": 123,
    "stay_ids": [789, 790],
    "internal_note": "Guest requested express checkout"
}
```

### Response:
```json
{
    "guest_id": 123,
    "checked_out_stay_ids": [789, 790],
    "skipped_stay_ids": [],
    "guest_has_active_stays": false,
    "checkout_message_sent": true,
    "feedback_triggered": true,
    "total_amount": "3000.00",
    "message": "Guest stays checked out successfully"
}
```

## 9. List All Bookings

**Endpoint**: `GET /api/guest/guest-management/bookings/`

## URL Registration

Add to your main `urls.py`:

```python
path('api/guest/', include('guest.urls_new')),
```
