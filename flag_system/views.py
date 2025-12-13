from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import GuestFlag
from .serializers import (
    GuestFlagSerializer,
    GuestFlagResponseSerializer,
    GuestFlagSummarySerializer,
    ResetFlagSerializer
)
from .permissions import (
    CanFlagGuests,
    CanViewGuestFlags,
    CanManageGuestFlags,
    CanResetGuestFlags
)
from .services import get_flag_summary_for_guest, reset_guest_flag


class GuestFlagViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing guest flags.
    """
    queryset = GuestFlag.objects.all()
    
    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [CanFlagGuests]
        elif self.action in ['list', 'retrieve']:
            permission_classes = [CanViewGuestFlags]
        elif self.action == 'reset':
            permission_classes = [CanResetGuestFlags]
        else:
            permission_classes = [CanViewGuestFlags]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        user = self.request.user
        
        # Platform staff can see all flags
        if user.user_type in ['platform_admin', 'platform_staff']:
            return GuestFlag.objects.all().select_related(
                'guest', 'last_modified_by', 'stay__hotel', 'reset_by'
            ).order_by('-created_at')
        
        # Hotel staff can see all flags (for check-in visibility)
        if user.user_type in ['hotel_admin', 'manager', 'receptionist'] and user.hotel:
            return GuestFlag.objects.all().select_related(
                'guest', 'last_modified_by', 'stay__hotel', 'reset_by'
            ).order_by('-created_at')
        
        return GuestFlag.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return GuestFlagSerializer
        elif self.action == 'reset':
            return ResetFlagSerializer
        return GuestFlagResponseSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a new guest flag"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flag = serializer.save()
        
        response_serializer = GuestFlagResponseSerializer(
            flag,
            context={'request': request}
        )
        
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    def retrieve(self, request, *args, **kwargs):
        """Get flag details"""
        flag = self.get_object()
        serializer = self.get_serializer(flag)
        return Response(serializer.data)
    
    def list(self, request, *args, **kwargs):
        """List flags with optional filtering"""
        queryset = self.get_queryset()
        
        # Filter by guest if provided
        guest_id = request.query_params.get('guest_id')
        if guest_id:
            queryset = queryset.filter(guest_id=guest_id)
        
        # Filter by hotel if provided (only for platform staff)
        hotel_id = request.query_params.get('hotel_id')
        if hotel_id and request.user.user_type in ['platform_admin', 'platform_staff']:
            queryset = queryset.filter(stay__hotel_id=hotel_id)
        
        # Filter active flags only
        active_only = request.query_params.get('active_only', 'false').lower() == 'true'
        if active_only:
            queryset = queryset.filter(is_active=True)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='reset')
    def reset(self, request, pk=None):
        """Reset (deactivate) a flag"""
        flag = self.get_object()
        
        if not flag.is_active:
            return Response(
                {'detail': 'Flag is already reset'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = ResetFlagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        reset_flag = reset_guest_flag(
            flag_id=flag.id,
            reset_reason=serializer.validated_data['reset_reason'],
            user=request.user
        )
        
        if not reset_flag:
            return Response(
                {'detail': 'Flag not found or already reset'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        response_serializer = GuestFlagResponseSerializer(
            reset_flag,
            context={'request': request}
        )
        
        return Response(response_serializer.data)
    
    @action(detail=False, methods=['get'], url_path='check/(?P<guest_id>\d+)')
    def check_guest(self, request, guest_id=None):
        """
        Check if a guest has any active flags.
        Used during check-in process.
        """
        if not guest_id:
            return Response(
                {'detail': 'guest_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        flag_summary = get_flag_summary_for_guest(guest_id)
        
        # For hotel staff checking, don't include internal_reason
        if request.user.user_type in ['hotel_admin', 'manager', 'receptionist']:
            # Remove internal_reason from flags for hotel staff
            for flag_data in flag_summary['flags']:
                flag_data.pop('internal_reason', None)
        
        serializer = GuestFlagSummarySerializer(flag_summary)
        return Response(serializer.data)