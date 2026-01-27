from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from lobbybee.utils.responses import success_response, error_response, created_response, not_found_response, forbidden_response
from django.shortcuts import get_object_or_404
from django.db.models import Q
from .models import GuestFlag
from guest.models import Guest
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
        
        return created_response(data=response_serializer.data)
    
    def retrieve(self, request, *args, **kwargs):
        """Get flag details"""
        flag = self.get_object()
        serializer = self.get_serializer(flag)
        return success_response(data=serializer.data)
    
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
        return success_response(data=serializer.data)
    
    @action(detail=True, methods=['post'], url_path='reset')
    @action(detail=True, methods=['post'], url_path='reset')
    def reset(self, request, pk=None):
        """Reset (deactivate) a flag"""
        try:
            try:
                flag = self.get_object()
            except Exception:
                return not_found_response("Flag not found")
            
            if not flag.is_active:
                return error_response(
                    'Flag is already reset',
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
                return not_found_response('Flag not found or already reset')
            
            response_serializer = GuestFlagResponseSerializer(
                reset_flag,
                context={'request': request}
            )
            
            return success_response(data=response_serializer.data)
        except Exception as e:
            return error_response(f"Failed to reset flag: {str(e)}", status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='check/(?P<guest_id>\d+)')
    @action(detail=False, methods=['get'], url_path='check/(?P<guest_id>\d+)')
    def check_guest(self, request, guest_id=None):
        """
        Check if a guest has any active flags.
        Used during check-in process.
        """
        if not guest_id:
            return error_response(
                'guest_id is required',
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            flag_summary = get_flag_summary_for_guest(guest_id)
            
            # For hotel staff checking, don't include internal_reason
            if request.user.user_type in ['hotel_admin', 'manager', 'receptionist']:
                # Remove internal_reason from flags for hotel staff
                for flag_data in flag_summary['flags']:
                    flag_data.pop('internal_reason', None)
            
            serializer = GuestFlagSummarySerializer(flag_summary)
            return success_response(data=serializer.data)
        except Exception as e:
            return error_response(f"Failed to check guest flags: {str(e)}", status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_guests(request):
    """
    Search guests by name, ID, or phone number with fuzzy matching.
    Available for platform admins and hotel staff.
    """
    try:
        query = request.query_params.get('q', '').strip()

        if not query:
            return error_response(
                'Search query parameter "q" is required',
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if user has permission (platform admin/staff or hotel staff)
        if not (request.user.user_type in ['platform_admin', 'platform_staff'] or
                (request.user.user_type in ['hotel_admin', 'manager', 'receptionist'] and request.user.hotel)):
            return forbidden_response('Permission denied')

        # Limit results to prevent overwhelming responses
        limit = min(int(request.query_params.get('limit', 20)), 50)

        # Build fuzzy search query
        guests = Guest.objects.filter(
            Q(full_name__icontains=query) |
            Q(whatsapp_number__icontains=query) |
            Q(email__icontains=query) |
            Q(register_number__icontains=query)
        ).distinct()[:limit]

        # Prepare response data
        results = []
        for guest in guests:
            # Get guest's recent stays (last 5)
            recent_stays = guest.stays.all().order_by('-created_at')[:5]
            stays_info = []

            for stay in recent_stays:
                stays_info.append({
                    'id': stay.id,
                    'hotel_name': stay.hotel.name,
                    'check_in_date': stay.check_in_date,
                    'check_out_date': stay.check_out_date,
                    'status': stay.status,
                    'internal_rating': stay.internal_rating
                })

            # Check if guest has any active flags
            active_flags_count = guest.flags.filter(is_active=True).count()

            results.append({
                'id': guest.id,
                'full_name': guest.full_name,
                'whatsapp_number': guest.whatsapp_number,
                'email': guest.email,
                'register_number': guest.register_number,
                'date_of_birth': guest.date_of_birth,
                'nationality': guest.nationality,
                'status': guest.status,
                'loyalty_points': guest.loyalty_points,
                'first_contact_date': guest.first_contact_date,
                'last_activity': guest.last_activity,
                'recent_stays': stays_info,
                'active_flags_count': active_flags_count
            })

        return success_response(data={
            'query': query,
            'count': len(results),
            'results': results
        })
    except Exception as e:
        return error_response(f"Failed to search guests: {str(e)}", status=status.HTTP_500_INTERNAL_SERVER_ERROR)