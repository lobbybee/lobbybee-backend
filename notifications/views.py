from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Notification
from .serializers import NotificationSerializer, NotificationCreateSerializer
from .utils import get_user_notifications


class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notifications.
    Provides CRUD operations and filters notifications by the current user.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_read']  # Only allow filtering by read status

    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'create':
            return NotificationCreateSerializer
        return NotificationSerializer

    def get_queryset(self):
        """
        Get notifications for the current user, including group notifications
        Hotel staff automatically get hotel notifications from their hotel
        Platform users automatically get platform notifications
        """
        user = self.request.user
        return get_user_notifications(user, include_group_notifications=True)

    def perform_create(self, serializer):
        """
        Handle creating notifications with automatic hotel assignment and permission checks
        """
        user = self.request.user
        data = serializer.validated_data
        
        # Check permissions for group notifications
        if data.get('group_type') == 'hotel_staff':
            # Only hotel admin and manager can create hotel staff notifications
            if user.user_type not in ['hotel_admin', 'manager']:
                raise serializers.ValidationError("Only hotel admin and manager can create hotel staff notifications")
            
            if not user.hotel:
                raise serializers.ValidationError("Hotel staff must have a hotel assigned to create group notifications")
            
            serializer.save(hotel=user.hotel)
            
        elif data.get('group_type') == 'platform_user':
            # Only platform admin and staff can create platform notifications
            if user.user_type not in ['platform_admin', 'platform_staff']:
                raise serializers.ValidationError("Only platform admin and staff can create platform user notifications")
            
            serializer.save()
            
        else:
            # Personal notification - ensure user can only create for themselves unless admin
            if data.get('user') and data['user'] != user and user.user_type not in ['platform_admin', 'platform_staff', 'hotel_admin', 'manager']:
                raise serializers.ValidationError("You can only create notifications for yourself")
            
            serializer.save()

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        """
        Custom action to mark a notification as read.
        For group notifications, marks as read for all users.
        """
        notification = self.get_object()

        # Mark both individual and group notifications as read
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=['is_read'])

        serializer = self.get_serializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        """
        Custom action to mark all notifications for the current user as read.
        Marks both individual and group notifications as read.
        """
        # Get all unread notifications for the user (including group notifications)
        notifications = self.get_queryset().filter(is_read=False)
        notifications.update(is_read=True)

        return Response(
            {'message': 'All notifications marked as read'},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'], url_path='my-notifications')
    def my_notifications(self, request):
        """
        Get only notifications directly sent to the user (excluding group notifications)
        """
        user = request.user
        notifications = Notification.objects.filter(user=user).order_by('-created_at')
        
        page = self.paginate_queryset(notifications)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='group-notifications')
    def group_notifications(self, request):
        """
        Get only group notifications for the user
        Compatible with both PostgreSQL and SQLite
        """
        from django.db import connection
        user = request.user
        
        # Build conditions for group notifications
        conditions = []
        
        # Get hotel staff notifications
        if user.user_type in ['hotel_admin', 'manager', 'receptionist'] and user.hotel:
            conditions.append(
                Notification.objects.filter(
                    group_type='hotel_staff',
                    hotel=user.hotel
                )
            )
        
        # Get platform user notifications
        if user.user_type in ['platform_admin', 'platform_staff']:
            conditions.append(
                Notification.objects.filter(
                    group_type='platform_user'
                )
            )
        
        if not conditions:
            notifications = Notification.objects.none()
        elif connection.vendor == 'postgresql':
            # PostgreSQL supports UNION with ORDER BY
            notifications = conditions[0]
            for condition in conditions[1:]:
                notifications = notifications.union(condition)
            notifications = notifications.order_by('-created_at')
        else:
            # For SQLite and others, use the ID collection approach
            notification_ids = []
            for condition in conditions:
                notification_ids.extend(condition.values_list('id', flat=True))
            
            # Remove duplicates and fetch
            unique_ids = list(set(notification_ids))
            if unique_ids:
                notifications = Notification.objects.filter(id__in=unique_ids).order_by('-created_at')
            else:
                notifications = Notification.objects.none()
        
        page = self.paginate_queryset(notifications)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)