# Platform API Type Definitions

Auto-generated definitions for Platform Admin/Staff routes.

## Endpoint: `/api/admin/create-hotel/`
**View**: `PlatformCreateHotelView`
**Permissions**: Authenticated Users, <rest_framework.permissions.OperandHolder object at 0x7827bbf9f950>

### GET, PATCH, POST, PUT
**Serializer: `UserSerializer`**
```json
{
  id: integer
  username*: string // Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.
  email*: string
  user_type: enum
  phone_number: string
  password: string
  hotel: string
  created_by: string
  is_active_hotel_user: boolean
  is_verified: boolean
  department: json/object
}
```

---

## Endpoint: `/api/admin/^users/$`
**View**: `PlatformUserViewSet`
**Permissions**: Public

### GET, POST
**Serializer: `UserSerializer`**
```json
{
  id: integer
  username*: string // Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.
  email*: string
  user_type: enum
  phone_number: string
  password: string
  hotel: string
  created_by: string
  is_active_hotel_user: boolean
  is_verified: boolean
  department: json/object
}
```

---

## Endpoint: `/api/admin/^users\.(?P<format>[a-z0-9]+)/?$`
**View**: `PlatformUserViewSet`
**Permissions**: Public

### GET, POST
**Serializer: `UserSerializer`**
```json
{
  id: integer
  username*: string // Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.
  email*: string
  user_type: enum
  phone_number: string
  password: string
  hotel: string
  created_by: string
  is_active_hotel_user: boolean
  is_verified: boolean
  department: json/object
}
```

---

## Endpoint: `/api/admin/^users/(?P<pk>[^/.]+)/$`
**View**: `PlatformUserViewSet`
**Permissions**: Public

### DELETE, GET, PATCH, PUT
**Serializer: `UserSerializer`**
```json
{
  id: integer
  username*: string // Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.
  email*: string
  user_type: enum
  phone_number: string
  password: string
  hotel: string
  created_by: string
  is_active_hotel_user: boolean
  is_verified: boolean
  department: json/object
}
```

---

## Endpoint: `/api/admin/^users/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$`
**View**: `PlatformUserViewSet`
**Permissions**: Public

### DELETE, GET, PATCH, PUT
**Serializer: `UserSerializer`**
```json
{
  id: integer
  username*: string // Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.
  email*: string
  user_type: enum
  phone_number: string
  password: string
  hotel: string
  created_by: string
  is_active_hotel_user: boolean
  is_verified: boolean
  department: json/object
}
```

---

## Endpoint: `/api/admin/^hotels/$`
**View**: `AdminHotelViewSet`
**Permissions**: Authenticated Users, CanManagePlatform

### GET, POST
**Serializer: `HotelSerializer`**
```json
{
  id: string
  name*: string
  description: string
  address: string
  city: string
  state: string
  country: string
  pincode: string
  phone: string
  email: string
  google_review_link: string // Google Review link for the hotel
  latitude: string
  longitude: string
  qr_code_url: string
  unique_qr_code: string
  check_in_time: string
  time_zone: string
  breakfast_reminder: boolean // Enable breakfast reminders for guests
  dinner_reminder: boolean // Enable dinner reminders for guests
  status: enum
  is_verified: boolean
  is_active: boolean
  is_demo: boolean
  verification_notes: string // Notes for verification process by platform admin.
  registration_date: datetime (ISO 8601)
  verified_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  admin: string
  documents: Array[{'id': {'type': 'string', 'required': False}, 'hotel': {'type': 'string', 'required': False}, 'document_type': {'type': 'enum', 'required': True}, 'document_file': {'type': 'file', 'required': True}, 'document_file_url': {'type': 'string', 'required': False}, 'uploaded_at': {'type': 'datetime (ISO 8601)', 'required': False}}]
}
```

---

## Endpoint: `/api/admin/^hotels\.(?P<format>[a-z0-9]+)/?$`
**View**: `AdminHotelViewSet`
**Permissions**: Authenticated Users, CanManagePlatform

### GET, POST
**Serializer: `HotelSerializer`**
```json
{
  id: string
  name*: string
  description: string
  address: string
  city: string
  state: string
  country: string
  pincode: string
  phone: string
  email: string
  google_review_link: string // Google Review link for the hotel
  latitude: string
  longitude: string
  qr_code_url: string
  unique_qr_code: string
  check_in_time: string
  time_zone: string
  breakfast_reminder: boolean // Enable breakfast reminders for guests
  dinner_reminder: boolean // Enable dinner reminders for guests
  status: enum
  is_verified: boolean
  is_active: boolean
  is_demo: boolean
  verification_notes: string // Notes for verification process by platform admin.
  registration_date: datetime (ISO 8601)
  verified_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  admin: string
  documents: Array[{'id': {'type': 'string', 'required': False}, 'hotel': {'type': 'string', 'required': False}, 'document_type': {'type': 'enum', 'required': True}, 'document_file': {'type': 'file', 'required': True}, 'document_file_url': {'type': 'string', 'required': False}, 'uploaded_at': {'type': 'datetime (ISO 8601)', 'required': False}}]
}
```

---

## Endpoint: `/api/admin/^hotels/(?P<pk>[^/.]+)/$`
**View**: `AdminHotelViewSet`
**Permissions**: Authenticated Users, CanManagePlatform

### GET
**Serializer: `HotelSerializer`**
```json
{
  id: string
  name*: string
  description: string
  address: string
  city: string
  state: string
  country: string
  pincode: string
  phone: string
  email: string
  google_review_link: string // Google Review link for the hotel
  latitude: string
  longitude: string
  qr_code_url: string
  unique_qr_code: string
  check_in_time: string
  time_zone: string
  breakfast_reminder: boolean // Enable breakfast reminders for guests
  dinner_reminder: boolean // Enable dinner reminders for guests
  status: enum
  is_verified: boolean
  is_active: boolean
  is_demo: boolean
  verification_notes: string // Notes for verification process by platform admin.
  registration_date: datetime (ISO 8601)
  verified_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  admin: string
  documents: Array[{'id': {'type': 'string', 'required': False}, 'hotel': {'type': 'string', 'required': False}, 'document_type': {'type': 'enum', 'required': True}, 'document_file': {'type': 'file', 'required': True}, 'document_file_url': {'type': 'string', 'required': False}, 'uploaded_at': {'type': 'datetime (ISO 8601)', 'required': False}}]
}
```

### PATCH, PUT
**Serializer: `AdminHotelUpdateSerializer`**
```json
{
  name*: string
  description: string
  address: string
  city: string
  state: string
  country: string
  pincode: string
  phone: string
  email: string
  google_review_link: string // Google Review link for the hotel
  latitude: string
  longitude: string
  qr_code_url: string
  check_in_time: string
  time_zone: string
  breakfast_reminder: boolean // Enable breakfast reminders for guests
  dinner_reminder: boolean // Enable dinner reminders for guests
}
```

---

## Endpoint: `/api/admin/^hotels/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$`
**View**: `AdminHotelViewSet`
**Permissions**: Authenticated Users, CanManagePlatform

### GET
**Serializer: `HotelSerializer`**
```json
{
  id: string
  name*: string
  description: string
  address: string
  city: string
  state: string
  country: string
  pincode: string
  phone: string
  email: string
  google_review_link: string // Google Review link for the hotel
  latitude: string
  longitude: string
  qr_code_url: string
  unique_qr_code: string
  check_in_time: string
  time_zone: string
  breakfast_reminder: boolean // Enable breakfast reminders for guests
  dinner_reminder: boolean // Enable dinner reminders for guests
  status: enum
  is_verified: boolean
  is_active: boolean
  is_demo: boolean
  verification_notes: string // Notes for verification process by platform admin.
  registration_date: datetime (ISO 8601)
  verified_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  admin: string
  documents: Array[{'id': {'type': 'string', 'required': False}, 'hotel': {'type': 'string', 'required': False}, 'document_type': {'type': 'enum', 'required': True}, 'document_file': {'type': 'file', 'required': True}, 'document_file_url': {'type': 'string', 'required': False}, 'uploaded_at': {'type': 'datetime (ISO 8601)', 'required': False}}]
}
```

### PATCH, PUT
**Serializer: `AdminHotelUpdateSerializer`**
```json
{
  name*: string
  description: string
  address: string
  city: string
  state: string
  country: string
  pincode: string
  phone: string
  email: string
  google_review_link: string // Google Review link for the hotel
  latitude: string
  longitude: string
  qr_code_url: string
  check_in_time: string
  time_zone: string
  breakfast_reminder: boolean // Enable breakfast reminders for guests
  dinner_reminder: boolean // Enable dinner reminders for guests
}
```

---

## Endpoint: `/api/admin/hotels/<uuid:hotel_pk>/^documents/$`
**View**: `AdminHotelDocumentViewSet`
**Permissions**: Authenticated Users, CanManagePlatform

### GET, POST
**Serializer: `HotelDocumentSerializer`**
```json
{
  id: string
  hotel: string
  document_type*: enum
  document_file*: file
  document_file_url: string
  uploaded_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/admin/hotels/<uuid:hotel_pk>/^documents\.(?P<format>[a-z0-9]+)/?$`
**View**: `AdminHotelDocumentViewSet`
**Permissions**: Authenticated Users, CanManagePlatform

### GET, POST
**Serializer: `HotelDocumentSerializer`**
```json
{
  id: string
  hotel: string
  document_type*: enum
  document_file*: file
  document_file_url: string
  uploaded_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/admin/hotels/<uuid:hotel_pk>/^documents/(?P<pk>[^/.]+)/$`
**View**: `AdminHotelDocumentViewSet`
**Permissions**: Authenticated Users, CanManagePlatform

### GET
**Serializer: `HotelDocumentSerializer`**
```json
{
  id: string
  hotel: string
  document_type*: enum
  document_file*: file
  document_file_url: string
  uploaded_at: datetime (ISO 8601)
}
```

### PATCH, PUT
**Serializer: `AdminHotelDocumentUpdateSerializer`**
```json
{
  id: string
  hotel: string
  document_type*: enum
  document_file: file
  document_file_url: string
  uploaded_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/admin/hotels/<uuid:hotel_pk>/^documents/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$`
**View**: `AdminHotelDocumentViewSet`
**Permissions**: Authenticated Users, CanManagePlatform

### GET
**Serializer: `HotelDocumentSerializer`**
```json
{
  id: string
  hotel: string
  document_type*: enum
  document_file*: file
  document_file_url: string
  uploaded_at: datetime (ISO 8601)
}
```

### PATCH, PUT
**Serializer: `AdminHotelDocumentUpdateSerializer`**
```json
{
  id: string
  hotel: string
  document_type*: enum
  document_file: file
  document_file_url: string
  uploaded_at: datetime (ISO 8601)
}
```

---

