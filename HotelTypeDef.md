# Hotel API Type Definitions

Auto-generated definitions for Hotel Admin/Staff routes.

## Endpoint: `/api/hotel/staff/create/`
**View**: `HotelStaffRegistrationView`
**Permissions**: Authenticated Users, IsHotelAdmin

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

## Endpoint: `/api/logout/`
**View**: `LogoutView`
**Permissions**: Authenticated Users

### POST
**Manual Definition**
```json
{
  refresh*: string
}
```

---

## Endpoint: `/api/change-password/`
**View**: `ChangePasswordView`
**Permissions**: Authenticated Users, IsHotelAdmin

### POST
**Manual Definition**
```json
{
  old_password*: string
  new_password*: string
}
```

---

## Endpoint: `/api/^users/$`
**View**: `UserViewSet`
**Permissions**: Authenticated Users

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

## Endpoint: `/api/^users\.(?P<format>[a-z0-9]+)/?$`
**View**: `UserViewSet`
**Permissions**: Authenticated Users

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

## Endpoint: `/api/^users/(?P<pk>[^/.]+)/$`
**View**: `UserViewSet`
**Permissions**: Authenticated Users

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

## Endpoint: `/api/^users/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$`
**View**: `UserViewSet`
**Permissions**: Authenticated Users

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

## Endpoint: `/api/^room-categories/$`
**View**: `RoomCategoryViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, IsHotelStaffReadOnlyOrAdmin

### GET, POST
**Serializer: `RoomCategorySerializer`**
```json
{
  id: integer
  room_count: string
  name*: string
  description: string
  base_price*: string
  max_occupancy*: integer
  amenities: json/object
  created_at: datetime (ISO 8601)
  hotel: string
}
```

---

## Endpoint: `/api/^room-categories\.(?P<format>[a-z0-9]+)/?$`
**View**: `RoomCategoryViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, IsHotelStaffReadOnlyOrAdmin

### GET, POST
**Serializer: `RoomCategorySerializer`**
```json
{
  id: integer
  room_count: string
  name*: string
  description: string
  base_price*: string
  max_occupancy*: integer
  amenities: json/object
  created_at: datetime (ISO 8601)
  hotel: string
}
```

---

## Endpoint: `/api/^room-categories/(?P<pk>[^/.]+)/$`
**View**: `RoomCategoryViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, IsHotelStaffReadOnlyOrAdmin

### DELETE, GET, PATCH, PUT
**Serializer: `RoomCategorySerializer`**
```json
{
  id: integer
  room_count: string
  name*: string
  description: string
  base_price*: string
  max_occupancy*: integer
  amenities: json/object
  created_at: datetime (ISO 8601)
  hotel: string
}
```

---

## Endpoint: `/api/^room-categories/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$`
**View**: `RoomCategoryViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, IsHotelStaffReadOnlyOrAdmin

### DELETE, GET, PATCH, PUT
**Serializer: `RoomCategorySerializer`**
```json
{
  id: integer
  room_count: string
  name*: string
  description: string
  base_price*: string
  max_occupancy*: integer
  amenities: json/object
  created_at: datetime (ISO 8601)
  hotel: string
}
```

---

## Endpoint: `/api/^rooms/$`
**View**: `RoomViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, RoomPermissions

### GET, POST
**Serializer: `RoomSerializer`**
```json
{
  id: integer
  status_display: string
  room_number*: string
  floor*: integer
  status: enum
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel: string
  category*: string
  current_guest: string
}
```

---

## Endpoint: `/api/^rooms\.(?P<format>[a-z0-9]+)/?$`
**View**: `RoomViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, RoomPermissions

### GET, POST
**Serializer: `RoomSerializer`**
```json
{
  id: integer
  status_display: string
  room_number*: string
  floor*: integer
  status: enum
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel: string
  category*: string
  current_guest: string
}
```

---

## Endpoint: `/api/^rooms/bulk-create/$`
**View**: `RoomViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, RoomPermissions

### POST
**Serializer: `RoomSerializer`**
```json
{
  id: integer
  status_display: string
  room_number*: string
  floor*: integer
  status: enum
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel: string
  category*: string
  current_guest: string
}
```

---

## Endpoint: `/api/^rooms/bulk-create\.(?P<format>[a-z0-9]+)/?$`
**View**: `RoomViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, RoomPermissions

### POST
**Serializer: `RoomSerializer`**
```json
{
  id: integer
  status_display: string
  room_number*: string
  floor*: integer
  status: enum
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel: string
  category*: string
  current_guest: string
}
```

---

## Endpoint: `/api/^rooms/floors/$`
**View**: `RoomViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, RoomPermissions

### GET
**Serializer: `RoomSerializer`**
```json
{
  id: integer
  status_display: string
  room_number*: string
  floor*: integer
  status: enum
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel: string
  category*: string
  current_guest: string
}
```

---

## Endpoint: `/api/^rooms/floors\.(?P<format>[a-z0-9]+)/?$`
**View**: `RoomViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, RoomPermissions

### GET
**Serializer: `RoomSerializer`**
```json
{
  id: integer
  status_display: string
  room_number*: string
  floor*: integer
  status: enum
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel: string
  category*: string
  current_guest: string
}
```

---

## Endpoint: `/api/^rooms/(?P<pk>[^/.]+)/$`
**View**: `RoomViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, RoomPermissions

### DELETE, GET, PUT
**Serializer: `RoomSerializer`**
```json
{
  id: integer
  status_display: string
  room_number*: string
  floor*: integer
  status: enum
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel: string
  category*: string
  current_guest: string
}
```

### PATCH
**Serializer: `RoomStatusUpdateSerializer`**
```json
{
  status: enum
}
```

---

## Endpoint: `/api/^rooms/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$`
**View**: `RoomViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, RoomPermissions

### DELETE, GET, PUT
**Serializer: `RoomSerializer`**
```json
{
  id: integer
  status_display: string
  room_number*: string
  floor*: integer
  status: enum
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel: string
  category*: string
  current_guest: string
}
```

### PATCH
**Serializer: `RoomStatusUpdateSerializer`**
```json
{
  status: enum
}
```

---

## Endpoint: `/api/^payment-qr-codes/$`
**View**: `PaymentQRCodeViewSet`
**Permissions**: Authenticated Users, Can Manage Payment QRCode

### GET, POST
**Serializer: `PaymentQRCodeSerializer`**
```json
{
  id: string
  hotel: string
  name*: string // Name/Description of the QR code (e.g., 'UPI Payment', 'PhonePe', 'Google Pay')
  image*: file // QR code image file
  image_url: string
  upi_id*: string // UPI ID associated with this QR code
  active: boolean // Whether this QR code is currently active for use
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^payment-qr-codes\.(?P<format>[a-z0-9]+)/?$`
**View**: `PaymentQRCodeViewSet`
**Permissions**: Authenticated Users, Can Manage Payment QRCode

### GET, POST
**Serializer: `PaymentQRCodeSerializer`**
```json
{
  id: string
  hotel: string
  name*: string // Name/Description of the QR code (e.g., 'UPI Payment', 'PhonePe', 'Google Pay')
  image*: file // QR code image file
  image_url: string
  upi_id*: string // UPI ID associated with this QR code
  active: boolean // Whether this QR code is currently active for use
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^payment-qr-codes/send-to-whatsapp/$`
**View**: `PaymentQRCodeViewSet`
**Permissions**: Authenticated Users, Can Manage Payment QRCode

### POST
**Serializer: `PaymentQRCodeSerializer`**
```json
{
  id: string
  hotel: string
  name*: string // Name/Description of the QR code (e.g., 'UPI Payment', 'PhonePe', 'Google Pay')
  image*: file // QR code image file
  image_url: string
  upi_id*: string // UPI ID associated with this QR code
  active: boolean // Whether this QR code is currently active for use
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^payment-qr-codes/send-to-whatsapp\.(?P<format>[a-z0-9]+)/?$`
**View**: `PaymentQRCodeViewSet`
**Permissions**: Authenticated Users, Can Manage Payment QRCode

### POST
**Serializer: `PaymentQRCodeSerializer`**
```json
{
  id: string
  hotel: string
  name*: string // Name/Description of the QR code (e.g., 'UPI Payment', 'PhonePe', 'Google Pay')
  image*: file // QR code image file
  image_url: string
  upi_id*: string // UPI ID associated with this QR code
  active: boolean // Whether this QR code is currently active for use
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^payment-qr-codes/(?P<pk>[^/.]+)/$`
**View**: `PaymentQRCodeViewSet`
**Permissions**: Authenticated Users, Can Manage Payment QRCode

### DELETE, GET, PATCH, PUT
**Serializer: `PaymentQRCodeSerializer`**
```json
{
  id: string
  hotel: string
  name*: string // Name/Description of the QR code (e.g., 'UPI Payment', 'PhonePe', 'Google Pay')
  image*: file // QR code image file
  image_url: string
  upi_id*: string // UPI ID associated with this QR code
  active: boolean // Whether this QR code is currently active for use
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^payment-qr-codes/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$`
**View**: `PaymentQRCodeViewSet`
**Permissions**: Authenticated Users, Can Manage Payment QRCode

### DELETE, GET, PATCH, PUT
**Serializer: `PaymentQRCodeSerializer`**
```json
{
  id: string
  hotel: string
  name*: string // Name/Description of the QR code (e.g., 'UPI Payment', 'PhonePe', 'Google Pay')
  image*: file // QR code image file
  image_url: string
  upi_id*: string // UPI ID associated with this QR code
  active: boolean // Whether this QR code is currently active for use
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^payment-qr-codes/(?P<pk>[^/.]+)/toggle-active/$`
**View**: `PaymentQRCodeViewSet`
**Permissions**: Authenticated Users, Can Manage Payment QRCode

### POST
**Serializer: `PaymentQRCodeSerializer`**
```json
{
  id: string
  hotel: string
  name*: string // Name/Description of the QR code (e.g., 'UPI Payment', 'PhonePe', 'Google Pay')
  image*: file // QR code image file
  image_url: string
  upi_id*: string // UPI ID associated with this QR code
  active: boolean // Whether this QR code is currently active for use
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^payment-qr-codes/(?P<pk>[^/.]+)/toggle-active\.(?P<format>[a-z0-9]+)/?$`
**View**: `PaymentQRCodeViewSet`
**Permissions**: Authenticated Users, Can Manage Payment QRCode

### POST
**Serializer: `PaymentQRCodeSerializer`**
```json
{
  id: string
  hotel: string
  name*: string // Name/Description of the QR code (e.g., 'UPI Payment', 'PhonePe', 'Google Pay')
  image*: file // QR code image file
  image_url: string
  upi_id*: string // UPI ID associated with this QR code
  active: boolean // Whether this QR code is currently active for use
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^wifi-credentials/$`
**View**: `WiFiCredentialViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, IsHotelStaffReadOnlyOrAdmin

### GET, POST
**Serializer: `WiFiCredentialSerializer`**
```json
{
  id: string
  hotel: string
  floor*: integer // Floor number for these WiFi credentials
  room_category: string // Room category for these credentials. If null, applies to all categories on this floor.
  room_category_name: string
  network_name*: string // WiFi network name (SSID)
  password*: string // WiFi password for this floor/category
  is_active: boolean // Whether these WiFi credentials are currently active
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^wifi-credentials\.(?P<format>[a-z0-9]+)/?$`
**View**: `WiFiCredentialViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, IsHotelStaffReadOnlyOrAdmin

### GET, POST
**Serializer: `WiFiCredentialSerializer`**
```json
{
  id: string
  hotel: string
  floor*: integer // Floor number for these WiFi credentials
  room_category: string // Room category for these credentials. If null, applies to all categories on this floor.
  room_category_name: string
  network_name*: string // WiFi network name (SSID)
  password*: string // WiFi password for this floor/category
  is_active: boolean // Whether these WiFi credentials are currently active
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^wifi-credentials/available-floors/$`
**View**: `WiFiCredentialViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, IsHotelStaffReadOnlyOrAdmin

### GET
**Serializer: `WiFiCredentialSerializer`**
```json
{
  id: string
  hotel: string
  floor*: integer // Floor number for these WiFi credentials
  room_category: string // Room category for these credentials. If null, applies to all categories on this floor.
  room_category_name: string
  network_name*: string // WiFi network name (SSID)
  password*: string // WiFi password for this floor/category
  is_active: boolean // Whether these WiFi credentials are currently active
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^wifi-credentials/available-floors\.(?P<format>[a-z0-9]+)/?$`
**View**: `WiFiCredentialViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, IsHotelStaffReadOnlyOrAdmin

### GET
**Serializer: `WiFiCredentialSerializer`**
```json
{
  id: string
  hotel: string
  floor*: integer // Floor number for these WiFi credentials
  room_category: string // Room category for these credentials. If null, applies to all categories on this floor.
  room_category_name: string
  network_name*: string // WiFi network name (SSID)
  password*: string // WiFi password for this floor/category
  is_active: boolean // Whether these WiFi credentials are currently active
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^wifi-credentials/by-floor/(?P<floor>[^/.]+)/$`
**View**: `WiFiCredentialViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, IsHotelStaffReadOnlyOrAdmin

### GET
**Serializer: `WiFiCredentialSerializer`**
```json
{
  id: string
  hotel: string
  floor*: integer // Floor number for these WiFi credentials
  room_category: string // Room category for these credentials. If null, applies to all categories on this floor.
  room_category_name: string
  network_name*: string // WiFi network name (SSID)
  password*: string // WiFi password for this floor/category
  is_active: boolean // Whether these WiFi credentials are currently active
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^wifi-credentials/by-floor/(?P<floor>[^/.]+)\.(?P<format>[a-z0-9]+)/?$`
**View**: `WiFiCredentialViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, IsHotelStaffReadOnlyOrAdmin

### GET
**Serializer: `WiFiCredentialSerializer`**
```json
{
  id: string
  hotel: string
  floor*: integer // Floor number for these WiFi credentials
  room_category: string // Room category for these credentials. If null, applies to all categories on this floor.
  room_category_name: string
  network_name*: string // WiFi network name (SSID)
  password*: string // WiFi password for this floor/category
  is_active: boolean // Whether these WiFi credentials are currently active
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^wifi-credentials/by-room/(?P<room_id>[^/.]+)/$`
**View**: `WiFiCredentialViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, IsHotelStaffReadOnlyOrAdmin

### GET
**Serializer: `WiFiCredentialSerializer`**
```json
{
  id: string
  hotel: string
  floor*: integer // Floor number for these WiFi credentials
  room_category: string // Room category for these credentials. If null, applies to all categories on this floor.
  room_category_name: string
  network_name*: string // WiFi network name (SSID)
  password*: string // WiFi password for this floor/category
  is_active: boolean // Whether these WiFi credentials are currently active
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^wifi-credentials/by-room/(?P<room_id>[^/.]+)\.(?P<format>[a-z0-9]+)/?$`
**View**: `WiFiCredentialViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, IsHotelStaffReadOnlyOrAdmin

### GET
**Serializer: `WiFiCredentialSerializer`**
```json
{
  id: string
  hotel: string
  floor*: integer // Floor number for these WiFi credentials
  room_category: string // Room category for these credentials. If null, applies to all categories on this floor.
  room_category_name: string
  network_name*: string // WiFi network name (SSID)
  password*: string // WiFi password for this floor/category
  is_active: boolean // Whether these WiFi credentials are currently active
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^wifi-credentials/(?P<pk>[^/.]+)/$`
**View**: `WiFiCredentialViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, IsHotelStaffReadOnlyOrAdmin

### DELETE, GET, PATCH, PUT
**Serializer: `WiFiCredentialSerializer`**
```json
{
  id: string
  hotel: string
  floor*: integer // Floor number for these WiFi credentials
  room_category: string // Room category for these credentials. If null, applies to all categories on this floor.
  room_category_name: string
  network_name*: string // WiFi network name (SSID)
  password*: string // WiFi password for this floor/category
  is_active: boolean // Whether these WiFi credentials are currently active
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^wifi-credentials/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$`
**View**: `WiFiCredentialViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, IsHotelStaffReadOnlyOrAdmin

### DELETE, GET, PATCH, PUT
**Serializer: `WiFiCredentialSerializer`**
```json
{
  id: string
  hotel: string
  floor*: integer // Floor number for these WiFi credentials
  room_category: string // Room category for these credentials. If null, applies to all categories on this floor.
  room_category_name: string
  network_name*: string // WiFi network name (SSID)
  password*: string // WiFi password for this floor/category
  is_active: boolean // Whether these WiFi credentials are currently active
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^wifi-credentials/(?P<pk>[^/.]+)/toggle-active/$`
**View**: `WiFiCredentialViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, IsHotelStaffReadOnlyOrAdmin

### POST
**Serializer: `WiFiCredentialSerializer`**
```json
{
  id: string
  hotel: string
  floor*: integer // Floor number for these WiFi credentials
  room_category: string // Room category for these credentials. If null, applies to all categories on this floor.
  room_category_name: string
  network_name*: string // WiFi network name (SSID)
  password*: string // WiFi password for this floor/category
  is_active: boolean // Whether these WiFi credentials are currently active
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^wifi-credentials/(?P<pk>[^/.]+)/toggle-active\.(?P<format>[a-z0-9]+)/?$`
**View**: `WiFiCredentialViewSet`
**Permissions**: Authenticated Users, IsSameHotelUser, IsHotelStaffReadOnlyOrAdmin

### POST
**Serializer: `WiFiCredentialSerializer`**
```json
{
  id: string
  hotel: string
  floor*: integer // Floor number for these WiFi credentials
  room_category: string // Room category for these credentials. If null, applies to all categories on this floor.
  room_category_name: string
  network_name*: string // WiFi network name (SSID)
  password*: string // WiFi password for this floor/category
  is_active: boolean // Whether these WiFi credentials are currently active
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/profile/update/`
**View**: `UpdateProfileView`
**Permissions**: Authenticated Users, IsHotelAdmin

### GET, PATCH, POST, PUT
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

## Endpoint: `/api/documents/upload/`
**View**: `HotelDocumentUploadView`
**Permissions**: Authenticated Users, IsHotelAdmin

### GET, PATCH, POST, PUT
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

## Endpoint: `/api/documents/<uuid:pk>/update/`
**View**: `HotelDocumentUpdateView`
**Permissions**: Authenticated Users, IsHotelAdmin

### GET, PATCH, POST, PUT
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

## Endpoint: `/api/^guest-management/create-guest/$`
**View**: `GuestManagementViewSet`
**Permissions**: Authenticated Users, IsHotelStaff, IsSameHotelUser

### POST
**Serializer: `CreateGuestSerializer`**
```json
{
  primary_guest*: string
  accompanying_guests: string
}
```

---

## Endpoint: `/api/^guest-management/create-guest\.(?P<format>[a-z0-9]+)/?$`
**View**: `GuestManagementViewSet`
**Permissions**: Authenticated Users, IsHotelStaff, IsSameHotelUser

### POST
**Serializer: `CreateGuestSerializer`**
```json
{
  primary_guest*: string
  accompanying_guests: string
}
```

---

## Endpoint: `/api/^guest-management/bookings/$`
**View**: `GuestManagementViewSet`
**Permissions**: Authenticated Users, IsHotelStaff, IsSameHotelUser

### GET
**Serializer: `BookingListSerializer`**
```json
{
  id: integer
  primary_guest: {
    id: integer
    whatsapp_number*: string
    full_name: string
    email: string
    status: enum
    is_primary_guest: boolean
    documents: string
    nationality: string
    register_number: string
    date_of_birth: date (ISO 8601)
    preferred_language: string
    is_whatsapp_active: boolean
    loyalty_points: integer
    notes: string
  }
  check_in_date*: datetime (ISO 8601)
  check_out_date*: datetime (ISO 8601)
  status: enum
  total_amount: string
  guest_names: json/object
  is_via_whatsapp: boolean
}
```

---

## Endpoint: `/api/^guest-management/bookings\.(?P<format>[a-z0-9]+)/?$`
**View**: `GuestManagementViewSet`
**Permissions**: Authenticated Users, IsHotelStaff, IsSameHotelUser

### GET
**Serializer: `BookingListSerializer`**
```json
{
  id: integer
  primary_guest: {
    id: integer
    whatsapp_number*: string
    full_name: string
    email: string
    status: enum
    is_primary_guest: boolean
    documents: string
    nationality: string
    register_number: string
    date_of_birth: date (ISO 8601)
    preferred_language: string
    is_whatsapp_active: boolean
    loyalty_points: integer
    notes: string
  }
  check_in_date*: datetime (ISO 8601)
  check_out_date*: datetime (ISO 8601)
  status: enum
  total_amount: string
  guest_names: json/object
  is_via_whatsapp: boolean
}
```

---

## Endpoint: `/api/^guest-management/guests/$`
**View**: `GuestManagementViewSet`
**Permissions**: Authenticated Users, IsHotelStaff, IsSameHotelUser

### GET
**Serializer: `GuestResponseSerializer`**
```json
{
  id: integer
  whatsapp_number*: string
  full_name: string
  email: string
  status: enum
  is_primary_guest: boolean
  documents: string
  nationality: string
  register_number: string
  date_of_birth: date (ISO 8601)
  preferred_language: string
  is_whatsapp_active: boolean
  loyalty_points: integer
  notes: string
}
```

---

## Endpoint: `/api/^guest-management/guests\.(?P<format>[a-z0-9]+)/?$`
**View**: `GuestManagementViewSet`
**Permissions**: Authenticated Users, IsHotelStaff, IsSameHotelUser

### GET
**Serializer: `GuestResponseSerializer`**
```json
{
  id: integer
  whatsapp_number*: string
  full_name: string
  email: string
  status: enum
  is_primary_guest: boolean
  documents: string
  nationality: string
  register_number: string
  date_of_birth: date (ISO 8601)
  preferred_language: string
  is_whatsapp_active: boolean
  loyalty_points: integer
  notes: string
}
```

---

## Endpoint: `/api/^stay-management/checked-in-users/$`
**View**: `StayManagementViewSet`
**Permissions**: Authenticated Users, CanViewAndManageStays, IsSameHotelUser

### GET
**Serializer: `StayListSerializer`**
```json
{
  id: integer
  guest: {
    id: integer
    whatsapp_number*: string
    full_name: string
    email: string
    status: enum
    is_primary_guest: boolean
    documents: string
    nationality: string
    register_number: string
    date_of_birth: date (ISO 8601)
    preferred_language: string
    is_whatsapp_active: boolean
    loyalty_points: integer
    notes: string
  }
  status: enum
  check_in_date*: datetime (ISO 8601)
  check_out_date*: datetime (ISO 8601)
  room: string
  room_details: string
  register_number: string
  identity_verified: boolean
  booking_details: string
  internal_rating: integer // Internal rating from 1 to 5
  internal_note: string // Internal notes about the guest stay
  hours_24: boolean // Indicates if this is a 24-hour stay
  breakfast_reminder: boolean // Enable breakfast reminder for this stay
  dinner_reminder: boolean // Enable dinner reminder for this stay
  billing: string
}
```

---

## Endpoint: `/api/^stay-management/checked-in-users\.(?P<format>[a-z0-9]+)/?$`
**View**: `StayManagementViewSet`
**Permissions**: Authenticated Users, CanViewAndManageStays, IsSameHotelUser

### GET
**Serializer: `StayListSerializer`**
```json
{
  id: integer
  guest: {
    id: integer
    whatsapp_number*: string
    full_name: string
    email: string
    status: enum
    is_primary_guest: boolean
    documents: string
    nationality: string
    register_number: string
    date_of_birth: date (ISO 8601)
    preferred_language: string
    is_whatsapp_active: boolean
    loyalty_points: integer
    notes: string
  }
  status: enum
  check_in_date*: datetime (ISO 8601)
  check_out_date*: datetime (ISO 8601)
  room: string
  room_details: string
  register_number: string
  identity_verified: boolean
  booking_details: string
  internal_rating: integer // Internal rating from 1 to 5
  internal_note: string // Internal notes about the guest stay
  hours_24: boolean // Indicates if this is a 24-hour stay
  breakfast_reminder: boolean // Enable breakfast reminder for this stay
  dinner_reminder: boolean // Enable dinner reminder for this stay
  billing: string
}
```

---

## Endpoint: `/api/^stay-management/checkin-offline/$`
**View**: `StayManagementViewSet`
**Permissions**: Authenticated Users, CanViewAndManageStays, IsSameHotelUser

### POST
**Serializer: `CheckinOfflineSerializer`**
```json
{
  primary_guest_id*: integer
  room_ids*: string
  check_in_date*: datetime (ISO 8601)
  check_out_date*: datetime (ISO 8601)
  guest_names: string
  hours_24: boolean // Indicates if this is a 24-hour stay
}
```

---

## Endpoint: `/api/^stay-management/checkin-offline\.(?P<format>[a-z0-9]+)/?$`
**View**: `StayManagementViewSet`
**Permissions**: Authenticated Users, CanViewAndManageStays, IsSameHotelUser

### POST
**Serializer: `CheckinOfflineSerializer`**
```json
{
  primary_guest_id*: integer
  room_ids*: string
  check_in_date*: datetime (ISO 8601)
  check_out_date*: datetime (ISO 8601)
  guest_names: string
  hours_24: boolean // Indicates if this is a 24-hour stay
}
```

---

## Endpoint: `/api/^stay-management/pending-stays/$`
**View**: `StayManagementViewSet`
**Permissions**: Authenticated Users, CanViewAndManageStays, IsSameHotelUser

### GET
**Serializer: `StayListSerializer`**
```json
{
  id: integer
  guest: {
    id: integer
    whatsapp_number*: string
    full_name: string
    email: string
    status: enum
    is_primary_guest: boolean
    documents: string
    nationality: string
    register_number: string
    date_of_birth: date (ISO 8601)
    preferred_language: string
    is_whatsapp_active: boolean
    loyalty_points: integer
    notes: string
  }
  status: enum
  check_in_date*: datetime (ISO 8601)
  check_out_date*: datetime (ISO 8601)
  room: string
  room_details: string
  register_number: string
  identity_verified: boolean
  booking_details: string
  internal_rating: integer // Internal rating from 1 to 5
  internal_note: string // Internal notes about the guest stay
  hours_24: boolean // Indicates if this is a 24-hour stay
  breakfast_reminder: boolean // Enable breakfast reminder for this stay
  dinner_reminder: boolean // Enable dinner reminder for this stay
  billing: string
}
```

---

## Endpoint: `/api/^stay-management/pending-stays\.(?P<format>[a-z0-9]+)/?$`
**View**: `StayManagementViewSet`
**Permissions**: Authenticated Users, CanViewAndManageStays, IsSameHotelUser

### GET
**Serializer: `StayListSerializer`**
```json
{
  id: integer
  guest: {
    id: integer
    whatsapp_number*: string
    full_name: string
    email: string
    status: enum
    is_primary_guest: boolean
    documents: string
    nationality: string
    register_number: string
    date_of_birth: date (ISO 8601)
    preferred_language: string
    is_whatsapp_active: boolean
    loyalty_points: integer
    notes: string
  }
  status: enum
  check_in_date*: datetime (ISO 8601)
  check_out_date*: datetime (ISO 8601)
  room: string
  room_details: string
  register_number: string
  identity_verified: boolean
  booking_details: string
  internal_rating: integer // Internal rating from 1 to 5
  internal_note: string // Internal notes about the guest stay
  hours_24: boolean // Indicates if this is a 24-hour stay
  breakfast_reminder: boolean // Enable breakfast reminder for this stay
  dinner_reminder: boolean // Enable dinner reminder for this stay
  billing: string
}
```

---

## Endpoint: `/api/^stay-management/(?P<pk>[^/.]+)/checkout/$`
**View**: `StayManagementViewSet`
**Permissions**: Authenticated Users, CanViewAndManageStays, IsSameHotelUser

### POST
**Serializer: `CheckoutSerializer`**
```json
{
  internal_rating: integer // Internal rating from 1 to 5 (optional)
  internal_note: string // Internal notes about the guest stay (optional)
  flag_user: boolean // Flag this guest for future reference
}
```

---

## Endpoint: `/api/^stay-management/(?P<pk>[^/.]+)/checkout\.(?P<format>[a-z0-9]+)/?$`
**View**: `StayManagementViewSet`
**Permissions**: Authenticated Users, CanViewAndManageStays, IsSameHotelUser

### POST
**Serializer: `CheckoutSerializer`**
```json
{
  internal_rating: integer // Internal rating from 1 to 5 (optional)
  internal_note: string // Internal notes about the guest stay (optional)
  flag_user: boolean // Flag this guest for future reference
}
```

---

## Endpoint: `/api/^stay-management/(?P<pk>[^/.]+)/extend-stay/$`
**View**: `StayManagementViewSet`
**Permissions**: Authenticated Users, CanViewAndManageStays, IsSameHotelUser

### POST
**Serializer: `ExtendStaySerializer`**
```json
{
  check_out_date*: datetime (ISO 8601) // New checkout date and time for extending the stay
}
```

---

## Endpoint: `/api/^stay-management/(?P<pk>[^/.]+)/extend-stay\.(?P<format>[a-z0-9]+)/?$`
**View**: `StayManagementViewSet`
**Permissions**: Authenticated Users, CanViewAndManageStays, IsSameHotelUser

### POST
**Serializer: `ExtendStaySerializer`**
```json
{
  check_out_date*: datetime (ISO 8601) // New checkout date and time for extending the stay
}
```

---

## Endpoint: `/api/^stay-management/(?P<pk>[^/.]+)/verify-checkin/$`
**View**: `StayManagementViewSet`
**Permissions**: Authenticated Users, CanViewAndManageStays, IsSameHotelUser

### PATCH
**Serializer: `VerifyCheckinSerializer`**
```json
{
  register_number: string
  room_id: integer
  guest_updates: string
  check_out_date: datetime (ISO 8601)
  breakfast_reminder: boolean // Enable breakfast reminders for this stay
  dinner_reminder: boolean // Enable dinner reminders for this stay
  verified_document_ids: string // List of document IDs to mark as verified
  verify_all_documents: boolean // If True, marks all guest documents as verified
}
```

---

## Endpoint: `/api/^stay-management/(?P<pk>[^/.]+)/verify-checkin\.(?P<format>[a-z0-9]+)/?$`
**View**: `StayManagementViewSet`
**Permissions**: Authenticated Users, CanViewAndManageStays, IsSameHotelUser

### PATCH
**Serializer: `VerifyCheckinSerializer`**
```json
{
  register_number: string
  room_id: integer
  guest_updates: string
  check_out_date: datetime (ISO 8601)
  breakfast_reminder: boolean // Enable breakfast reminders for this stay
  dinner_reminder: boolean // Enable dinner reminders for this stay
  verified_document_ids: string // List of document IDs to mark as verified
  verify_all_documents: boolean // If True, marks all guest documents as verified
}
```

---

## Endpoint: `/api/hotel_stat/compare/`
**View**: `HotelComparisonView`
**Permissions**: Authenticated Users, Hotel Admin | Manager

### GET
**Manual Definition**
```json
{
  description: Compare hotels
  type: object
}
```

---

## Endpoint: `/api/^plans/$`
**View**: `SubscriptionPlanViewSet`
**Permissions**: Authenticated Users, CanManagePlatform

### GET, POST
**Serializer: `SubscriptionPlanSerializer`**
```json
{
  id: string
  name*: string
  plan_type: enum
  price: string
  duration_days*: integer // Duration of the plan in days
  description: string
  is_active: boolean
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^plans\.(?P<format>[a-z0-9]+)/?$`
**View**: `SubscriptionPlanViewSet`
**Permissions**: Authenticated Users, CanManagePlatform

### GET, POST
**Serializer: `SubscriptionPlanSerializer`**
```json
{
  id: string
  name*: string
  plan_type: enum
  price: string
  duration_days*: integer // Duration of the plan in days
  description: string
  is_active: boolean
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^plans/(?P<pk>[^/.]+)/$`
**View**: `SubscriptionPlanViewSet`
**Permissions**: Authenticated Users, CanManagePlatform

### DELETE, GET, PATCH, PUT
**Serializer: `SubscriptionPlanSerializer`**
```json
{
  id: string
  name*: string
  plan_type: enum
  price: string
  duration_days*: integer // Duration of the plan in days
  description: string
  is_active: boolean
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^plans/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$`
**View**: `SubscriptionPlanViewSet`
**Permissions**: Authenticated Users, CanManagePlatform

### DELETE, GET, PATCH, PUT
**Serializer: `SubscriptionPlanSerializer`**
```json
{
  id: string
  name*: string
  plan_type: enum
  price: string
  duration_days*: integer // Duration of the plan in days
  description: string
  is_active: boolean
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^notifications/$`
**View**: `NotificationViewSet`
**Permissions**: Authenticated Users

### GET
**Serializer: `NotificationSerializer`**
```json
{
  id: integer
  user: string
  group_type: enum
  group_type_display: string
  hotel: string // Required for hotel_staff group notifications
  title*: string
  message*: string
  link: string // URL to navigate to when notification is clicked
  link_label: string // Label text for the link button
  is_read: boolean
  created_at: datetime (ISO 8601)
}
```

### POST
**Serializer: `NotificationCreateSerializer`**
```json
{
  user: string
  group_type: enum
  title*: string
  message*: string
  link: string // URL to navigate to when notification is clicked
  link_label: string // Label text for the link button
}
```

---

## Endpoint: `/api/^notifications/group-notifications/$`
**View**: `NotificationViewSet`
**Permissions**: Authenticated Users

### GET
**Serializer: `NotificationSerializer`**
```json
{
  id: integer
  user: string
  group_type: enum
  group_type_display: string
  hotel: string // Required for hotel_staff group notifications
  title*: string
  message*: string
  link: string // URL to navigate to when notification is clicked
  link_label: string // Label text for the link button
  is_read: boolean
  created_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^notifications/mark-all-read/$`
**View**: `NotificationViewSet`
**Permissions**: Authenticated Users

### POST
**Serializer: `NotificationCreateSerializer`**
```json
{
  user: string
  group_type: enum
  title*: string
  message*: string
  link: string // URL to navigate to when notification is clicked
  link_label: string // Label text for the link button
}
```

---

## Endpoint: `/api/^notifications/my-notifications/$`
**View**: `NotificationViewSet`
**Permissions**: Authenticated Users

### GET
**Serializer: `NotificationSerializer`**
```json
{
  id: integer
  user: string
  group_type: enum
  group_type_display: string
  hotel: string // Required for hotel_staff group notifications
  title*: string
  message*: string
  link: string // URL to navigate to when notification is clicked
  link_label: string // Label text for the link button
  is_read: boolean
  created_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^notifications/(?P<pk>[^/.]+)/$`
**View**: `NotificationViewSet`
**Permissions**: Authenticated Users

### DELETE, GET, PATCH, PUT
**Serializer: `NotificationSerializer`**
```json
{
  id: integer
  user: string
  group_type: enum
  group_type_display: string
  hotel: string // Required for hotel_staff group notifications
  title*: string
  message*: string
  link: string // URL to navigate to when notification is clicked
  link_label: string // Label text for the link button
  is_read: boolean
  created_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/^notifications/(?P<pk>[^/.]+)/mark-read/$`
**View**: `NotificationViewSet`
**Permissions**: Authenticated Users

### POST
**Serializer: `NotificationCreateSerializer`**
```json
{
  user: string
  group_type: enum
  title*: string
  message*: string
  link: string // URL to navigate to when notification is clicked
  link_label: string // Label text for the link button
}
```

---

## Endpoint: `/api/chat/templates/`
**View**: `MessageTemplateListCreateView`
**Permissions**: Authenticated Users

### GET, PATCH, POST, PUT
**Serializer: `MessageTemplateSerializer`**
```json
{
  id: integer
  name*: string
  template_type*: enum
  text_content*: string
  media_file: file
  media_filename: string
  media_url: string
  is_customizable: boolean
  is_active: boolean
  variables: json/object // List of variable names that can be customized
  description: string
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/chat/templates/<int:pk>/`
**View**: `MessageTemplateDetailView`
**Permissions**: Authenticated Users

### GET, PATCH, POST, PUT
**Serializer: `MessageTemplateSerializer`**
```json
{
  id: integer
  name*: string
  template_type*: enum
  text_content*: string
  media_file: file
  media_filename: string
  media_url: string
  is_customizable: boolean
  is_active: boolean
  variables: json/object // List of variable names that can be customized
  description: string
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/chat/templates/types/`
**View**: `template_types_view`
**Permissions**: Authenticated Users

### GET
**Manual Definition**
```json
{
  type: array
  description: List of available template types
}
```

---

## Endpoint: `/api/chat/templates/<int:template_id>/preview/`
**View**: `render_template_preview`
**Permissions**: Authenticated Users

### GET
**Manual Definition**
```json
{
  description: Preview rendered template with variables
  type: object
}
```

---

## Endpoint: `/api/chat/templates/variables/`
**View**: `template_variables_view`
**Permissions**: Authenticated Users

### GET
**Manual Definition**
```json
{
  description: List of available template variables
  type: object
}
```

---

## Endpoint: `/api/chat/custom-templates/`
**View**: `CustomMessageTemplateListCreateView`
**Permissions**: Authenticated Users, Hotel Admin

### GET, PATCH, POST, PUT
**Serializer: `CustomMessageTemplateSerializer`**
```json
{
  id: integer
  hotel: string
  hotel_name: string
  base_template: string // Base template this customization is derived from
  base_template_name: string
  name*: string
  template_type*: enum
  text_content*: string
  media_file: file
  media_filename: string
  media_url: string
  is_customizable: boolean
  is_active: boolean
  variables: json/object // List of variable names that can be customized
  description: string
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/chat/custom-templates/<int:pk>/`
**View**: `CustomMessageTemplateDetailView`
**Permissions**: Authenticated Users, Hotel Admin

### GET, PATCH, POST, PUT
**Serializer: `CustomMessageTemplateSerializer`**
```json
{
  id: integer
  hotel: string
  hotel_name: string
  base_template: string // Base template this customization is derived from
  base_template_name: string
  name*: string
  template_type*: enum
  text_content*: string
  media_file: file
  media_filename: string
  media_url: string
  is_customizable: boolean
  is_active: boolean
  variables: json/object // List of variable names that can be customized
  description: string
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

---

## Endpoint: `/api/chat/custom-templates/<int:template_id>/preview/`
**View**: `render_template_preview`
**Permissions**: Authenticated Users

### GET
**Manual Definition**
```json
{
  description: Preview rendered template with variables
  type: object
}
```

---

