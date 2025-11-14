# Guest Management API Documentation

## Table of Contents

1. [Guest Management Endpoints](#guest-management-endpoints)
   - [Create Guest](#create-guest)
   - [List Guests](#list-guests)
   - [List Bookings](#list-bookings)
2. [Stay Management Endpoints](#stay-management-endpoints)
   - [Check-in Offline](#checkin-offline)
   - [Verify Check-in](#verify-checkin)
   - [List Pending Stays](#list-pending-stays)
   - [List Checked-in Users](#list-checked-in-users)
   - [Check Out User](#checkout-user)

## Guest Management Endpoints

### Create Guest

**Endpoint:** `POST /api/guest/create-guest/`

**Description:** Creates primary guest with accompanying guests and their identity documents. Supports file upload for documents and returns guest IDs for use in subsequent booking/stay creation.

**Required Permissions:**
- `permissions.IsAuthenticated`
- `IsHotelStaff`
- `IsSameHotelUser`

**Request Format:** Form data (multipart/form-data)

#### Required Fields:

| Field | Type | Description |
|-------|------|-------------|
| `primary_guest` | JSON | Primary guest information object |
| `accompanying_guests` | JSON (optional) | Array of accompanying guest information objects |

#### Primary Guest Object Structure:
```json
{
  "full_name": "string",
  "whatsapp_number": "string",
  "email": "string (optional)",
  "document_type": "string (optional)",
  "document_number": "string (optional)"
}
```

#### Accompanying Guest Object Structure:
```json
{
  "full_name": "string",
  "document_type": "string (optional)",
  "document_number": "string (optional)"
}
```

#### File Upload Fields:
- `primary_documents_0`, `primary_documents_1`, ...: Primary guest document files
- `primary_documents_back_0`, `primary_documents_back_1`, ...: Back side of primary guest documents (optional)
- `guest_0_documents_0`, `guest_0_documents_1`, ...: Documents for accompanying guest 0
- `guest_1_documents_0`, `guest_1_documents_1`, ...: Documents for accompanying guest 1

#### Business Logic:
- Creates primary guest with status 'pending_checkin'
- Creates accompanying guests with auto-generated WhatsApp numbers
- Handles multiple document uploads per guest
- Sets first document as primary for each guest
- Supports both front and back document uploads

#### Success Response (201 Created):
```json
{
  "primary_guest_id": 123,
  "accompanying_guest_ids": [124, 125],
  "message": "Guests created successfully"
}
```

### List Guests

**Endpoint:** `GET /api/guest/guests/`

**Description:** Lists all guests for the hotel with optional search functionality. Supports searching guests by name or phone number.

**Required Permissions:**
- `permissions.IsAuthenticated`
- `IsHotelStaff`
- `IsSameHotelUser`

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `search` | String | No | Search term to filter guests by name or phone number (case-insensitive, partial match) |

**Response Format:** JSON Array

#### Business Logic:
- Filters guests to only show those associated with the hotel (via stays or bookings)
- If search parameter is provided, filters guests where:
  - `full_name` contains the search term (case-insensitive)
  - OR `whatsapp_number` contains the search term (case-insensitive)
- Returns all guests if no search parameter is provided
- Includes document information for each guest

#### Usage Examples:

**List all guests:**
```
GET /api/guest/guests/
```

**Search by name:**
```
GET /api/guest/guests/?search=John
```

**Search by phone number:**
```
GET /api/guest/guests/?search=1234567890
```

**Partial search:**
```
GET /api/guest/guests/?search=john
GET /api/guest/guests/?search=123
```

#### Success Response (200 OK):
```json
[
  {
    "id": 123,
    "whatsapp_number": "+1234567890",
    "full_name": "John Doe",
    "email": "john@example.com",
    "status": "checked_in",
    "is_primary_guest": true,
    "documents": [
      {
        "id": 456,
        "document_type": "aadhar_id",
        "document_number": "1234-5678-9012",
        "is_verified": true,
        "document_file_url": "https://example.com/media/docs/front.jpg",
        "document_file_back_url": "https://example.com/media/docs/back.jpg"
      }
    ]
  }
]
```

### List Bookings

**Endpoint:** `GET /api/guest/bookings/`

**Description:** Lists all bookings for the hotel.

**Required Permissions:**
- `permissions.IsAuthenticated`
- `IsHotelStaff`
- `IsSameHotelUser`

**Response Format:** JSON Array

**Success Response (200 OK):**
```json
[
  {
    "id": 789,
    "primary_guest": {
      "id": 123,
      "whatsapp_number": "+1234567890",
      "full_name": "John Doe",
      "email": "john@example.com",
      "status": "checked_in",
      "is_primary_guest": true
    },
    "check_in_date": "2024-01-15T14:00:00Z",
    "check_out_date": "2024-01-18T11:00:00Z",
    "status": "confirmed",
    "total_amount": "600.00",
    "guest_names": ["John Doe", "Jane Smith"]
  }
]
```

---

## Stay Management Endpoints

### Check-in Offline

**Endpoint:** `POST /api/guest/stays/checkin-offline/`

**Description:** Creates pending stay records with room assignments. This endpoint is used for offline check-in processes where guests are pre-registered but their identity needs to be verified later. It creates a booking record to group multiple stays and handles both single and multiple room assignments.

**Required Permissions:**
- `permissions.IsAuthenticated`
- `IsHotelStaff`
- `CanViewAndManageStays`
- `IsSameHotelUser`

**Request Format:** JSON

#### Required Fields:

| Field | Type | Description |
|-------|------|-------------|
| `primary_guest_id` | Integer | ID of the primary guest who has been previously created |
| `room_ids` | Array[Integer] | List of room IDs to assign to the guest(s) |
| `check_in_date` | DateTime | Check-in date and time (ISO format) |
| `check_out_date` | DateTime | Check-out date and time (ISO format) |

#### Optional Fields:

| Field | Type | Description |
|-------|------|-------------|
| `guest_names` | Array[String] | Names of guests for each room. If not provided, primary guest's full name will be used for all rooms |

#### Business Logic:

1. **Validation:**
   - Primary guest must exist and be accessible to the hotel
   - All rooms must exist and belong to the same hotel
   - All rooms must have `status = 'available'`
   - Check-out date must be after check-in date

2. **Processing:**
   - Creates a dummy booking record to group all stays
   - Creates a stay record for each room
   - Updates room status to 'occupied'
   - Sets room's current_guest to the primary guest
   - Initial stay status is set to 'pending'
   - Identity verification flag is set to `False`

3. **Single vs Multiple Room Handling:**
   - **Single Room:** Creates one stay record with the primary guest
   - **Multiple Rooms:** Creates multiple stay records, one for each room, all linked to the same booking and primary guest

4. **Single vs Multiple Guest Handling:**
   - The system uses a primary guest model where one guest is responsible for multiple rooms
   - Guest names array allows specifying different guest names for each room
   - If guest_names length < room_ids length, primary guest's name is used for remaining rooms

#### Request Examples:

**Single Room Check-in:**
```json
{
  "primary_guest_id": 123,
  "room_ids": [456],
  "check_in_date": "2024-01-15T14:00:00Z",
  "check_out_date": "2024-01-18T11:00:00Z",
  "guest_names": ["John Doe"]
}
```

**Multiple Room Check-in:**
```json
{
  "primary_guest_id": 123,
  "room_ids": [456, 457, 458],
  "check_in_date": "2024-01-15T14:00:00Z",
  "check_out_date": "2024-01-18T11:00:00Z",
  "guest_names": ["John Doe", "Jane Smith", "Bob Johnson"]
}
```

**Multiple Room without Guest Names:**
```json
{
  "primary_guest_id": 123,
  "room_ids": [456, 457],
  "check_in_date": "2024-01-15T14:00:00Z",
  "check_out_date": "2024-01-18T11:00:00Z"
}
```
*Result: Both rooms will have "John Doe" as guest name (assuming primary guest's name is John Doe)*

#### Success Response (201 Created):
```json
{
  "booking_id": 789,
  "stay_ids": [101, 102, 103],
  "message": "Check-in created successfully. Pending verification."
}
```

#### Error Responses:

**400 Bad Request - Room Not Available:**
```json
{
  "error": "Room 456 is not available"
}
```

**400 Bad Request - General Error:**
```json
{
  "error": "Failed to create check-in: [error details]"
}
```

**404 Not Found - Guest/Room Not Found:**
```json
{
  "detail": "Not found."
}
```

---

### Verify Check-in

**Endpoint:** `PATCH /api/guest/stays/{stay_id}/verify-checkin/`

**Description:** Verifies and activates a pending stay. This endpoint is used to complete the check-in process by updating the register number, optionally changing room assignments, updating guest information, and marking the stay as active. This is typically done after manual identity verification by hotel staff.

**Required Permissions:**
- `permissions.IsAuthenticated`
- `CanViewAndManageStays`
- `IsSameHotelUser`

**Request Format:** JSON

**Prerequisites:**
- Stay must have `status = 'pending'`
- Stay must belong to the same hotel as the requesting user

#### All Fields are Optional:

| Field | Type | Description |
|-------|------|-------------|
| `register_number` | String | Official register number for the stay (can be empty string) |
| `room_id` | Integer | New room ID if room change is needed |
| `guest_updates` | Object | Dictionary of guest fields to update |

#### Guest Updates Object:
The `guest_updates` object can contain any of these Guest model fields:

| Field | Type | Description |
|-------|------|-------------|
| `full_name` | String | Guest's full name |
| `email` | String | Guest's email address |
| `date_of_birth` | Date | Guest's date of birth |
| `nationality` | String | Guest's nationality |
| `preferred_language` | String | Guest's preferred language (e.g., 'en', 'es') |
| `notes` | String | Additional notes about the guest |

#### Business Logic:

1. **Validation:**
   - Stay must be in 'pending' status
   - If room_id is provided, new room must exist and belong to the same hotel

2. **Processing:**
   - Updates register number if provided
   - **Room Change Logic:** If new room is specified:
     - Frees up the old room (sets status to 'available', clears current_guest)
     - Occupies the new room (sets status to 'occupied', sets current_guest)
     - Updates the stay's room reference
   - Updates guest information if guest_updates provided
   - Marks identity as verified (`identity_verified = True`)
   - Updates stay status to 'active'
   - Sets `actual_check_in` to current timestamp
   - Updates guest status to 'checked_in'
   - Updates booking status to 'confirmed' if all associated stays are active

3. **Transactional Integrity:**
   - All operations are wrapped in a database transaction
   - If any operation fails, all changes are rolled back

#### Request Examples:

**Basic Verification (register number only):**
```json
{
  "register_number": "REG-2024-00123"
}
```

**Room Change During Verification:**
```json
{
  "register_number": "REG-2024-00124",
  "room_id": 459
}
```

**Guest Information Update:**
```json
{
  "register_number": "REG-2024-00125",
  "guest_updates": {
    "full_name": "Johnathan Doe",
    "email": "john.doe.updated@example.com",
    "nationality": "US",
    "preferred_language": "en",
    "notes": "VIP guest - prefers early check-in"
  }
}
```

**Complete Update Example:**
```json
{
  "register_number": "REG-2024-00126",
  "room_id": 460,
  "guest_updates": {
    "full_name": "John Doe",
    "email": "john.doe@example.com",
    "date_of_birth": "1985-06-15",
    "nationality": "Canada",
    "preferred_language": "en",
    "notes": "Business traveler, requests newspaper"
  }
}
```

#### Success Response (200 OK):
```json
{
  "stay_id": 101,
  "register_number": "REG-2024-00123",
  "message": "Check-in verified and activated successfully"
}
```

#### Error Responses:

**400 Bad Request - Stay Not Pending:**
```json
{
  "error": "Stay is not pending. Current status: active"
}
```

**400 Bad Request - General Error:**
```json
{
  "error": "Failed to verify check-in: [error details]"
}
```

**404 Not Found - Stay Not Found:**
```json
{
  "detail": "Not found."
}
```

**404 Not Found - Room Not Found (for room change):**
```json
{
  "detail": "Not found."
}
```

### List Pending Stays

**Endpoint:** `GET /api/guest/stays/pending-stays/`

**Description:** Lists all stays that are pending verification. This endpoint is used by hotel staff to see which guests have completed the offline check-in process but still need identity verification and activation.

**Required Permissions:**
- `permissions.IsAuthenticated`
- `CanViewAndManageStays`
- `IsSameHotelUser`

**Query Parameters:** None

**Response Format:** JSON Array

#### Business Logic:
- Filters stays to only show those with `status = 'pending'`
- Only returns stays belonging to the user's hotel
- Orders results by creation date (newest first)
- Includes guest information and room details for each pending stay

#### Success Response (200 OK):
```json
[
  {
    "id": 101,
    "guest": {
      "id": 123,
      "whatsapp_number": "+1234567890",
      "full_name": "John Doe",
      "email": "john@example.com",
      "status": "pending_checkin",
      "is_primary_guest": true,
      "documents": [
        {
          "id": 456,
          "document_type": "aadhar_id",
          "document_number": "1234-5678-9012",
          "is_verified": false,
          "document_file_url": "https://example.com/media/docs/front.jpg",
          "document_file_back_url": "https://example.com/media/docs/back.jpg"
        }
      ]
    },
    "status": "pending",
    "check_in_date": "2024-01-15T14:00:00Z",
    "check_out_date": "2024-01-18T11:00:00Z",
    "room": 201,
    "room_details": {
      "id": 201,
      "room_number": "101",
      "floor": 1,
      "category": "Deluxe"
    },
    "register_number": null,
    "identity_verified": false
  },
  {
    "id": 102,
    "guest": {
      "id": 124,
      "whatsapp_number": "+1234567891",
      "full_name": "Jane Smith",
      "email": "jane@example.com",
      "status": "pending_checkin",
      "is_primary_guest": true,
      "documents": [
        {
          "id": 457,
          "document_type": "driving_license",
          "document_number": "DL123456",
          "is_verified": false,
          "document_file_url": "https://example.com/media/docs/license_front.jpg",
          "document_file_back_url": "https://example.com/media/docs/license_back.jpg"
        }
      ]
    },
    "status": "pending",
    "check_in_date": "2024-01-15T15:00:00Z",
    "check_out_date": "2024-01-17T11:00:00Z",
    "room": 202,
    "room_details": {
      "id": 202,
      "room_number": "102",
      "floor": 1,
      "category": "Standard"
    },
    "register_number": null,
    "identity_verified": false
  }
]
```

#### Error Responses:

**401 Unauthorized:**
```json
{
  "detail": "Authentication credentials were not provided."
}
```

**403 Forbidden:**
```json
{
  "detail": "You do not have permission to perform this action."
}
```

### List Checked-in Users

**Endpoint:** `GET /api/guest/stays/checked-in-users/`

**Description:** Lists all guests who are currently checked-in (active stays). This endpoint is used by hotel staff to see which guests are currently occupying rooms and have completed the check-in process.

**Required Permissions:**
- `permissions.IsAuthenticated`
- `CanViewAndManageStays`
- `IsSameHotelUser`

**Query Parameters:** None

**Response Format:** JSON Array

#### Business Logic:
- Filters stays to only show those with `status = 'active'`
- Only returns stays belonging to the user's hotel
- Orders results by actual check-in time (most recent first)
- Includes guest information and room details for each active stay

#### Success Response (200 OK):
```json
[
  {
    "id": 103,
    "guest": {
      "id": 125,
      "whatsapp_number": "+1234567893",
      "full_name": "Michael Brown",
      "email": "michael@example.com",
      "status": "checked_in",
      "is_primary_guest": true,
      "documents": [
        {
          "id": 458,
          "document_type": "passport",
          "document_number": "P12345678",
          "is_verified": true,
          "document_file_url": "https://example.com/media/docs/passport.jpg",
          "document_file_back_url": null
        }
      ]
    },
    "status": "active",
    "check_in_date": "2024-01-14T16:00:00Z",
    "check_out_date": "2024-01-17T11:00:00Z",
    "room": 301,
    "room_details": {
      "id": 301,
      "room_number": "201",
      "floor": 2,
      "category": "Suite"
    },
    "register_number": "REG-2024-00127",
    "identity_verified": true
  },
  {
    "id": 104,
    "guest": {
      "id": 126,
      "whatsapp_number": "+1234567894",
      "full_name": "Sarah Davis",
      "email": "sarah@example.com",
      "status": "checked_in",
      "is_primary_guest": true,
      "documents": [
        {
          "id": 459,
          "document_type": "national_id",
          "document_number": "NID987654",
          "is_verified": true,
          "document_file_url": "https://example.com/media/docs/id_front.jpg",
          "document_file_back_url": "https://example.com/media/docs/id_back.jpg"
        }
      ]
    },
    "status": "active",
    "check_in_date": "2024-01-14T15:30:00Z",
    "check_out_date": "2024-01-16T11:00:00Z",
    "room": 302,
    "room_details": {
      "id": 302,
      "room_number": "202",
      "floor": 2,
      "category": "Deluxe"
    },
    "register_number": "REG-2024-00128",
    "identity_verified": true
  }
]
```

#### Error Responses:

**401 Unauthorized:**
```json
{
  "detail": "Authentication credentials were not provided."
}
```

**403 Forbidden:**
```json
{
  "detail": "You do not have permission to perform this action."
}
```

### Check Out User

**Endpoint:** `POST /api/guest/stays/{stay_id}/checkout/`

**Description:** Checks out a guest by changing the stay status to completed and updating related records. This endpoint handles the complete checkout process including guest status updates and room status changes.

**Required Permissions:**
- `permissions.IsAuthenticated`
- `CanViewAndManageStays`
- `IsSameHotelUser`

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `stay_id` | Integer | ID of the stay to check out |

**Request Format:** JSON (empty body)

**Prerequisites:**
- Stay must have `status = 'active'`
- Stay must belong to the same hotel as the requesting user

#### Business Logic:

1. **Validation:**
   - Stay must be in 'active' status (not already checked out)
   - Stay must belong to the user's hotel

2. **Processing:**
   - Updates stay status from 'active' to 'completed'
   - Sets `actual_check_out` to current timestamp
   - Updates guest status from 'checked_in' to 'checked_out'
   - Updates room status from 'occupied' to 'cleaning'
   - Clears room's current_guest field

3. **Transactional Integrity:**
   - All operations are wrapped in a database transaction
   - If any operation fails, all changes are rolled back

#### Success Response (200 OK):
```json
{
  "stay_id": 103,
  "message": "Guest checked out successfully"
}
```

#### Error Responses:

**400 Bad Request - Stay Not Active:**
```json
{
  "error": "Stay is not active. Current status: completed"
}
```

**400 Bad Request - General Error:**
```json
{
  "error": "Failed to check out guest: [error details]"
}
```

**404 Not Found - Stay Not Found:**
```json
{
  "detail": "Not found."
}
```

**401 Unauthorized:**
```json
{
  "detail": "Authentication credentials were not provided."
}
```

**403 Forbidden:**
```json
{
  "detail": "You do not have permission to perform this action."
}
```

---

## Usage Patterns and Workflows

### Typical Offline Check-in Workflow:

1. **Pre-registration:** Guest information is collected via the `create-guest` endpoint
2. **Offline Check-in:** Hotel staff uses `checkin-offline` to assign rooms and create pending stays
3. **Identity Verification:** Staff verifies guest documents manually
4. **Activation:** Staff uses `verify-checkin` to activate the stays with register numbers

### Multi-room Booking Example:

**Scenario:** A company books 3 rooms for 3 different employees

1. Create primary guest (company contact or first employee)
2. Check-in offline:
   ```json
   {
     "primary_guest_id": 123,
     "room_ids": [201, 202, 203],
     "check_in_date": "2024-01-15T14:00:00Z",
     "check_out_date": "2024-01-18T11:00:00Z",
     "guest_names": ["Alice Johnson", "Bob Smith", "Carol White"]
   }
   ```
3. Verify each stay individually with their respective register numbers

### Room Change During Check-in:

**Scenario:** Guest needs a different room after initial assignment

1. Initial check-in creates stay with room 201
2. During verification, staff finds room 201 has maintenance issues
3. Use verify-checkin with room change:
   ```json
   {
     "register_number": "REG-2024-00130",
     "room_id": 205
   }
   ```
4. System automatically frees room 201 and occupies room 205

### Guest Checkout Workflow:

**Scenario:** Guest is leaving the hotel and needs to be checked out

1. **View Current Occupancy:** Staff uses `checked-in-users` to see all current guests:
   ```
   GET /api/guest/stays/checked-in-users/
   ```

2. **Process Checkout:** When guest is ready to leave, staff calls checkout:
   ```
   POST /api/guest/stays/103/checkout/
   ```
   (Where 103 is the stay_id)

3. **System Actions:**
   - Changes stay status to 'completed'
   - Updates guest status to 'checked_out'
   - Marks room as 'cleaning' (not 'available')
   - Clears guest from room assignment
   - Records checkout timestamp

4. **Room Ready for Next Guest:** After cleaning, staff manually update room status to 'available'

---

## Error Handling Best Practices

1. **Always check room availability** before calling checkin-offline
2. **Verify stay status** before calling verify-checkin
3. **Handle transaction failures** gracefully - the system will rollback all changes
4. **Validate dates** - check-out must be after check-in
5. **Ensure hotel permissions** - all operations require proper hotel affiliation

---

## Data Model Relationships

```
Booking (1) → (N) Stay (1) → (1) Room
   ↑              ↑
   └──── Guest ───┘
```

- One booking groups multiple stays
- Each stay represents one room occupation
- All stays in a booking share the same primary guest
- Room status is automatically managed during check-in/verification