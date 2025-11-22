"""
Example usage of the simplified OCR service.

This example demonstrates how to use the OCR functions without any model dependencies.
The OCR service is now completely independent and just extracts text from images.
"""

from chat.utils.ocr.ocr_service import extract_text
from chat.utils.ocr.id_parser import IndianIDParser, get_document_type
from chat.utils.ocr.tasks.simple_ocr_tasks import (
    extract_text_from_image_task,
    parse_id_document_task,
    process_id_document_image_task
)


def simple_text_extraction_example():
    """Example of simple text extraction from an image."""
    image_path = "/path/to/your/id/document.jpg"
    
    try:
        # Extract text directly (synchronous)
        text = extract_text(image_path)
        print(f"Extracted text:\n{text}")
        return text
    except Exception as e:
        print(f"Error extracting text: {e}")
        return None


def id_document_parsing_example():
    """Example of ID document parsing from extracted text."""
    # First, extract text from an image
    image_path = "/path/to/your/id/document.jpg"
    text = extract_text(image_path)
    
    if not text:
        return None
    
    # Detect document type
    doc_type = get_document_type(text)
    print(f"Detected document type: {doc_type}")
    
    # Parse the document
    parsed_data = IndianIDParser.parse(text)
    print(f"Parsed data:\n{parsed_data}")
    return parsed_data


def asynchronous_processing_example():
    """Example of using the asynchronous tasks for OCR processing."""
    image_path = "/path/to/your/id/document.jpg"
    
    # Use Celery tasks for asynchronous processing
    # This would work in a production environment with Celery running
    
    # Option 1: Just extract text
    text_task = extract_text_from_image_task.delay(image_path)
    text_result = text_task.get()  # In production, you wouldn't use .get()
    
    if text_result.get('success'):
        print(f"Extracted text: {text_result.get('text')}")
        print(f"Word count: {text_result.get('word_count')}")
    else:
        print(f"Error: {text_result.get('error')}")
    
    # Option 2: Process complete ID document (extract + parse)
    id_task = process_id_document_image_task.delay(image_path)
    id_result = id_task.get()
    
    if id_result.get('success'):
        print(f"Document type: {id_result.get('document_type')}")
        print(f"Parsed data: {id_result.get('parsed_data')}")
        print(f"Fields extracted: {id_result.get('fields_count')}")
    else:
        print(f"Error: {id_result.get('error')}")


def integration_example_with_existing_code():
    """
    Example of how to integrate the simplified OCR service with existing code.
    
    This shows how you can replace the old OCR service calls with the new simplified ones.
    """
    
    # OLD WAY (with model dependencies):
    # from chat.utils.ocr.ocr_service import process_id_document_with_ocr
    # result = process_id_document_with_ocr(front_image_path, back_image_path)
    # guest_data = result.get('guest_data', {})
    
    # NEW WAY (without model dependencies):
    image_path = "/path/to/your/id/document.jpg"
    
    # Step 1: Extract text
    text = extract_text(image_path)
    
    # Step 2: Parse ID data (optional, if you need structured data)
    parsed_data = IndianIDParser.parse(text)
    
    # Step 3: Use the extracted text/parsed data as needed
    # For example, to create or update a guest record:
    guest_name = parsed_data.get('name', '')
    guest_dob = parsed_data.get('dob', '')
    document_type = parsed_data.get('document_type', '')
    
    # Then use these values to update your models as needed
    # guest = Guest.objects.create(name=guest_name, ...)
    
    return {
        'text': text,
        'parsed_data': parsed_data,
        'guest_name': guest_name,
        'document_type': document_type
    }


if __name__ == "__main__":
    # Run examples
    print("=== Simple Text Extraction ===")
    simple_text_extraction_example()
    
    print("\n=== ID Document Parsing ===")
    id_document_parsing_example()
    
    print("\n=== Asynchronous Processing ===")
    # Note: This would require Celery workers to be running
    # asynchronous_processing_example()
    
    print("\n=== Integration Example ===")
    integration_example_with_existing_code()