import uuid
def upload_to_hotel_documents(instance, filename):
    """Generate upload path for hotel documents"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"hotels/{instance.hotel.id}/documents/{filename}"


def upload_to_guest_documents(instance, filename):
    """Generate upload path for guest identity documents"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"guests/{instance.guest.id}/documents/{filename}"


def upload_to_customer_documents(instance, filename):
    """Generate upload path for customer documents"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"customers/{instance.customer.id}/documents/{filename}"
