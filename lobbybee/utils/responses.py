"""
Standardized API Response Helpers

Usage:
    from lobbybee.utils.responses import success_response, error_response, created_response
    
    # Success with data
    return success_response(data=serializer.data)
    
    # Success with message
    return success_response(message="Hotel verified")
    
    # Created
    return created_response(data=serializer.data, message="User created successfully")
    
    # Error
    return error_response("Invalid input")
    
    # Error with field-level details
    return error_response("Validation failed", errors={"email": ["Already exists"]})
"""

from rest_framework.response import Response
from rest_framework import status as http_status


def success_response(data=None, message=None, status=http_status.HTTP_200_OK):
    """
    Return standardized success response.
    
    Format: {"success": true, "message"?: string, "data"?: any}
    """
    response_data = {"success": True}
    if message:
        response_data["message"] = message
    if data is not None:
        response_data["data"] = data
    return Response(response_data, status=status)


def error_response(message, errors=None, status=http_status.HTTP_400_BAD_REQUEST):
    """
    Return standardized error response.
    
    Format: {"success": false, "message": string, "errors"?: object}
    """
    response_data = {
        "success": False,
        "message": message
    }
    if errors:
        response_data["errors"] = errors
    return Response(response_data, status=status)


def created_response(data=None, message="Created successfully"):
    """
    Return standardized 201 response.
    
    Shorthand for success_response with HTTP_201_CREATED status.
    """
    return success_response(data=data, message=message, status=http_status.HTTP_201_CREATED)


def not_found_response(message="Not found"):
    """
    Return standardized 404 response.
    """
    return error_response(message=message, status=http_status.HTTP_404_NOT_FOUND)


def forbidden_response(message="You do not have permission to perform this action"):
    """
    Return standardized 403 response.
    """
    return error_response(message=message, status=http_status.HTTP_403_FORBIDDEN)


def server_error_response(message="An unexpected error occurred"):
    """
    Return standardized 500 response.
    """
    return error_response(message=message, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)


def paginated_response(data, message="Fetched successfully", status=http_status.HTTP_200_OK):
    """
    Return standardized paginated response.
    
    Expected data format from DRF pagination:
    {
        "count": 100,
        "next": "url",
        "previous": "url",
        "results": [...]
    }
    
    Output format:
    {
        "success": True,
        "message": "Fetched successfully",
        "data": {
            "count": 100,
            "next": "url",
            "previous": "url",
            "results": [...]
        }
    }
    """
    return success_response(data=data, message=message, status=status)
