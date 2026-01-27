# General API Type Definitions

Auto-generated definitions for Public/Unknown routes.

## Endpoint: `/api/hotel/register/`
**View**: `HotelRegistrationView`
**Permissions**: Public

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

## Endpoint: `/api/verify-otp/`
**View**: `VerifyOTPView`
**Permissions**: Public

### POST
**Manual Definition**
```json
{
  email*: string
  otp*: string
}
```

---

## Endpoint: `/api/username-suggestions/`
**View**: `UsernameSuggestionView`
**Permissions**: Public

### GET
**Manual Definition**
```json
{
  hotel_name*: string // Query Parameter
}
```

---

## Endpoint: `/api/resend-otp/`
**View**: `ResendOTPView`
**Permissions**: Public

### POST
**Manual Definition**
```json
{
  email*: string
}
```

---

## Endpoint: `/api/login/`
**View**: `CustomTokenObtainPairView`
**Permissions**: Unknown / Default

### GET, PATCH, POST, PUT
**Serializer: `MyTokenObtainPairSerializer`**
```json
{
}
```

---

## Endpoint: `/api/login/refresh/`
**View**: `TokenRefreshView`
**Permissions**: Unknown / Default

### POST
**Manual Definition**
```json
{
  refresh*: string
}
```

---

## Endpoint: `/api/password-reset/request/`
**View**: `PasswordResetRequestView`
**Permissions**: Public

### POST
**Manual Definition**
```json
{
  email*: string
}
```

---

## Endpoint: `/api/password-reset/confirm/`
**View**: `PasswordResetConfirmView`
**Permissions**: Public

### POST
**Manual Definition**
```json
{
  email*: string
  otp*: string
  new_password*: string
}
```

---

## Endpoint: `/api/^hotels/$`
**View**: `HotelViewSet`
**Permissions**: IsVerifiedUser

### GET
**Serializer: `UserHotelSerializer`**
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
  is_verified: boolean
  is_active: boolean
  is_demo: boolean
  verification_notes: string // Notes for verification process by platform admin.
  registration_date: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

### POST
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

## Endpoint: `/api/^hotels\.(?P<format>[a-z0-9]+)/?$`
**View**: `HotelViewSet`
**Permissions**: IsVerifiedUser

### GET
**Serializer: `UserHotelSerializer`**
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
  is_verified: boolean
  is_active: boolean
  is_demo: boolean
  verification_notes: string // Notes for verification process by platform admin.
  registration_date: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

### POST
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

## Endpoint: `/api/^hotels/(?P<pk>[^/.]+)/$`
**View**: `HotelViewSet`
**Permissions**: IsVerifiedUser

### GET
**Serializer: `UserHotelSerializer`**
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
  is_verified: boolean
  is_active: boolean
  is_demo: boolean
  verification_notes: string // Notes for verification process by platform admin.
  registration_date: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

### PATCH, PUT
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

## Endpoint: `/api/^hotels/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$`
**View**: `HotelViewSet`
**Permissions**: IsVerifiedUser

### GET
**Serializer: `UserHotelSerializer`**
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
  is_verified: boolean
  is_active: boolean
  is_demo: boolean
  verification_notes: string // Notes for verification process by platform admin.
  registration_date: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
}
```

### PATCH, PUT
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

## Endpoint: `/api/^transactions/$`
**View**: `TransactionViewSet`
**Permissions**: Public

### GET, POST
**Serializer: `TransactionSerializer`**
```json
{
  id: string
  hotel_name: string
  plan_name: string
  amount*: string
  transaction_type: enum
  status: enum
  transaction_id: string // External payment gateway transaction ID
  notes: string
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel*: string
  plan*: string
}
```

---

## Endpoint: `/api/^transactions\.(?P<format>[a-z0-9]+)/?$`
**View**: `TransactionViewSet`
**Permissions**: Public

### GET, POST
**Serializer: `TransactionSerializer`**
```json
{
  id: string
  hotel_name: string
  plan_name: string
  amount*: string
  transaction_type: enum
  status: enum
  transaction_id: string // External payment gateway transaction ID
  notes: string
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel*: string
  plan*: string
}
```

---

## Endpoint: `/api/^transactions/(?P<pk>[^/.]+)/$`
**View**: `TransactionViewSet`
**Permissions**: Public

### DELETE, GET, PATCH, PUT
**Serializer: `TransactionSerializer`**
```json
{
  id: string
  hotel_name: string
  plan_name: string
  amount*: string
  transaction_type: enum
  status: enum
  transaction_id: string // External payment gateway transaction ID
  notes: string
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel*: string
  plan*: string
}
```

---

## Endpoint: `/api/^transactions/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$`
**View**: `TransactionViewSet`
**Permissions**: Public

### DELETE, GET, PATCH, PUT
**Serializer: `TransactionSerializer`**
```json
{
  id: string
  hotel_name: string
  plan_name: string
  amount*: string
  transaction_type: enum
  status: enum
  transaction_id: string // External payment gateway transaction ID
  notes: string
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel*: string
  plan*: string
}
```

---

## Endpoint: `/api/^subscriptions/$`
**View**: `HotelSubscriptionViewSet`
**Permissions**: Public

### GET, POST
**Serializer: `HotelSubscriptionSerializer`**
```json
{
  id: string
  hotel_name: string
  plan_name: string
  is_expired: boolean
  days_until_expiry: integer
  start_date*: datetime (ISO 8601)
  end_date*: datetime (ISO 8601)
  is_active: boolean
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel*: string
  plan*: string
}
```

---

## Endpoint: `/api/^subscriptions\.(?P<format>[a-z0-9]+)/?$`
**View**: `HotelSubscriptionViewSet`
**Permissions**: Public

### GET, POST
**Serializer: `HotelSubscriptionSerializer`**
```json
{
  id: string
  hotel_name: string
  plan_name: string
  is_expired: boolean
  days_until_expiry: integer
  start_date*: datetime (ISO 8601)
  end_date*: datetime (ISO 8601)
  is_active: boolean
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel*: string
  plan*: string
}
```

---

## Endpoint: `/api/^subscriptions/create_subscription/$`
**View**: `HotelSubscriptionViewSet`
**Permissions**: Public

### POST
**Serializer: `HotelSubscriptionSerializer`**
```json
{
  id: string
  hotel_name: string
  plan_name: string
  is_expired: boolean
  days_until_expiry: integer
  start_date*: datetime (ISO 8601)
  end_date*: datetime (ISO 8601)
  is_active: boolean
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel*: string
  plan*: string
}
```

---

## Endpoint: `/api/^subscriptions/create_subscription\.(?P<format>[a-z0-9]+)/?$`
**View**: `HotelSubscriptionViewSet`
**Permissions**: Public

### POST
**Serializer: `HotelSubscriptionSerializer`**
```json
{
  id: string
  hotel_name: string
  plan_name: string
  is_expired: boolean
  days_until_expiry: integer
  start_date*: datetime (ISO 8601)
  end_date*: datetime (ISO 8601)
  is_active: boolean
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel*: string
  plan*: string
}
```

---

## Endpoint: `/api/^subscriptions/extend_subscription/$`
**View**: `HotelSubscriptionViewSet`
**Permissions**: Public

### POST
**Serializer: `HotelSubscriptionSerializer`**
```json
{
  id: string
  hotel_name: string
  plan_name: string
  is_expired: boolean
  days_until_expiry: integer
  start_date*: datetime (ISO 8601)
  end_date*: datetime (ISO 8601)
  is_active: boolean
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel*: string
  plan*: string
}
```

---

## Endpoint: `/api/^subscriptions/extend_subscription\.(?P<format>[a-z0-9]+)/?$`
**View**: `HotelSubscriptionViewSet`
**Permissions**: Public

### POST
**Serializer: `HotelSubscriptionSerializer`**
```json
{
  id: string
  hotel_name: string
  plan_name: string
  is_expired: boolean
  days_until_expiry: integer
  start_date*: datetime (ISO 8601)
  end_date*: datetime (ISO 8601)
  is_active: boolean
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel*: string
  plan*: string
}
```

---

## Endpoint: `/api/^subscriptions/my_subscription/$`
**View**: `HotelSubscriptionViewSet`
**Permissions**: Public

### GET
**Serializer: `HotelSubscriptionSerializer`**
```json
{
  id: string
  hotel_name: string
  plan_name: string
  is_expired: boolean
  days_until_expiry: integer
  start_date*: datetime (ISO 8601)
  end_date*: datetime (ISO 8601)
  is_active: boolean
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel*: string
  plan*: string
}
```

---

## Endpoint: `/api/^subscriptions/my_subscription\.(?P<format>[a-z0-9]+)/?$`
**View**: `HotelSubscriptionViewSet`
**Permissions**: Public

### GET
**Serializer: `HotelSubscriptionSerializer`**
```json
{
  id: string
  hotel_name: string
  plan_name: string
  is_expired: boolean
  days_until_expiry: integer
  start_date*: datetime (ISO 8601)
  end_date*: datetime (ISO 8601)
  is_active: boolean
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel*: string
  plan*: string
}
```

---

## Endpoint: `/api/^subscriptions/process_payment/$`
**View**: `HotelSubscriptionViewSet`
**Permissions**: Public

### POST
**Serializer: `HotelSubscriptionSerializer`**
```json
{
  id: string
  hotel_name: string
  plan_name: string
  is_expired: boolean
  days_until_expiry: integer
  start_date*: datetime (ISO 8601)
  end_date*: datetime (ISO 8601)
  is_active: boolean
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel*: string
  plan*: string
}
```

---

## Endpoint: `/api/^subscriptions/process_payment\.(?P<format>[a-z0-9]+)/?$`
**View**: `HotelSubscriptionViewSet`
**Permissions**: Public

### POST
**Serializer: `HotelSubscriptionSerializer`**
```json
{
  id: string
  hotel_name: string
  plan_name: string
  is_expired: boolean
  days_until_expiry: integer
  start_date*: datetime (ISO 8601)
  end_date*: datetime (ISO 8601)
  is_active: boolean
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel*: string
  plan*: string
}
```

---

## Endpoint: `/api/^subscriptions/subscribe_to_plan/$`
**View**: `HotelSubscriptionViewSet`
**Permissions**: Public

### POST
**Serializer: `HotelSubscriptionSerializer`**
```json
{
  id: string
  hotel_name: string
  plan_name: string
  is_expired: boolean
  days_until_expiry: integer
  start_date*: datetime (ISO 8601)
  end_date*: datetime (ISO 8601)
  is_active: boolean
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel*: string
  plan*: string
}
```

---

## Endpoint: `/api/^subscriptions/subscribe_to_plan\.(?P<format>[a-z0-9]+)/?$`
**View**: `HotelSubscriptionViewSet`
**Permissions**: Public

### POST
**Serializer: `HotelSubscriptionSerializer`**
```json
{
  id: string
  hotel_name: string
  plan_name: string
  is_expired: boolean
  days_until_expiry: integer
  start_date*: datetime (ISO 8601)
  end_date*: datetime (ISO 8601)
  is_active: boolean
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel*: string
  plan*: string
}
```

---

## Endpoint: `/api/^subscriptions/(?P<pk>[^/.]+)/$`
**View**: `HotelSubscriptionViewSet`
**Permissions**: Public

### DELETE, GET, PATCH, PUT
**Serializer: `HotelSubscriptionSerializer`**
```json
{
  id: string
  hotel_name: string
  plan_name: string
  is_expired: boolean
  days_until_expiry: integer
  start_date*: datetime (ISO 8601)
  end_date*: datetime (ISO 8601)
  is_active: boolean
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel*: string
  plan*: string
}
```

---

## Endpoint: `/api/^subscriptions/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$`
**View**: `HotelSubscriptionViewSet`
**Permissions**: Public

### DELETE, GET, PATCH, PUT
**Serializer: `HotelSubscriptionSerializer`**
```json
{
  id: string
  hotel_name: string
  plan_name: string
  is_expired: boolean
  days_until_expiry: integer
  start_date*: datetime (ISO 8601)
  end_date*: datetime (ISO 8601)
  is_active: boolean
  created_at: datetime (ISO 8601)
  updated_at: datetime (ISO 8601)
  hotel*: string
  plan*: string
}
```

---

## Endpoint: `/api/chat/messages/typing/`
**View**: `send_typing_indicator`
**Permissions**: Unknown / Manual

### POST
**Manual Definition**
```json
{
  conversation_id*: integer
}
```

---

