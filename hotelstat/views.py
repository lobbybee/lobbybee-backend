from rest_framework import viewsets, permissions, status, views, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from hotel.models import Hotel, Room, RoomCategory
from lobbybee.utils.responses import success_response, error_response, forbidden_response
from guest.models import Guest, Stay, Booking, Feedback
from chat.models import Conversation, Message
from user.models import User
from user.permissions import IsHotelManagerOrAdmin, IsHotelStaffOrAdmin
from django.db.models import Count, Q, Avg, Sum, F, ExpressionWrapper, DecimalField, DurationField, Max, Min
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import calendar


class HotelStatsViewSet(viewsets.ViewSet):
    """
    Comprehensive hotel statistics API with proper filtering by hotel and user type
    Access restricted to hotel receptionists, managers, hotel admins, and superusers only
    """
    permission_classes = [permissions.IsAuthenticated, IsHotelStaffOrAdmin]

    def list(self, request):
        try:
            """Get list of available hotels user can access stats for"""
            user = request.user
            accessible_hotels = self.get_accessible_hotels(user)
            
            hotels_data = []
            for hotel in accessible_hotels:
                hotels_data.append({
                    'id': str(hotel.id),
                    'name': hotel.name,
                    'city': hotel.city,
                    'status': hotel.status,
                })
            
            return success_response(data=hotels_data)
        except Exception as e:
            return error_response(
                f"Failed to list hotels stats: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def retrieve(self, request, pk=None):
        try:
            """Get statistics for a specific hotel"""
            user = request.user
            hotel_id = pk
            stat_type = request.query_params.get('stat_type', 'overview')
            
            # Parse date parameters
            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')
            date_str = request.query_params.get('date')
            
            try:
                if date_str:
                    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                else:
                    target_date = timezone.now().date()
                    
                if date_from:
                    date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                if date_to:
                    date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            except ValueError:
                return error_response(
                    "Invalid date format. Use YYYY-MM-DD.", 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Determine which hotel(s) the user can access
            accessible_hotels = self.get_accessible_hotels(user, hotel_id)
            
            if not accessible_hotels:
                return forbidden_response("Access denied or no hotel associated.")

            # Route to appropriate statistics method
            if stat_type == 'overview':
                return self.get_overview_stats(accessible_hotels, target_date, date_from, date_to)
            elif stat_type == 'occupancy':
                return self.get_occupancy_stats(accessible_hotels, target_date, date_from, date_to)
            elif stat_type == 'guests':
                return self.get_guest_stats(accessible_hotels, target_date, date_from, date_to)
            elif stat_type == 'rooms':
                return self.get_room_stats(accessible_hotels, target_date, date_from, date_to)
            elif stat_type == 'staff':
                return self.get_staff_stats(accessible_hotels, target_date, user)
            elif stat_type == 'performance':
                return self.get_performance_stats(accessible_hotels, target_date, date_from, date_to)
            else:
                return error_response(
                    f"Invalid stat type: {stat_type}", 
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return error_response(
                f"Failed to retrieve hotel stats: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get_accessible_hotels(self, user, hotel_id=None):
        """
        Determine which hotels a user can access based on their user type and permissions
        """
        # Superusers can access all hotels
        if user.is_superuser:
            if hotel_id:
                try:
                    return Hotel.objects.filter(id=hotel_id)
                except:
                    return Hotel.objects.none()
            return Hotel.objects.all()

        # Hotel users (admin/manager) can only access their associated hotel
        if user.user_type in ['hotel_admin', 'manager']:
            if user.hotel:
                if hotel_id and str(user.hotel.id) != hotel_id:
                    return Hotel.objects.none()
                return Hotel.objects.filter(id=user.hotel.id)

        return Hotel.objects.none()

    def get_overview_stats(self, hotels, target_date, date_from=None, date_to=None):
        """
        Overview statistics for dashboard
        """
        stats = {}
        
        for hotel in hotels:
            # Room statistics
            rooms = Room.objects.filter(hotel=hotel)
            room_stats = {
                'total': rooms.count(),
                'available': rooms.filter(status='available').count(),
                'occupied': rooms.filter(status='occupied').count(),
                'cleaning': rooms.filter(status='cleaning').count(),
                'maintenance': rooms.filter(status='maintenance').count(),
                'out_of_order': rooms.filter(status='out_of_order').count(),
            }
            
            # Calculate occupancy rate
            if room_stats['total'] > 0:
                occupancy_rate = (room_stats['occupied'] / room_stats['total']) * 100
            else:
                occupancy_rate = 0
            
            # Guest statistics
            active_stays = Stay.objects.filter(
                hotel=hotel, 
                status='active',
                check_in_date__lte=target_date,
                check_out_date__gte=target_date
            )
            
            # Booking statistics
            bookings_today = Booking.objects.filter(
                hotel=hotel,
                check_in_date=target_date
            )
            
            # Staff statistics (for hotel admins and managers)
            staff_stats = self._get_staff_count(hotel)
            
            hotel_stats = {
                'hotel_id': str(hotel.id),
                'hotel_name': hotel.name,
                'verification_status': hotel.status,
                'is_verified': hotel.is_verified,
                'rooms': room_stats,
                'occupancy_rate': round(occupancy_rate, 2),
                'active_stays': active_stays.count(),
                'expected_checkins': bookings_today.filter(status='confirmed').count(),
                'expected_checkouts': Stay.objects.filter(
                    hotel=hotel,
                    status='active',
                    check_out_date=target_date
                ).count(),
                'staff': staff_stats,
            }
            
            if date_from and date_to:
                # Add date range statistics
                hotel_stats.update(self._get_date_range_stats(hotel, date_from, date_to))
            
            stats[f"hotel_{hotel.id}"] = hotel_stats

        return success_response(data=stats)

    def get_occupancy_stats(self, hotels, target_date, date_from=None, date_to=None):
        """
        Detailed occupancy statistics
        """
        stats = {}
        
        for hotel in hotels:
            # Current occupancy by room category
            category_occupancy = []
            categories = RoomCategory.objects.filter(hotel=hotel)
            
            for category in categories:
                category_rooms = Room.objects.filter(hotel=hotel, category=category)
                occupied_rooms = category_rooms.filter(status='occupied')
                
                category_data = {
                    'category_name': category.name,
                    'total_rooms': category_rooms.count(),
                    'occupied_rooms': occupied_rooms.count(),
                    'available_rooms': category_rooms.filter(status='available').count(),
                    'occupancy_rate': round(
                        (occupied_rooms.count() / category_rooms.count() * 100) if category_rooms.count() > 0 else 0, 
                        2
                    ),
                    'base_rate': float(category.base_price),
                }
                category_occupancy.append(category_data)
            
            # Floor-wise occupancy
            floors = Room.objects.filter(hotel=hotel).values_list('floor', flat=True).distinct().order_by('floor')
            floor_occupancy = []
            
            for floor in floors:
                floor_rooms = Room.objects.filter(hotel=hotel, floor=floor)
                occupied_rooms = floor_rooms.filter(status='occupied')
                
                floor_data = {
                    'floor_number': floor,
                    'total_rooms': floor_rooms.count(),
                    'occupied_rooms': occupied_rooms.count(),
                    'occupancy_rate': round(
                        (occupied_rooms.count() / floor_rooms.count() * 100) if floor_rooms.count() > 0 else 0, 
                        2
                    ),
                }
                floor_occupancy.append(floor_data)
            
            # Monthly occupancy trend
            monthly_trend = self._get_monthly_occupancy_trend(hotel, target_date.year)
            
            stats[f"hotel_{hotel.id}"] = {
                'hotel_id': str(hotel.id),
                'hotel_name': hotel.name,
                'category_occupancy': category_occupancy,
                'floor_occupancy': floor_occupancy,
                'monthly_trend': monthly_trend,
            }
        
        return success_response(data=stats)

    

    def get_guest_stats(self, hotels, target_date, date_from=None, date_to=None):
        """
        Guest-related statistics
        """
        stats = {}
        
        for hotel in hotels:
            # Current guests
            current_guests = Guest.objects.filter(
                stays__hotel=hotel,
                stays__status='active'
            ).distinct()
            
            # New guests today
            new_guests_today = Guest.objects.filter(
                first_contact_date__date=target_date,
                stays__hotel=hotel
            ).distinct()
            
            # Guest distribution by status
            guest_status_dist = current_guests.values('status').annotate(
                count=Count('id')
            )
            
            # Guest nationality distribution
            nationality_dist = current_guests.values('nationality').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            # Loyalty points statistics
            loyalty_stats = current_guests.aggregate(
                total_points=Sum('loyalty_points'),
                avg_points=Avg('loyalty_points'),
                max_points=Coalesce(Max('loyalty_points'), 0)
            )
            
            # Repeat guests (guests with multiple stays)
            repeat_guests = Guest.objects.filter(
                stays__hotel=hotel
            ).annotate(
                stay_count=Count('stays')
            ).filter(stay_count__gt=1).distinct()
            
            stats[f"hotel_{hotel.id}"] = {
                'hotel_id': str(hotel.id),
                'hotel_name': hotel.name,
                'current_guests': current_guests.count(),
                'new_guests_today': new_guests_today.count(),
                'repeat_guests': repeat_guests.count(),
                'guest_status_distribution': list(guest_status_dist),
                'nationality_distribution': list(nationality_dist),
                'loyalty_stats': {
                    'total_points': loyalty_stats['total_points'] or 0,
                    'avg_points': round(loyalty_stats['avg_points'] or 0, 2),
                    'max_points': loyalty_stats['max_points'],
                }
            }
        
        return success_response(data=stats)

    def get_room_stats(self, hotels, target_date, date_from=None, date_to=None):
        """
        Room-related statistics
        """
        stats = {}
        
        for hotel in hotels:
            rooms = Room.objects.filter(hotel=hotel)
            
            # Basic room statistics
            room_status_dist = rooms.values('status').annotate(
                count=Count('id')
            )
            
            # Room category distribution
            category_dist = rooms.values('category__name').annotate(
                count=Count('id')
            )
            
            # Floor distribution
            floor_dist = rooms.values('floor').annotate(
                count=Count('id')
            ).order_by('floor')
            
            # Maintenance statistics
            maintenance_rooms = rooms.filter(status='maintenance')
            cleaning_rooms = rooms.filter(status='cleaning')
            
            stats[f"hotel_{hotel.id}"] = {
                'hotel_id': str(hotel.id),
                'hotel_name': hotel.name,
                'total_rooms': rooms.count(),
                'room_status_distribution': list(room_status_dist),
                'category_distribution': list(category_dist),
                'floor_distribution': list(floor_dist),
                'maintenance_rooms': maintenance_rooms.count(),
                'cleaning_rooms': cleaning_rooms.count(),
            }
        
        return success_response(data=stats)

    def get_staff_stats(self, hotels, target_date, user):
        """
        Hotel staff statistics (only for hotel admins, managers, and superusers)
        """
        # Only allow access to staff stats for authorized roles
        if not (user.is_superuser or 
                user.user_type in ['hotel_admin', 'manager']):
            return forbidden_response("Access denied for staff statistics.")
        
        stats = {}
        
        for hotel in hotels:
            # Staff distribution by user type
            staff_by_type = User.objects.filter(
                hotel=hotel,
                is_active=True
            ).values('user_type').annotate(
                count=Count('id')
            )
            
            # Staff by department
            staff_by_department = []
            for dept in ['Reception', 'Housekeeping', 'Room Service', 'Restaurant', 'Management']:
                dept_count = User.objects.filter(
                    hotel=hotel,
                    is_active=True,
                    department__contains=[dept]
                ).count()
                
                staff_by_department.append({
                    'department': dept,
                    'count': dept_count
                })
            
            # Recently active staff
            recent_active = User.objects.filter(
                hotel=hotel,
                is_active=True,
                last_login__gte=target_date - timedelta(days=7)
            ).count()
            
            stats[f"hotel_{hotel.id}"] = {
                'hotel_id': str(hotel.id),
                'hotel_name': hotel.name,
                'total_staff': User.objects.filter(hotel=hotel, is_active=True).count(),
                'staff_by_type': list(staff_by_type),
                'staff_by_department': staff_by_department,
                'recently_active': recent_active,
            }
        
        return success_response(data=stats)

    def get_performance_stats(self, hotels, target_date, date_from=None, date_to=None):
        """
        Performance metrics and KPIs
        """
        stats = {}
        
        for hotel in hotels:
            # Average stay duration
            avg_stay_duration = Stay.objects.filter(
                hotel=hotel,
                status='completed'
            ).aggregate(
                avg_duration=Avg(
                    ExpressionWrapper(
                        F('actual_check_out') - F('actual_check_in'),
                        output_field=DecimalField()
                    )
                )
            )['avg_duration'] or 0
            
            # Check-in to check-out conversion rate
            total_bookings = Booking.objects.filter(hotel=hotel).count()
            completed_stays = Stay.objects.filter(hotel=hotel, status='completed').count()
            conversion_rate = (completed_stays / total_bookings * 100) if total_bookings > 0 else 0
            
            # Room turnover time (simplified - could be enhanced with actual cleaning times)
            rooms_turned_over_today = Room.objects.filter(
                hotel=hotel,
                status='cleaning',
                updated_at__date=target_date
            ).count()
            
            stats[f"hotel_{hotel.id}"] = {
                'hotel_id': str(hotel.id),
                'hotel_name': hotel.name,
                'avg_stay_duration_days': float(avg_stay_duration.days) if hasattr(avg_stay_duration, 'days') else 0,
                'booking_conversion_rate': round(conversion_rate, 2),
                'rooms_turned_over_today': rooms_turned_over_today,
            }
        
        return success_response(data=stats)

    # Helper methods
    def _get_staff_count(self, hotel):
        """Get staff count by user type for a hotel"""
        staff_counts = User.objects.filter(
            hotel=hotel,
            is_active=True
        ).values('user_type').annotate(count=Count('id'))
        
        return dict(staff_counts)

    def _get_monthly_occupancy_trend(self, hotel, year):
        """Get monthly occupancy trend for a given year"""
        monthly_data = []
        
        for month in range(1, 13):
            month_start = datetime(year, month, 1).date()
            month_end = datetime(year, month, calendar.monthrange(year, month)[1]).date()
            
            total_rooms = Room.objects.filter(hotel=hotel).count()
            if total_rooms == 0:
                occupancy_rate = 0
            else:
                occupied_rooms = Stay.objects.filter(
                    hotel=hotel,
                    status='active',
                    check_in_date__lte=month_end,
                    check_out_date__gte=month_start
                ).values('room').distinct().count()
                
                occupancy_rate = (occupied_rooms / total_rooms) * 100
            
            monthly_data.append({
                'month': calendar.month_abbr[month],
                'occupancy_rate': round(occupancy_rate, 2)
            })
        
        return monthly_data

    def _get_date_range_stats(self, hotel, date_from, date_to):
        """Get statistics for a date range"""
        # This could include trends, comparisons, etc.
        return {
            'date_range_stats': True,
            'date_from': date_from.isoformat(),
            'date_to': date_to.isoformat(),
        }

    


class HotelUserStatsViewSet(viewsets.ViewSet):
    """
    Statistics for hotel users (receptionists, managers, hotel admins)
    Hotel is automatically extracted from the user model - no hotel_id needed
    """
    permission_classes = [permissions.IsAuthenticated, IsHotelStaffOrAdmin]

    def get_hotel_for_user(self, user):
        """Get the hotel associated with the current user"""
        if user.is_superuser:
            # For superusers, return all hotels or redirect to admin endpoints
            return None
        elif user.hotel:
            return user.hotel
        return None

    def list(self, request):
        try:
            """Get overview statistics for user's hotel"""
            user = request.user
            hotel = self.get_hotel_for_user(user)
            
            if not hotel:
                if user.is_superuser:
                    return error_response(
                        "Superusers should use /api/hotel_stat/admin/hotels/ endpoints with hotel_id parameter.", 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                return forbidden_response("No hotel associated with user.")
            
            # Parse date parameters
            target_date, date_from, date_to = self._parse_date_parameters(request)
            if isinstance(target_date, Response):
                return target_date  # Return error response
            
            # Import the main stats class to use its methods
            stats_viewset = HotelStatsViewSet()
            return stats_viewset.get_overview_stats([hotel], target_date, date_from, date_to)
        except Exception as e:
            return error_response(
                f"Failed to fetch user hotel stats: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='occupancy')
    def occupancy(self, request):
        """Get occupancy statistics for user's hotel"""
        return self._get_stat_type(request, 'occupancy')

    @action(detail=False, methods=['get'], url_path='guests')
    def guests(self, request):
        """Get guest statistics for user's hotel"""
        return self._get_stat_type(request, 'guests')

    @action(detail=False, methods=['get'], url_path='rooms')
    def rooms(self, request):
        """Get room statistics for user's hotel"""
        return self._get_stat_type(request, 'rooms')

    @action(detail=False, methods=['get'], url_path='staff')
    def staff(self, request):
        """Get staff statistics for user's hotel"""
        return self._get_stat_type(request, 'staff')

    @action(detail=False, methods=['get'], url_path='performance')
    def performance(self, request):
        """Get performance metrics for user's hotel"""
        return self._get_stat_type(request, 'performance')

    @action(detail=False, methods=['get'], url_path='guest-history')
    def guest_history(self, request):
        try:
            """Get guest history with stays and filters"""
            user = request.user
            hotel = self.get_hotel_for_user(user)
            
            if not hotel:
                if user.is_superuser:
                    return error_response(
                        "Superusers should use /api/hotel_stat/admin/hotels/ endpoints with hotel_id parameter for guest history.", 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                return forbidden_response("No hotel associated with user.")
            
            # Parse filters
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            guest_whatsapp = request.query_params.get('guest_whatsapp')
            
            try:
                if start_date:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                if end_date:
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                return error_response(
                    "Invalid date format. Use YYYY-MM-DD.", 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get guests who have stayed at this hotel
            guests = Guest.objects.filter(
                stays__hotel=hotel
            ).distinct()
            
            # Apply date filters - include guests who were present during the period
            if start_date or end_date:
                filtered_stays = Stay.objects.filter(hotel=hotel)
                
                # Find stays that overlap with the date range
                if start_date:
                    filtered_stays = filtered_stays.filter(check_out_date__gte=start_date)
                if end_date:
                    filtered_stays = filtered_stays.filter(check_in_date__lte=end_date)
                    
                guests = guests.filter(stays__in=filtered_stays).distinct()
            
            # Filter by specific guest WhatsApp number if provided
            if guest_whatsapp:
                guests = guests.filter(whatsapp_number=guest_whatsapp)
            
            # Prepare response data
            guest_data = []
            for guest in guests:
                # Get all stays for this guest, then optionally filter by overlapping dates for display
                guest_stays = Stay.objects.filter(guest=guest, hotel=hotel).order_by('-check_in_date')
                
                # Apply date filters for display purposes - include overlapping stays
                if start_date or end_date:
                    if start_date:
                        guest_stays = guest_stays.filter(check_out_date__gte=start_date)
                    if end_date:
                        guest_stays = guest_stays.filter(check_in_date__lte=end_date)
                
                stays_data = []
                for stay in guest_stays:
                    stay_data = {
                        'id': stay.id,
                        'check_in_date': stay.check_in_date,
                        'check_out_date': stay.check_out_date,
                        'actual_check_in': stay.actual_check_in,
                        'actual_check_out': stay.actual_check_out,
                        'status': stay.status,
                        'room_number': stay.room.room_number if stay.room else None,
                        'room_floor': stay.room.floor if stay.room else None,
                        'room_category': stay.room.category.name if stay.room and stay.room.category else None,
                        'total_amount': float(stay.total_amount),
                        'number_of_guests': stay.number_of_guests,
                        'guest_names': stay.guest_names,
                        'register_number': stay.register_number,
                    }
                    stays_data.append(stay_data)
                
                guest_info = {
                    'id': guest.id,
                    'full_name': guest.full_name,
                    'whatsapp_number': guest.whatsapp_number,
                    'email': guest.email,
                    'nationality': guest.nationality,
                    'preferred_language': guest.preferred_language,
                    'loyalty_points': guest.loyalty_points,
                    'total_stays': guest_stays.count(),
                    'stays': stays_data,
                }
                
                guest_data.append(guest_info)
            
            # Summary statistics - count all guests and their total stays
            all_guests_count = Guest.objects.filter(stays__hotel=hotel).distinct().count()
            all_stays_count = Stay.objects.filter(hotel=hotel).count()
            
            summary = {
                'total_guests': all_guests_count,
                'total_stays': all_stays_count,
                'filtered_guests_shown': guests.count(),
                'filtered_stays_shown': sum(len(guest['stays']) for guest in guest_data),
                'date_range': {
                    'start_date': start_date.isoformat() if start_date else None,
                    'end_date': end_date.isoformat() if end_date else None,
                }
            }
            
            return success_response(data={
                'summary': summary,
                'guests': guest_data
            })
        except Exception as e:
            return error_response(
                f"Failed to retrieve guest history: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='room-history')
    def room_history(self, request):
        try:
            """Get room history with stay records and filters"""
            user = request.user
            hotel = self.get_hotel_for_user(user)
            
            if not hotel:
                if user.is_superuser:
                    return error_response(
                        "Superusers should use /api/hotel_stat/admin/hotels/ endpoints with hotel_id parameter for room history.", 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                return forbidden_response("No hotel associated with user.")
            
            # Parse filters
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            room_id = request.query_params.get('room_id')
            guest_whatsapp = request.query_params.get('guest_whatsapp')
            
            try:
                if start_date:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                if end_date:
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                return error_response(
                    "Invalid date format. Use YYYY-MM-DD.", 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get rooms for this hotel
            rooms_queryset = Room.objects.filter(hotel=hotel)
            
            # Filter by specific room ID if provided
            if room_id:
                try:
                    rooms_queryset = rooms_queryset.filter(id=int(room_id))
                except ValueError:
                    return error_response(
                        "Invalid room_id format.", 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Prepare response data
            room_data = []
            for room in rooms_queryset:
                # Get all stays for this room, then optionally filter by overlapping dates for display
                room_stays = Stay.objects.filter(room=room)
                
                # Apply date filters for display purposes - include overlapping stays
                if start_date or end_date:
                    if start_date:
                        room_stays = room_stays.filter(check_out_date__gte=start_date)
                    if end_date:
                        room_stays = room_stays.filter(check_in_date__lte=end_date)
                
                # Apply guest WhatsApp filter if provided
                if guest_whatsapp:
                    room_stays = room_stays.filter(guest__whatsapp_number=guest_whatsapp)
                
                room_stays = room_stays.order_by('-check_in_date')
                
                stays_data = []
                for stay in room_stays:
                    stay_data = {
                        'id': stay.id,
                        'guest_name': stay.guest.full_name,
                        'guest_whatsapp': stay.guest.whatsapp_number,
                        'check_in_date': stay.check_in_date,
                        'check_out_date': stay.check_out_date,
                        'actual_check_in': stay.actual_check_in,
                        'actual_check_out': stay.actual_check_out,
                        'status': stay.status,
                        'total_amount': float(stay.total_amount),
                        'number_of_guests': stay.number_of_guests,
                        'guest_names': stay.guest_names,
                        'register_number': stay.register_number,
                    }
                    stays_data.append(stay_data)
                
                room_info = {
                    'id': room.id,
                    'room_number': room.room_number,
                    'floor': room.floor,
                    'category': room.category.name if room.category else None,
                    'base_price': float(room.category.base_price) if room.category else None,
                    'status': room.status,
                    'total_stays': room_stays.count(),
                    'stays': stays_data,
                }
                
                room_data.append(room_info)
            
            # Summary statistics
            summary = {
                'total_rooms': rooms_queryset.count(),
                'total_stays': sum(room['total_stays'] for room in room_data),
                'date_range': {
                    'start_date': start_date.isoformat() if start_date else None,
                    'end_date': end_date.isoformat() if end_date else None,
                }
            }
            
            return success_response(data={
                'summary': summary,
                'rooms': room_data
            })
        except Exception as e:
            return error_response(
                f"Failed to retrieve room history: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='conversation-history')
    def conversation_history(self, request):
        try:
            """Get conversation history with message counts and filters"""
            user = request.user
            hotel = self.get_hotel_for_user(user)
            
            if not hotel:
                if user.is_superuser:
                    return error_response(
                        "Superusers should use /api/hotel_stat/admin/hotels/ endpoints with hotel_id parameter for conversation history.", 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                return forbidden_response("No hotel associated with user.")
            
            # Parse filters
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            
            try:
                if start_date:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                if end_date:
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                return error_response(
                    "Invalid date format. Use YYYY-MM-DD.", 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get conversations for this hotel
            conversations_queryset = Conversation.objects.filter(hotel=hotel)
            
            # Apply date filters
            if start_date:
                conversations_queryset = conversations_queryset.filter(created_at__gte=start_date)
            if end_date:
                conversations_queryset = conversations_queryset.filter(created_at__lte=end_date)
            
            # Get message counts for each conversation
            conversations_data = []
            total_messages = 0
            
            for conversation in conversations_queryset.order_by('-created_at'):
                message_count = Message.objects.filter(conversation=conversation).count()
                total_messages += message_count
                
                # Get guest information
                guest_info = {
                    'id': conversation.guest.id,
                    'full_name': conversation.guest.full_name,
                    'whatsapp_number': conversation.guest.whatsapp_number,
                }
                
                # Get room info from active stay if available
                active_stay = conversation.guest.stays.filter(
                    status='active',
                    hotel=hotel
                ).first()
                if active_stay and active_stay.room:
                    guest_info['room_number'] = active_stay.room.room_number
                    guest_info['floor'] = active_stay.room.floor
                
                conversation_data = {
                    'id': conversation.id,
                    'guest': guest_info,
                    'department': conversation.department,
                    'conversation_type': conversation.conversation_type,
                    'status': conversation.status,
                    'message_count': message_count,
                    'created_at': conversation.created_at,
                    'last_message_at': conversation.last_message_at,
                    'last_message_preview': conversation.last_message_preview,
                    'is_fulfilled': conversation.is_request_fulfilled,
                    'fulfillment_status': conversation.get_fulfillment_status_display(),
                }
                
                conversations_data.append(conversation_data)
            
            # Summary statistics
            summary = {
                'total_conversations': conversations_queryset.count(),
                'total_messages': total_messages,
                'average_messages_per_conversation': round(
                    total_messages / conversations_queryset.count() if conversations_queryset.count() > 0 else 0, 2
                ),
                'date_range': {
                    'start_date': start_date.isoformat() if start_date else None,
                    'end_date': end_date.isoformat() if end_date else None,
                }
            }
            
            # Department breakdown
            dept_breakdown = conversations_queryset.values('department').annotate(
                count=Count('id'),
                total_messages=Count('messages')
            ).order_by('-count')
            
            summary['department_breakdown'] = list(dept_breakdown)
            
            # Conversation type breakdown
            type_breakdown = conversations_queryset.values('conversation_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            summary['type_breakdown'] = list(type_breakdown)
            
            return success_response(data={
                'summary': summary,
                'conversations': conversations_data
            })
        except Exception as e:
            return error_response(
                f"Failed to retrieve conversation history: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='feedback-analytics')
    def feedback_analytics(self, request):
        try:
            """Get comprehensive feedback analytics with ratings and filters"""
            user = request.user
            hotel = self.get_hotel_for_user(user)
            
            if not hotel:
                if user.is_superuser:
                    return error_response(
                        "Superusers should use /api/hotel_stat/admin/hotels/ endpoints with hotel_id parameter for feedback analytics.", 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                return forbidden_response("No hotel associated with user.")
            
            # Parse filters
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            room_id = request.query_params.get('room_id')
            guest_whatsapp = request.query_params.get('guest_whatsapp')
            
            try:
                if start_date:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                if end_date:
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                return error_response(
                    "Invalid date format. Use YYYY-MM-DD.", 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get feedback for this hotel
            feedback_queryset = Feedback.objects.filter(stay__hotel=hotel)
            
            # Apply date filters
            if start_date:
                feedback_queryset = feedback_queryset.filter(created_at__gte=start_date)
            if end_date:
                feedback_queryset = feedback_queryset.filter(created_at__lte=end_date)
            
            # Apply room filter
            if room_id:
                try:
                    feedback_queryset = feedback_queryset.filter(stay__room_id=int(room_id))
                except ValueError:
                    return error_response(
                        "Invalid room_id format.", 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Apply guest WhatsApp filter
            if guest_whatsapp:
                feedback_queryset = feedback_queryset.filter(guest__whatsapp_number=guest_whatsapp)
            
            # Order by most recent
            feedback_queryset = feedback_queryset.order_by('-created_at')
            
            # Prepare feedback data
            feedback_data = []
            ratings_list = []
            
            for feedback in feedback_queryset:
                # Get stay information
                stay = feedback.stay
                guest = feedback.guest
                
                # Get room information
                room_info = None
                if stay.room:
                    room_info = {
                        'id': stay.room.id,
                        'room_number': stay.room.room_number,
                        'floor': stay.room.floor,
                        'category': stay.room.category.name if stay.room.category else None,
                    }
                
                feedback_detail = {
                    'id': feedback.id,
                    'rating': feedback.rating,
                    'note': feedback.note,
                    'created_at': feedback.created_at,
                    'stay': {
                        'id': stay.id,
                        'check_in_date': stay.check_in_date,
                        'check_out_date': stay.check_out_date,
                        'actual_check_in': stay.actual_check_in,
                        'actual_check_out': stay.actual_check_out,
                        'status': stay.status,
                        'total_amount': float(stay.total_amount),
                        'room': room_info,
                        'register_number': stay.register_number,
                    },
                    'guest': {
                        'id': guest.id,
                        'full_name': guest.full_name,
                        'whatsapp_number': guest.whatsapp_number,
                        'email': guest.email,
                        'nationality': guest.nationality,
                        'loyalty_points': guest.loyalty_points,
                    }
                }
                
                feedback_data.append(feedback_detail)
                ratings_list.append(feedback.rating)
            
            # Calculate statistics
            total_feedback = len(ratings_list)
            
            # Rating distribution
            rating_distribution = {}
            for rating in range(1, 6):  # Ratings 1-5
                count = ratings_list.count(rating)
                rating_distribution[str(rating)] = count
            
            # Calculate averages
            if total_feedback > 0:
                avg_rating = sum(ratings_list) / total_feedback
                percentage_5_star = (rating_distribution.get('5', 0) / total_feedback) * 100
                percentage_4_plus_star = ((rating_distribution.get('4', 0) + rating_distribution.get('5', 0)) / total_feedback) * 100
            else:
                avg_rating = 0
                percentage_5_star = 0
                percentage_4_plus_star = 0
            
            # Room-specific statistics
            room_breakdown = feedback_queryset.values('stay__room__room_number', 'stay__room__id').annotate(
                count=Count('id'),
                avg_rating=Avg('rating')
            ).order_by('-count')
            
            # Monthly rating trends
            monthly_trends = {}
            for feedback in feedback_queryset:
                month_key = feedback.created_at.strftime('%Y-%m')
                if month_key not in monthly_trends:
                    monthly_trends[month_key] = {'ratings': [], 'count': 0}
                monthly_trends[month_key]['ratings'].append(feedback.rating)
                monthly_trends[month_key]['count'] += 1
            
            monthly_avg_ratings = []
            for month in sorted(monthly_trends.keys()):
                month_data = monthly_trends[month]
                avg_month_rating = sum(month_data['ratings']) / len(month_data['ratings'])
                monthly_avg_ratings.append({
                    'month': month,
                    'average_rating': round(avg_month_rating, 2),
                    'total_feedback': month_data['count']
                })
            
            # Guest nationality breakdown (if available)
            nationality_breakdown = feedback_queryset.values('guest__nationality').annotate(
                count=Count('id'),
                avg_rating=Avg('rating')
            ).order_by('-count')
            
            # Summary statistics
            summary = {
                'total_feedback': total_feedback,
                'average_rating': round(avg_rating, 2),
                'percentage_5_star': round(percentage_5_star, 2),
                'percentage_4_plus_star': round(percentage_4_plus_star, 2),
                'rating_distribution': rating_distribution,
                'date_range': {
                    'start_date': start_date.isoformat() if start_date else None,
                    'end_date': end_date.isoformat() if end_date else None,
                },
                'room_breakdown': list(room_breakdown),
                'monthly_trends': monthly_avg_ratings,
                'nationality_breakdown': list(nationality_breakdown),
            }
            
            return success_response(data={
                'summary': summary,
                'feedbacks': feedback_data
            })
        except Exception as e:
            return error_response(
                f"Failed to retrieve feedback analytics: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='overview')
    def overview(self, request):
        try:
            """Get key hotel metrics: Total Guests, Total Rooms, Occupancy Rate, Total Revenue"""
            user = request.user
            hotel = self.get_hotel_for_user(user)
            
            if not hotel:
                if user.is_superuser:
                    return error_response(
                        "Superusers should use /api/hotel_stat/admin/hotels/ endpoints with hotel_id parameter for overview.", 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                return forbidden_response("No hotel associated with user.")
            
            # Parse date parameters for revenue calculation
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            target_date_str = request.query_params.get('date')
            
            try:
                if target_date_str:
                    target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
                else:
                    target_date = timezone.now().date()
                    
                if start_date:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                if end_date:
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                return error_response(
                    "Invalid date format. Use YYYY-MM-DD.", 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 1. Total Rooms
            total_rooms = Room.objects.filter(hotel=hotel).count()
            
            # 2. Total Guests (unique guests who have stayed at the hotel)
            total_guests = Guest.objects.filter(
                stays__hotel=hotel
            ).distinct().count()
            
            # 3. Current Occupancy Rate
            occupied_rooms = Room.objects.filter(hotel=hotel, status='occupied').count()
            occupancy_rate = (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0
            
            # 4. Current Guests (checked in today)
            current_stays = Stay.objects.filter(
                hotel=hotel,
                status='active',
                check_in_date__lte=target_date,
                check_out_date__gte=target_date
            )
            current_guests_count = current_stays.count()
            
            # 5. Total Revenue
            if start_date and end_date:
                # Revenue for date range
                completed_stays = Stay.objects.filter(
                    hotel=hotel,
                    status='completed',
                    check_out_date__gte=start_date,
                    check_out_date__lte=end_date
                )
                revenue_period = f"{start_date} to {end_date}"
            else:
                # Revenue for current month
                month_start = target_date.replace(day=1)
                completed_stays = Stay.objects.filter(
                    hotel=hotel,
                    status='completed',
                    check_out_date__gte=month_start,
                    check_out_date__lte=target_date
                )
                revenue_period = f"Month of {target_date.strftime('%B %Y')}"
            
            # Also include confirmed bookings revenue
            confirmed_bookings = Booking.objects.filter(
                hotel=hotel,
                status='confirmed'
            )
            
            if start_date and end_date:
                confirmed_bookings = confirmed_bookings.filter(
                    check_in_date__gte=start_date,
                    check_in_date__lte=end_date
                )
            
            total_revenue = (completed_stays.aggregate(
                total=Sum('total_amount')
            )['total'] or 0) + (confirmed_bookings.aggregate(
                total=Sum('total_amount')
            )['total'] or 0)
            
            # 6. Additional useful metrics
            # Expected check-ins today
            expected_checkins_today = Booking.objects.filter(
                hotel=hotel,
                check_in_date=target_date,
                status='confirmed'
            ).count()
            
            # Expected check-outs today
            expected_checkouts_today = Stay.objects.filter(
                hotel=hotel,
                status='active',
                check_out_date=target_date
            ).count()
            
            # Available rooms for check-in
            available_rooms = Room.objects.filter(hotel=hotel, status='available').count()
            
            # Rooms under maintenance
            maintenance_rooms = Room.objects.filter(hotel=hotel, status='maintenance').count()
            
            # Average daily rate (ADR) for the period
            if start_date and end_date:
                days_in_period = (end_date - start_date).days + 1
                occupied_room_nights = completed_stays.aggregate(
                    total_nights=Sum(
                        ExpressionWrapper(
                            F('actual_check_out') - F('actual_check_in'),
                            output_field=DurationField()
                        )
                    )
                )['total_nights'] or timedelta(0)
                # Convert timedelta to total seconds, then to days for ADR calculation
                occupied_nights_days = occupied_room_nights.total_seconds() / (24 * 3600)
                adr = total_revenue / occupied_nights_days if occupied_nights_days > 0 else 0
            else:
                # ADR for current month
                month_start = target_date.replace(day=1)
                days_in_month = (target_date - month_start).days + 1
                occupied_room_nights = completed_stays.aggregate(
                    total_nights=Sum(
                        ExpressionWrapper(
                            F('actual_check_out') - F('actual_check_in'),
                            output_field=DurationField()
                        )
                    )
                )['total_nights'] or timedelta(0)
                # Convert timedelta to total seconds, then to days for ADR calculation
                occupied_nights_days = occupied_room_nights.total_seconds() / (24 * 3600)
                adr = total_revenue / occupied_nights_days if occupied_nights_days > 0 else 0
            
            # Hotel basic details
            hotel_details = {
                'name': hotel.name,
                'address': hotel.address,
                'phone': hotel.phone,
            }
            
            # Prepare response
            overview_data = {
                'hotel_details': hotel_details,
                'metrics': {
                    'total_rooms': total_rooms,
                    'total_guests': total_guests,
                    'current_guests': current_guests_count,
                    'occupancy_rate': round(occupancy_rate, 2),
                    'total_revenue': float(total_revenue),
                    'average_daily_rate': round(float(adr), 2),
                },
                'today_overview': {
                    'date': target_date.isoformat(),
                    'expected_checkins': expected_checkins_today,
                    'expected_checkouts': expected_checkouts_today,
                    'available_rooms': available_rooms,
                    'rooms_under_maintenance': maintenance_rooms,
                },
                'revenue_summary': {
                    'period': revenue_period,
                    'total_revenue': float(total_revenue),
                    'completed_stays_revenue': float(completed_stays.aggregate(
                        total=Sum('total_amount')
                    )['total'] or 0),
                    'confirmed_bookings_revenue': float(confirmed_bookings.aggregate(
                        total=Sum('total_amount')
                    )['total'] or 0),
                },
                'room_status_breakdown': {
                    'occupied': occupied_rooms,
                    'available': available_rooms,
                    'cleaning': Room.objects.filter(hotel=hotel, status='cleaning').count(),
                    'maintenance': maintenance_rooms,
                    'out_of_order': Room.objects.filter(hotel=hotel, status='out_of_order').count(),
                },
                'date_filters_applied': {
                    'date': target_date.isoformat(),
                    'start_date': start_date.isoformat() if start_date else None,
                    'end_date': end_date.isoformat() if end_date else None,
                }
            }
            
            return success_response(data=overview_data)
        except Exception as e:
            return error_response(
                f"Failed to retrieve overview stats: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_stat_type(self, request, stat_type):
        try:
            """Helper method to handle different stat types"""
            user = request.user
            hotel = self.get_hotel_for_user(user)
            
            if not hotel:
                if user.is_superuser:
                    return error_response(
                        f"Superusers should use /api/hotel_stat/admin/hotels/ endpoints with hotel_id parameter for {stat_type} stats.", 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                return forbidden_response("No hotel associated with user.")
            
            # Parse date parameters
            target_date, date_from, date_to = self._parse_date_parameters(request)
            if isinstance(target_date, Response):
                return target_date  # Return error response
            
            # Import the main stats class to use its methods
            stats_viewset = HotelStatsViewSet()
            
            # Route to appropriate statistics method
            if stat_type == 'occupancy':
                return stats_viewset.get_occupancy_stats([hotel], target_date, date_from, date_to)
            elif stat_type == 'guests':
                return stats_viewset.get_guest_stats([hotel], target_date, date_from, date_to)
            elif stat_type == 'rooms':
                return stats_viewset.get_room_stats([hotel], target_date, date_from, date_to)
            elif stat_type == 'staff':
                return stats_viewset.get_staff_stats([hotel], target_date, user)
            elif stat_type == 'performance':
                return stats_viewset.get_performance_stats([hotel], target_date, date_from, date_to)
            else:
                return error_response(
                    f"Invalid stat type: {stat_type}", 
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return error_response(
                f"Failed to get {stat_type} stats: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _parse_date_parameters(self, request):
        """Parse date parameters from request"""
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        date_str = request.query_params.get('date')
        
        try:
            if date_str:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                target_date = timezone.now().date()
                
            if date_from:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            if date_to:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                
            return target_date, date_from, date_to
        except ValueError:
            return error_response(
                "Invalid date format. Use YYYY-MM-DD.", 
                status=status.HTTP_400_BAD_REQUEST
            )


class PlatformStatsViewSet(HotelStatsViewSet):
    """
    Platform-wide statistics (for superusers only)
    """
    permission_classes = [permissions.IsAuthenticated, IsHotelManagerOrAdmin]

    def get_accessible_hotels(self, user, hotel_id=None):
        """
        Platform view - only superusers can access all hotels
        """
        if not user.is_superuser:
            return Hotel.objects.none()
            
        if hotel_id:
            try:
                return Hotel.objects.filter(id=hotel_id)
            except:
                return Hotel.objects.none()
        return Hotel.objects.all()

    def list(self, request):
        try:
            """Get platform-wide overview statistics"""
            user = request.user
            
            if not user.is_superuser:
                return forbidden_response("Access denied. Superuser access required.")
            
            # Parse date parameters
            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')
            date_str = request.query_params.get('date')
            
            try:
                if date_str:
                    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                else:
                    target_date = timezone.now().date()
                    
                if date_from:
                    date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                if date_to:
                    date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            except ValueError:
                return error_response(
                    "Invalid date format. Use YYYY-MM-DD.", 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            hotels = self.get_accessible_hotels(user)
            return self.get_overview_stats(hotels, target_date, date_from, date_to)
        except Exception as e:
            return error_response(
                f"Failed to retrieve platform overview: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='(?P<stat_type>[^/.]+)')
    def detailed_stats(self, request, stat_type=None):
        try:
            """Get platform-wide detailed statistics"""
            user = request.user
            
            if not user.is_superuser:
                return forbidden_response("Access denied. Superuser access required.")
            
            # Parse date parameters
            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')
            date_str = request.query_params.get('date')
            
            try:
                if date_str:
                    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                else:
                    target_date = timezone.now().date()
                    
                if date_from:
                    date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                if date_to:
                    date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            except ValueError:
                return error_response(
                    "Invalid date format. Use YYYY-MM-DD.", 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            hotels = self.get_accessible_hotels(user)
            
            # Route to appropriate statistics method
            if stat_type == 'occupancy':
                return self.get_occupancy_stats(hotels, target_date, date_from, date_to)
            elif stat_type == 'guests':
                return self.get_guest_stats(hotels, target_date, date_from, date_to)
            elif stat_type == 'rooms':
                return self.get_room_stats(hotels, target_date, date_from, date_to)
            elif stat_type == 'staff':
                return self.get_staff_stats(hotels, target_date, user)
            elif stat_type == 'performance':
                return self.get_performance_stats(hotels, target_date, date_from, date_to)
            else:
                return error_response(
                    f"Invalid stat type: {stat_type}", 
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return error_response(
                f"Failed to retrieve platform {stat_type} stats: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class HotelComparisonView(views.APIView):
    """
    Compare statistics between multiple hotels (for hotel managers, hotel admins, and superusers)
    """
    permission_classes = [permissions.IsAuthenticated, IsHotelManagerOrAdmin]

    def get(self, request):
        try:
            """Compare statistics between multiple hotels"""
            user = request.user
            hotel_ids = request.query_params.getlist('hotels')
            stat_type = request.query_params.get('stat_type', 'overview')
            
            # Only hotel admins, managers, and superusers can compare multiple hotels
            if not (user.is_superuser or user.user_type in ['hotel_admin', 'manager']):
                return forbidden_response(
                    "Access denied. Only hotel admins, managers, and superusers can compare hotels."
                )
            
            if not hotel_ids:
                return error_response(
                    "At least one hotel ID is required.", 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            hotels = Hotel.objects.filter(id__in=hotel_ids)
            if hotels.count() != len(hotel_ids):
                return error_response(
                    "One or more hotel IDs are invalid.", 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Parse date parameters
            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')
            date_str = request.query_params.get('date')
            
            try:
                if date_str:
                    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                else:
                    target_date = timezone.now().date()
                    
                if date_from:
                    date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                if date_to:
                    date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            except ValueError:
                return error_response(
                    "Invalid date format. Use YYYY-MM-DD.", 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Use the main stats viewset to get individual hotel data
            stats_viewset = HotelStatsViewSet()
            
            # Get stats for each hotel
            comparison_data = {}
            for hotel in hotels:
                # Create a mock request object
                class MockRequest:
                    def __init__(self, query_params):
                        self.query_params = query_params
                        self.user = user  # Add user to mock request for checks
                
                mock_query_params = request.query_params.copy()
                mock_query_params['stat_type'] = stat_type
                
                # Get the hotel statistics
                # Note: We need to handle potential recursion or method calls carefully.
                # Since we are calling retrieve, which calls get_accessible_hotels, we need to ensure permissions work.
                # However, for comparison view, we've already checked permissions at the top level.
                
                # Direct method call approach (cleaner than mocking request for retrieve)
                if stat_type == 'overview':
                    response_data = stats_viewset.get_overview_stats([hotel], target_date, date_from, date_to)
                elif stat_type == 'occupancy':
                    response_data = stats_viewset.get_occupancy_stats([hotel], target_date, date_from, date_to)
                elif stat_type == 'guests':
                    response_data = stats_viewset.get_guest_stats([hotel], target_date, date_from, date_to)
                elif stat_type == 'rooms':
                    response_data = stats_viewset.get_room_stats([hotel], target_date, date_from, date_to)
                elif stat_type == 'staff':
                    response_data = stats_viewset.get_staff_stats([hotel], target_date, user)
                elif stat_type == 'performance':
                    response_data = stats_viewset.get_performance_stats([hotel], target_date, date_from, date_to)
                else:
                    return error_response(f"Invalid stat type: {stat_type}", status=status.HTTP_400_BAD_REQUEST)
                
                if hasattr(response_data, 'data'):
                    comparison_data[f"hotel_{hotel.id}"] = response_data.data
                else:
                    # If response_data is not a DRF Response (e.g. error response dict from helper)
                     comparison_data[f"hotel_{hotel.id}"] = response_data
            
            return success_response(data=comparison_data)
        except Exception as e:
            return error_response(
                f"Failed to perform hotel comparison: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )