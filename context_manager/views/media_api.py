from rest_framework import generics, permissions
from ..models import WhatsappMedia
from ..serializers import WhatsappMediaSerializer
from hotel.permissions import IsHotelAdmin

class WhatsappMediaUploadView(generics.CreateAPIView):
    """
    An endpoint for hotel admins to upload media files directly.
    This stores the file in S3 and creates a WhatsappMedia record for it.
    """
    queryset = WhatsappMedia.objects.all()
    serializer_class = WhatsappMediaSerializer
    permission_classes = [permissions.IsAuthenticated, IsHotelAdmin]
