# Payment QR Code API Documentation

## Overview
The Payment QR Code API allows hotels to manage payment QR codes that can be used by guests for payments. Different user roles have different levels of access to these endpoints.

## Base URL
```
/api/hotel/payment-qr-codes/
```

## Authentication
All endpoints require authentication via JWT token or session authentication.

## User Roles & Permissions

| Role | List | View | Create | Update | Delete | Toggle Active |
|------|------|------|--------|--------|--------|---------------|
| Hotel Admin | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Manager | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Receptionist | ✅ (Active only) | ✅ | ❌ | ❌ | ❌ | ❌ |

## Data Model

### PaymentQRCode Object
```json
{
  "id": "uuid",
  "hotel": "uuid",
  "name": "string",
  "image": "file",
  "image_url": "string",
  "upi_id": "string", 
  "active": "boolean",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### Fields Description

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | UUID | Unique identifier for the QR code | `"550e8400-e29b-41d4-a716-446655440000"` |
| `hotel` | UUID | Hotel ID (auto-assigned) | `"550e8400-e29b-41d4-a716-446655440001"` |
| `name` | String | QR code display name | `"UPI Payment"` |
| `image` | File | QR code image file (upload only) | `"file upload"` |
| `image_url` | String | URL to access the QR code image | `"https://s3.amazonaws.com/hotel-documents/qr.png"` |
| `upi_id` | String | UPI ID associated with QR code | `"hotel@upi"` |
| `active` | Boolean | Whether QR code is active for use | `true` |
| `created_at` | DateTime | Creation timestamp | `"2024-01-15T10:30:00Z"` |
| `updated_at` | DateTime | Last update timestamp | `"2024-01-15T10:30:00Z"` |

## API Endpoints

### 1. List Payment QR Codes

**GET** `/api/hotel/payment-qr-codes/`

Lists all payment QR codes for the authenticated user's hotel. Receptionists see only active QR codes, while admins and managers see all QR codes.

#### Query Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `active` | Boolean | Filter by active status | `?active=true` |
| `search` | String | Search in name or UPI ID | `?search=upi` |
| `ordering` | String | Order by field | `?ordering=-created_at` |
| `page` | Integer | Page number | `?page=2` |
| `page_size` | Integer | Items per page | `?page_size=20` |

#### Response Example
```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "hotel": "550e8400-e29b-41d4-a716-446655440001",
      "name": "UPI Payment",
      "image_url": "https://s3.amazonaws.com/hotel-documents/qr-upi.png",
      "upi_id": "hotel@upi",
      "active": true,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440002",
      "hotel": "550e8400-e29b-41d4-a716-446655440001",
      "name": "Google Pay",
      "image_url": "https://s3.amazonaws.com/hotel-documents/qr-gpay.png",
      "upi_id": "hotel@gpay",
      "active": true,
      "created_at": "2024-01-14T15:20:00Z",
      "updated_at": "2024-01-14T15:20:00Z"
    }
  ]
}
```

#### Status Codes
- `200 OK` - QR codes retrieved successfully
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - User not associated with a hotel

---

### 2. Create Payment QR Code

**POST** `/api/hotel/payment-qr-codes/`

Creates a new payment QR code. Only accessible by hotel admins and managers.

#### Request Body (multipart/form-data)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | String | Yes | QR code display name |
| `image` | File | Yes | QR code image file |
| `upi_id` | String | Yes | UPI ID associated with QR code |
| `active` | Boolean | No | Whether QR code is active (default: true) |

#### Request Example
```javascript
const formData = new FormData();
formData.append('name', 'PhonePe Payment');
formData.append('image', qrImageFile);
formData.append('upi_id', 'hotel@phonepe');
formData.append('active', 'true');

fetch('/api/hotel/payment-qr-codes/', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer your-token',
  },
  body: formData
});
```

#### Response Example
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440003",
  "hotel": "550e8400-e29b-41d4-a716-446655440001",
  "name": "PhonePe Payment",
  "image_url": "https://s3.amazonaws.com/hotel-documents/qr-phonepe.png",
  "upi_id": "hotel@phonepe",
  "active": true,
  "created_at": "2024-01-16T09:15:00Z",
  "updated_at": "2024-01-16T09:15:00Z"
}
```

#### Status Codes
- `201 Created` - QR code created successfully
- `400 Bad Request` - Invalid input data
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - User is not admin or manager

---

### 3. Retrieve Payment QR Code

**GET** `/api/hotel/payment-qr-codes/{id}/`

Retrieves details of a specific payment QR code.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | UUID | QR code ID |

#### Response Example
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "hotel": "550e8400-e29b-41d4-a716-446655440001",
  "name": "UPI Payment",
  "image_url": "https://s3.amazonaws.com/hotel-documents/qr-upi.png",
  "upi_id": "hotel@upi",
  "active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

#### Status Codes
- `200 OK` - QR code retrieved successfully
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - User not authorized to view this QR code
- `404 Not Found` - QR code not found

---

### 4. Update Payment QR Code

**PUT** `/api/hotel/payment-qr-codes/{id}/`

Updates all fields of a payment QR code. Only accessible by hotel admins and managers.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | UUID | QR code ID |

#### Request Body (multipart/form-data)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | String | Yes | QR code display name |
| `image` | File | Optional | QR code image file |
| `upi_id` | String | Yes | UPI ID associated with QR code |
| `active` | Boolean | No | Whether QR code is active |

#### Response Example
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "hotel": "550e8400-e29b-41d4-a716-446655440001",
  "name": "UPI Payment - Updated",
  "image_url": "https://s3.amazonaws.com/hotel-documents/qr-upi-new.png",
  "upi_id": "hotel@upi-updated",
  "active": false,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-16T14:20:00Z"
}
```

#### Status Codes
- `200 OK` - QR code updated successfully
- `400 Bad Request` - Invalid input data
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - User is not admin or manager
- `404 Not Found` - QR code not found

---

### 5. Partial Update Payment QR Code

**PATCH** `/api/hotel/payment-qr-codes/{id}/`

Updates specific fields of a payment QR code. Only accessible by hotel admins and managers.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | UUID | QR code ID |

#### Request Body (JSON or multipart/form-data)

```json
{
  "active": false
}
```

or

```json
{
  "name": "Updated QR Code Name"
}
```

#### Response Example
Same as PUT request but with only updated fields changed.

#### Status Codes
Same as PUT request.

---

### 6. Delete Payment QR Code

**DELETE** `/api/hotel/payment-qr-codes/{id}/`

Deletes a payment QR code. Only accessible by hotel admins and managers.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | UUID | QR code ID |

#### Response Example
```json
{
  "detail": "Payment QR code deleted successfully."
}
```

#### Status Codes
- `204 No Content` - QR code deleted successfully
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - User is not admin or manager
- `404 Not Found` - QR code not found

---

### 7. Toggle QR Code Active Status

**POST** `/api/hotel/payment-qr-codes/{id}/toggle-active/`

Toggles the active status of a QR code (active becomes inactive, inactive becomes active). Only accessible by hotel admins and managers.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | UUID | QR code ID |

#### Response Example
```json
{
  "status": "QR code activated"
}
```

or

```json
{
  "status": "QR code deactivated"
}
```

#### Status Codes
- `200 OK` - QR code status toggled successfully
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - User is not admin or manager
- `404 Not Found` - QR code not found

## Error Response Format

All error responses follow this format:

```json
{
  "detail": "Error description"
}
```

or for validation errors:

```json
{
  "field_name": ["Error message for this field"],
  "another_field": ["Error message for this field"]
}
```

## Common Error Scenarios

### 1. Authentication Required
```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 2. Permission Denied for Receptionist
```json
{
  "detail": "You do not have permission to perform this action."
}
```

### 3. Hotel Not Associated
```json
{
  "detail": "User has no hotel associated."
}
```

### 4. QR Code Not Found
```json
{
  "detail": "Not found."
}
```

### 5. Validation Error
```json
{
  "name": ["This field is required."],
  "upi_id": ["This field is required."]
}
```

## Usage Examples

### JavaScript (React/Axios)

```javascript
// List QR codes
const listQRCodes = async () => {
  try {
    const response = await axios.get('/api/hotel/payment-qr-codes/', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    return response.data;
  } catch (error) {
    console.error('Error fetching QR codes:', error.response.data);
  }
};

// Create QR code
const createQRCode = async (formData) => {
  try {
    const response = await axios.post('/api/hotel/payment-qr-codes/', formData, {
      headers: { 
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'multipart/form-data'
      }
    });
    return response.data;
  } catch (error) {
    console.error('Error creating QR code:', error.response.data);
  }
};

// Toggle active status
const toggleQRCode = async (id) => {
  try {
    const response = await axios.post(`/api/hotel/payment-qr-codes/${id}/toggle-active/`, {}, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    return response.data;
  } catch (error) {
    console.error('Error toggling QR code:', error.response.data);
  }
};
```

### Python (Requests)

```python
import requests

# List QR codes
def list_qr_codes(token):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get('/api/hotel/payment-qr-codes/', headers=headers)
    return response.json()

# Create QR code
def create_qr_code(token, name, image_path, upi_id):
    headers = {'Authorization': f'Bearer {token}'}
    with open(image_path, 'rb') as f:
        files = {'image': f}
        data = {'name': name, 'upi_id': upi_id, 'active': True}
        response = requests.post('/api/hotel/payment-qr-codes/', 
                               headers=headers, files=files, data=data)
    return response.json()

# Toggle active status
def toggle_qr_code(token, qr_code_id):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.post(f'/api/hotel/payment-qr-codes/{qr_code_id}/toggle-active/', 
                           headers=headers)
    return response.json()
```

## Notes

1. **File Upload**: QR code images are uploaded using multipart/form-data and stored using the same system as hotel documents (compatible with S3).

2. **URL Generation**: The `image_url` field automatically generates the full URL to access the QR code image, whether stored locally or on S3.

3. **Role-Based Access**: The API automatically filters results based on user roles. Receptionists only see active QR codes.

4. **Hotel Association**: QR codes are automatically associated with the authenticated user's hotel.

5. **Pagination**: List endpoints support pagination for large datasets.

6. **Search and Filtering**: List endpoints support searching by name and UPI ID, and filtering by active status.