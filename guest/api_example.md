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
    "guest_updates": {
        "email": "updated@email.com"
    }
}
```

### Response:
```json
{
    "stay_id": 789,
    "register_number": "REG-2024-001",
    "message": "Check-in verified and activated successfully"
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

## 6. List All Bookings

**Endpoint**: `GET /api/guest/guest-management/bookings/`

## URL Registration

Add to your main `urls.py`:

```python
path('api/guest/', include('guest.urls_new')),
```