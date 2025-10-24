# Phone Number Utilities

This module provides comprehensive phone number normalization and validation utilities for the LobbyBee Hotel CRM system.

## Features

- **Automatic normalization** to E.164 format (+1234567890)
- **Support for multiple formats** with/without +, spaces, dashes, parentheses
- **Country code handling** for US and India numbers
- **Custom Django model field** for automatic normalization
- **Validation and comparison utilities**
- **Display formatting** options
- **Migration utilities** for existing data

## Core Functions

### `normalize_phone_number(phone_number: str) -> Optional[str]`

Normalizes a phone number to E.164 format.

```python
from chat.utils.phone_utils import normalize_phone_number

# Examples
normalize_phone_number("+1234567890")      # '1234567890'
normalize_phone_number("1234567890")       # '1234567890'
normalize_phone_number("123-456-7890")     # '1234567890'
normalize_phone_number("(123) 456-7890")   # '1234567890'
normalize_phone_number("+1 (123) 456-7890") # '11234567890'
normalize_phone_number("invalid")          # None
```

### `validate_phone_number(phone_number: str) -> bool`

Validates if a phone number is in a reasonable format.

```python
validate_phone_number("+1234567890")  # True
validate_phone_number("1234567890")   # True
validate_phone_number("123")          # False
validate_phone_number("")             # False
```

### `compare_phone_numbers(phone1: str, phone2: str) -> bool`

Compares two phone numbers after normalizing them.

```python
compare_phone_numbers("+1234567890", "123-456-7890")  # True
compare_phone_numbers("+1234567890", "+9876543210")   # False
```

## Django Model Field

### `NormalizedPhoneNumberField`

Custom Django field that automatically normalizes phone numbers before saving.

```python
from django.db import models
from chat.utils.phone_utils import NormalizedPhoneNumberField

class Guest(models.Model):
    whatsapp_number = NormalizedPhoneNumberField(max_length=20, unique=True)
    
class User(models.Model):
    phone = NormalizedPhoneNumberField(max_length=20, null=True, blank=True)
```

**Features:**
- Automatically normalizes on save
- Handles validation
- Works with migrations
- Returns `None` for invalid numbers

## Display Formatting

### `format_phone_number_for_display(phone_number: str, format_type: str) -> str`

Formats phone numbers for display purposes.

```python
# US numbers
format_phone_number_for_display("11234567890", "national")      # '(123) 456-7890'
format_phone_number_for_display("11234567890", "international") # '+1 123-456-7890'
format_phone_number_for_display("11234567890", "plain")         # '11234567890'

# India numbers
format_phone_number_for_display("911234567890", "national")     # '12345-67890'
format_phone_number_for_display("911234567890", "international") # '+91 12345-67890'
```

## API Integration

### Webhook Integration

Phone numbers are automatically normalized in webhook endpoints:

```python
# Incoming webhook data
{
    "whatsapp_number": "123-456-7890",  # Will be normalized to +1234567890
    "message": "Hello",
    "department": "Reception"
}
```

### API Endpoints

#### Get Conversation Type by Phone Number

```bash
GET /chat/guest/conversation-type/?phone_number=1234567890
```

**Response:**
```json
{
    "conversation_type": "service",
    "last_conversation_timing": "2024-01-15T10:30:00Z",
    "guest_name": "John Doe",
    "hotel_id": 1,
    "department": "Reception"
}
```

The endpoint automatically normalizes the phone number before lookup.

## Migration Guide

### 1. Update Models

Replace `CharField` with `NormalizedPhoneNumberField`:

```python
# Before
class Guest(models.Model):
    whatsapp_number = models.CharField(max_length=20, unique=True)

# After  
class Guest(models.Model):
    whatsapp_number = NormalizedPhoneNumberField(max_length=20, unique=True)
```

### 2. Create Migration

```bash
python manage.py makemigrations guest
```

### 3. Migrate Existing Data

Use the management command to normalize existing phone numbers:

```bash
# Dry run (see what would change)
python manage.py migrate_phone_numbers --dry-run

# Actual migration
python manage.py migrate_phone_numbers
```

**Custom migration options:**
```bash
# Specific app/model/field
python manage.py migrate_phone_numbers \
    --app-label=guest \
    --model-name=Guest \
    --field-name=whatsapp_number
```

### 4. Apply Migration

```bash
python manage.py migrate
```

## Usage Examples

### In Views

```python
from chat.utils.phone_utils import normalize_phone_number, compare_phone_numbers

class GuestLookupView(APIView):
    def get(self, request):
        phone = request.query_params.get('phone')
        normalized_phone = normalize_phone_number(phone)
        
        if not normalized_phone:
            return Response({'error': 'Invalid phone number'}, status=400)
            
        guest = Guest.objects.get(whatsapp_number=normalized_phone)
        return Response({'guest': guest.id})
```

### In Serializers

```python
from chat.utils.phone_utils import normalize_phone_number

class GuestSerializer(serializers.ModelSerializer):
    def validate_whatsapp_number(self, value):
        normalized = normalize_phone_number(value)
        if not normalized:
            raise serializers.ValidationError("Invalid phone number")
        return normalized
    
    class Meta:
        model = Guest
        fields = ['id', 'full_name', 'whatsapp_number']
```

### In Management Commands

```python
from chat.utils.phone_utils import migrate_existing_phone_numbers

# Custom migration logic
stats = migrate_existing_phone_numbers('guest', 'Guest', 'whatsapp_number')
print(f"Migrated {stats['normalized']} numbers")
```

## Supported Formats

### Input Formats
- `+1234567890` (with +)
- `1234567890` (10-digit)
- `123-456-7890` (with dashes)
- `(123) 456-7890` (with parentheses)
- `123.456.7890` (with dots)
- `123 456 7890` (with spaces)
- `+1 (123) 456-7890` (with country code and formatting)

### Output Format
All phone numbers are normalized to consistent format without +: `<country_code><number>`

## Country Support

### United States
- 10-digit numbers: `1234567890` → `11234567890`
- With country code: `+11234567890` → `11234567890`

### India
- 10-digit numbers: `1234567890` → `911234567890`
- With country code: `+911234567890` → `911234567890`

### International
- Numbers with country codes are preserved: `+441234567890` → `441234567890`
- Valid length: 10-15 digits including country code

## Error Handling

### Validation Errors
```python
# Invalid format
normalize_phone_number("invalid")  # Returns None

# Too short/long
normalize_phone_number("123")      # Returns None
normalize_phone_number("12345678901234567890")  # Returns None
```

### API Error Responses
```json
{
    "error": "Invalid phone number format"
}
```

```json
{
    "error": "Guest not found with the provided phone number"
}
```

## Best Practices

1. **Always normalize before storage** - Use `NormalizedPhoneNumberField` or call `normalize_phone_number()`
2. **Validate input early** - Use in serializers and form validation
3. **Use consistent format in APIs** - Always return normalized format
4. **Format for display only** - Use `format_phone_number_for_display()` for UI
5. **Handle None values** - Always check for None return values
6. **Test with various formats** - Include edge cases in tests

## Testing

```python
from chat.utils.phone_utils import normalize_phone_number, validate_phone_number

def test_phone_normalization():
    # Test no-plus normalization
    assert normalize_phone_number("+1234567890") == "1234567890"
    assert normalize_phone_number("123-456-7890") == "1234567890"
    assert normalize_phone_number("(123) 456-7890") == "1234567890"
    assert normalize_phone_number("+1 (123) 456-7890") == "11234567890"
    assert normalize_phone_number("invalid") is None
    
    assert validate_phone_number("+1234567890") is True
    assert validate_phone_number("123") is False

def test_websocket_group_names():
    from chat.utils.phone_utils import get_guest_group_name
    assert get_guest_group_name("+1234567890") == "guest_1234567890"
    assert get_guest_group_name("123-456-7890") == "guest_1234567890"
```

## Performance Considerations

- Normalization is O(n) where n is the length of the phone number
- Regular expressions are cached by Python
- Database queries benefit from normalized format indexing
- Consider adding database indexes on phone number fields

## Security Notes

- Phone numbers are sensitive data - handle according to privacy policies
- Normalization doesn't encrypt numbers - use encryption if required
- Input validation prevents injection attacks
- No external API calls - all processing is local