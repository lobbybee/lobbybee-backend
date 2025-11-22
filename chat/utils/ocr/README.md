# Simplified OCR Service

This directory contains a simplified OCR (Optical Character Recognition) service that extracts text from images without any model dependencies. The service is designed to be completely independent and reusable across different parts of the application.

## Key Features

- **Simple and Independent**: No model dependencies - just takes image input and returns text output
- **Flexible Input**: Supports both local file paths and S3 storage paths
- **Document Type Detection**: Automatically detects Indian ID document types (Aadhaar, Driving License, Voter ID, PAN, Passport)
- **Structured Data Extraction**: Parses specific fields from ID documents
- **Asynchronous Processing**: Includes Celery tasks for background processing

## Components

### 1. OCR Service (`ocr_service.py`)

The `TextractOCRService` class provides text extraction functionality using AWS Textract.

#### Key Functions

- `extract_text(image_path)`: Simple function to extract text from an image
- `detect_document_text(image_path)`: Extract text with additional metadata like confidence scores

### 2. ID Parser (`id_parser.py`)

The `IndianIDParser` class parses text extracted from Indian ID documents to extract structured information.

#### Key Functions

- `detect_document_type(text)`: Detects the type of ID document from text
- `parse(text)`: Auto-detects document type and parses structured data
- `get_document_type(text)`: Simple function to just get document type

#### Supported Document Types

- Aadhaar Card
- Driving License
- Voter ID (EPIC)
- PAN Card
- Passport

### 3. Async Tasks (`tasks/simple_ocr_tasks.py`)

Celery tasks for asynchronous processing:

- `extract_text_from_image_task`: Extract text from an image asynchronously
- `parse_id_document_task`: Parse ID document from text asynchronously
- `process_id_document_image_task`: Complete processing (extract + parse) asynchronously

## Usage Examples

### Basic Text Extraction

```python
from chat.utils.ocr.ocr_service import extract_text

# Extract text from an image
try:
    text = extract_text("/path/to/image.jpg")
    print(f"Extracted text: {text}")
except ValueError as e:
    print(f"Error: {e}")
```

### ID Document Parsing

```python
from chat.utils.ocr.ocr_service import extract_text
from chat.utils.ocr.id_parser import IndianIDParser

# Extract text
text = extract_text("/path/to/id/document.jpg")

# Parse ID document
parsed_data = IndianIDParser.parse(text)
print(f"Document type: {parsed_data.get('document_type')}")
print(f"Name: {parsed_data.get('name')}")
```

### Using Async Tasks

```python
from chat.utils.ocr.tasks.simple_ocr_tasks import process_id_document_image_task

# Process an ID document asynchronously
task = process_id_document_image_task.delay("/path/to/id/document.jpg")
result = task.get()  # In production, you wouldn't use .get()

if result.get('success'):
    print(f"Document type: {result.get('document_type')}")
    print(f"Parsed data: {result.get('parsed_data')}")
```

## Key Changes from Previous Implementation

1. **Removed Model Dependencies**: The OCR service no longer depends on Django models (Guest, GuestIdentityDocument, etc.)

2. **Simplified Interface**: Instead of complex processing pipelines, now provides simple functions:
   - `image_in → text_out`
   - `text_in → structured_data_out`

3. **Independent Functions**: All functions are completely independent and don't require database models

4. **Clear Separation of Concerns**:
   - `ocr_service.py`: Only handles text extraction from images
   - `id_parser.py`: Only handles parsing of extracted text

## Migration from Previous Implementation

If you were using the previous implementation:

```python
# OLD WAY (with model dependencies)
from chat.utils.ocr.ocr_service import process_id_document_with_ocr
result = process_id_document_with_ocr(front_image_path, back_image_path)
guest_data = result.get('guest_data', {})
```

Replace with:

```python
# NEW WAY (without model dependencies)
from chat.utils.ocr.ocr_service import extract_text
from chat.utils.ocr.id_parser import IndianIDParser

# Extract text from image
text = extract_text(front_image_path)

# Parse ID data (optional, if you need structured data)
parsed_data = IndianIDParser.parse(text)

# Use the extracted data as needed
guest_name = parsed_data.get('name', '')
document_type = parsed_data.get('document_type', '')

# Then use these values to update your models as needed
# guest = Guest.objects.create(name=guest_name, ...)
```

## Configuration

The OCR service requires AWS credentials to be configured in your Django settings:

```python
# settings.py
AWS_ACCESS_KEY_ID = "your_access_key"
AWS_SECRET_ACCESS_KEY = "your_secret_key"
AWS_S3_REGION_NAME = "your_region"  # e.g., "us-east-1"
AWS_STORAGE_BUCKET_NAME = "your_bucket_name"
```

## Error Handling

The OCR service provides clear error messages:

- Failed to initialize Textract client
- Failed to preprocess image
- Failed to download image from storage
- AWS Textract errors
- Text extraction failures

All errors include descriptive messages to help with debugging.