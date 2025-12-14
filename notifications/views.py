from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notifications.
    Provides CRUD operations and filters notifications by the current user.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_read', 'notification_type']

    def get_queryset(self):
        """
        Filter notifications to only show those for the current user.
        """
        user = self.request.user
        return Notification.objects.filter(user=user).order_by('-created_at')

    def perform_create(self, serializer):
        """
        Set the user to the current authenticated user when creating a notification.
        """
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        """
        Custom action to mark a notification as read.
        """
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        
        serializer = self.get_serializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        """
        Custom action to mark all notifications for the current user as read.
        """
        notifications = self.get_queryset().filter(is_read=False)
        notifications.update(is_read=True)
        
        return Response(
            {'message': 'All notifications marked as read'},
            status=status.HTTP_200_OK
        )