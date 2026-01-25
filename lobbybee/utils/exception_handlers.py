"""
Custom Exception Handler for Standardized API Responses

Automatically converts DRF exceptions (including serializer validation errors)
to the standardized format:
{
    "success": false,
    "message": "Error description",
    "errors": { ... }  // Optional, for field-level validation errors
}
"""

from rest_framework.views import exception_handler
from rest_framework.exceptions import ValidationError, AuthenticationFailed, NotAuthenticated, PermissionDenied


def custom_exception_handler(exc, context):
    """
    Custom exception handler that formats all errors consistently.
    """
    # Call DRF's default exception handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        custom_response_data = {
            "success": False,
            "message": _get_error_message(exc, response),
        }
        
        # Add field-level errors for ValidationError
        if isinstance(exc, ValidationError) and isinstance(response.data, dict):
            # Check if it's field-level errors (not just a "detail" key)
            if 'detail' not in response.data or len(response.data) > 1:
                custom_response_data["errors"] = _normalize_errors(response.data)
        
        response.data = custom_response_data
    
    return response


def _get_error_message(exc, response):
    """
    Extract a human-readable error message from the exception.
    """
    # Handle common exception types
    if isinstance(exc, NotAuthenticated):
        return "Authentication credentials were not provided."
    
    if isinstance(exc, AuthenticationFailed):
        return "Invalid authentication credentials."
    
    if isinstance(exc, PermissionDenied):
        if hasattr(exc, 'detail') and exc.detail:
            return str(exc.detail)
        return "You do not have permission to perform this action."
    
    if isinstance(exc, ValidationError):
        return _extract_first_validation_error(exc.detail)
    
    # Generic detail extraction
    if hasattr(exc, 'detail'):
        if isinstance(exc.detail, str):
            return exc.detail
        elif isinstance(exc.detail, list):
            return str(exc.detail[0]) if exc.detail else "An error occurred"
        elif isinstance(exc.detail, dict):
            if 'detail' in exc.detail:
                return str(exc.detail['detail'])
            return _extract_first_validation_error(exc.detail)
    
    return "An error occurred"


def _extract_first_validation_error(errors):
    """
    Extract the first validation error message from a nested structure.
    Used to provide a human-readable summary message.
    """
    if isinstance(errors, str):
        return errors
    
    if isinstance(errors, list):
        for item in errors:
            if isinstance(item, str):
                return item
            result = _extract_first_validation_error(item)
            if result:
                return result
    
    if isinstance(errors, dict):
        for key, value in errors.items():
            if key == 'non_field_errors':
                if isinstance(value, list) and value:
                    return str(value[0])
            elif isinstance(value, list) and value:
                return f"{key}: {value[0]}"
            elif isinstance(value, str):
                return f"{key}: {value}"
            elif isinstance(value, dict):
                result = _extract_first_validation_error(value)
                if result:
                    return result
    
    return "Validation error"


def _normalize_errors(errors):
    """
    Normalize error structure to ensure consistent format.
    Converts all error values to lists of strings.
    """
    if not isinstance(errors, dict):
        return errors
    
    normalized = {}
    for key, value in errors.items():
        if isinstance(value, list):
            normalized[key] = [str(v) for v in value]
        elif isinstance(value, str):
            normalized[key] = [value]
        elif isinstance(value, dict):
            normalized[key] = _normalize_errors(value)
        else:
            normalized[key] = [str(value)]
    
    return normalized
