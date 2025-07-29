from rest_framework import viewsets, permissions, views
from rest_framework.response import Response
from .models import Hotel
from .serializers import HotelSerializer, UserHotelSerializer
from .permissions import IsHotelAdmin

class IsVerifiedUser(permissions.BasePermission):
    """
    Allows access only to verified users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_verified

class HotelViewSet(viewsets.ModelViewSet):
    queryset = Hotel.objects.all()
    permission_classes = [IsVerifiedUser]

    def get_serializer_class(self):
        if self.request.user.is_staff or self.request.user.is_superuser:
            return HotelSerializer
        return UserHotelSerializer

    def get_queryset(self):
        if self.request.user.is_staff or self.request.user.is_superuser:
            return Hotel.objects.all()
        return Hotel.objects.filter(invited_by=self.request.user)

    def perform_create(self, serializer):
        serializer.save(invited_by=self.request.user)

class HotelOnboardingView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsHotelAdmin]
    
    def post(self, request):
        # Only verified hotel_admin can complete onboarding
        if not request.user.is_verified:
            return Response({'error': 'Email not verified'}, status=status.HTTP_403_FORBIDDEN)

        if request.user.hotel:
            return Response({'error': 'Hotel profile already exists.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = HotelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        hotel = serializer.save()

        # Associate user with hotel
        request.user.hotel = hotel
        request.user.save()
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
