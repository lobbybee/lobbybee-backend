from rest_framework import viewsets, permissions, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from hotel.models import Hotel, Room, RoomCategory
from guest.models import Guest, Stay, Booking
from user.models import User
from user.permissions import IsHotelManagerOrAdmin
from django.db.models import Count, Q, Avg, Sum, F, ExpressionWrapper, DecimalField, Max
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import calendar


class HotelStatsViewSet(viewsets.ViewSet):
    """
    Comprehensive hotel statistics API with proper filtering by hotel and user type
    Access restricted to hotel managers, hotel admins, and superusers only
    """
    permission_classes = [permissions.IsAuthenticated, IsHotelManagerOrAdmin]

    def list(self, request):
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
        
        return Response(hotels_data)

    def retrieve(self, request, pk=None):
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
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Determine which hotel(s) the user can access
        accessible_hotels = self.get_accessible_hotels(user, hotel_id)
        
        if not accessible_hotels:
            return Response(
                {"error": "Access denied or no hotel associated."}, 
                status=status.HTTP_403_FORBIDDEN
            )

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
            return Response(
                {"error": f"Invalid stat type: {stat_type}"}, 
                status=status.HTTP_400_BAD_REQUEST
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

        return Response(stats)

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
        
        return Response(stats)

    

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
        
        return Response(stats)

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
        
        return Response(stats)

    def get_staff_stats(self, hotels, target_date, user):
        """
        Hotel staff statistics (only for hotel admins, managers, and superusers)
        """
        # Only allow access to staff stats for authorized roles
        if not (user.is_superuser or 
                user.user_type in ['hotel_admin', 'manager']):
            return Response(
                {"error": "Access denied for staff statistics."}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
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
        
        return Response(stats)

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
        
        return Response(stats)

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
    Statistics for hotel users (managers, hotel admins)
    Hotel is automatically extracted from the user model - no hotel_id needed
    """
    permission_classes = [permissions.IsAuthenticated, IsHotelManagerOrAdmin]

    def get_hotel_for_user(self, user):
        """Get the hotel associated with the current user"""
        if user.is_superuser:
            # For superusers, return all hotels or redirect to admin endpoints
            return None
        elif user.hotel:
            return user.hotel
        return None

    def list(self, request):
        """Get overview statistics for user's hotel"""
        user = request.user
        hotel = self.get_hotel_for_user(user)
        
        if not hotel:
            if user.is_superuser:
                return Response(
                    {"error": "Superusers should use /api/hotel_stat/admin/hotels/ endpoints with hotel_id parameter."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                {"error": "No hotel associated with user."}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Parse date parameters
        target_date, date_from, date_to = self._parse_date_parameters(request)
        if isinstance(target_date, Response):
            return target_date  # Return error response
        
        # Import the main stats class to use its methods
        stats_viewset = HotelStatsViewSet()
        return stats_viewset.get_overview_stats([hotel], target_date, date_from, date_to)

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

    def _get_stat_type(self, request, stat_type):
        """Helper method to handle different stat types"""
        user = request.user
        hotel = self.get_hotel_for_user(user)
        
        if not hotel:
            if user.is_superuser:
                return Response(
                    {"error": f"Superusers should use /api/hotel_stat/admin/hotels/ endpoints with hotel_id parameter for {stat_type} stats."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                {"error": "No hotel associated with user."}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
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
            return Response(
                {"error": f"Invalid stat type: {stat_type}"}, 
                status=status.HTTP_400_BAD_REQUEST
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
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."}, 
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
        """Get platform-wide overview statistics"""
        user = request.user
        
        if not user.is_superuser:
            return Response(
                {"error": "Access denied. Superuser access required."}, 
                status=status.HTTP_403_FORBIDDEN
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
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        hotels = self.get_accessible_hotels(user)
        return self.get_overview_stats(hotels, target_date, date_from, date_to)

    @action(detail=False, methods=['get'], url_path='(?P<stat_type>[^/.]+)')
    def detailed_stats(self, request, stat_type=None):
        """Get platform-wide detailed statistics"""
        user = request.user
        
        if not user.is_superuser:
            return Response(
                {"error": "Access denied. Superuser access required."}, 
                status=status.HTTP_403_FORBIDDEN
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
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."}, 
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
            return Response(
                {"error": f"Invalid stat type: {stat_type}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class HotelComparisonView(views.APIView):
    """
    Compare statistics between multiple hotels (for hotel managers, hotel admins, and superusers)
    """
    permission_classes = [permissions.IsAuthenticated, IsHotelManagerOrAdmin]

    def get(self, request):
        """Compare statistics between multiple hotels"""
        user = request.user
        hotel_ids = request.query_params.getlist('hotels')
        stat_type = request.query_params.get('stat_type', 'overview')
        
        # Only hotel admins, managers, and superusers can compare multiple hotels
        if not (user.is_superuser or user.user_type in ['hotel_admin', 'manager']):
            return Response(
                {"error": "Access denied. Only hotel admins, managers, and superusers can compare hotels."}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not hotel_ids:
            return Response(
                {"error": "At least one hotel ID is required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        hotels = Hotel.objects.filter(id__in=hotel_ids)
        if hotels.count() != len(hotel_ids):
            return Response(
                {"error": "One or more hotel IDs are invalid."}, 
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
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."}, 
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
            
            mock_query_params = request.query_params.copy()
            mock_query_params['stat_type'] = stat_type
            
            # Get the hotel statistics
            response = stats_viewset.retrieve(MockRequest(mock_query_params), pk=str(hotel.id))
            if hasattr(response, 'status_code') and response.status_code == 200:
                comparison_data[f"hotel_{hotel.id}"] = response.data
            else:
                # Fallback: directly call the appropriate stats method
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
                    response_data = Response({"error": f"Invalid stat type: {stat_type}"}, status=status.HTTP_400_BAD_REQUEST)
                
                if hasattr(response_data, 'data'):
                    comparison_data[f"hotel_{hotel.id}"] = response_data.data
        
        return Response(comparison_data)