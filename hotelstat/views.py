from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from hotel.models import Hotel, Room, Department
from guest.models import Guest, Stay
from django.db.models import Count
from hotel.permissions import IsHotelAdmin

from datetime import datetime

class StatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        stat_type = kwargs.get('stat_type')
        user = request.user

        date_str = request.query_params.get('date')
        date_obj = None
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        if user.is_superuser:
            if stat_type:
                return Response({"error": "Detailed stats are not available for superadmins."}, status=status.HTTP_400_BAD_REQUEST)
            return self.get_global_stats(date_obj)

        if not hasattr(user, 'hotel') or not user.hotel:
            return Response({"error": "User is not associated with a hotel."}, status=status.HTTP_400_BAD_REQUEST)

        if stat_type:
            return self.get_detailed_stats(user.hotel, stat_type, date_obj)
        else:
            return self.get_hotel_stats(user.hotel, date_obj)

    def get_global_stats(self, date_obj=None):
        hotels = Hotel.objects.all()
        guests = Guest.objects.all()
        rooms = Room.objects.all()
        departments = Department.objects.all()
        stays = Stay.objects.all()

        if date_obj:
            hotels = hotels.filter(registration_date__date=date_obj)
            guests = guests.filter(first_contact_date__date=date_obj)
            rooms = rooms.filter(created_at__date=date_obj)
            departments = departments.filter(created_at__date=date_obj)
            stays = stays.filter(created_at__date=date_obj)

        stats = {
            'total_hotels': hotels.count(),
            'total_guests': guests.count(),
            'total_rooms': rooms.count(),
            'total_departments': departments.count(),
            'total_stays': stays.count(),
        }
        return Response(stats)

    def get_hotel_stats(self, hotel, date_obj=None):
        guests = Guest.objects.filter(stays__hotel=hotel).distinct()
        rooms = Room.objects.filter(hotel=hotel)
        departments = Department.objects.filter(hotel=hotel)
        stays = Stay.objects.filter(hotel=hotel)

        if date_obj:
            guests = guests.filter(first_contact_date__date=date_obj)
            rooms = rooms.filter(created_at__date=date_obj)
            departments = departments.filter(created_at__date=date_obj)
            stays = stays.filter(created_at__date=date_obj)

        stats = {
            'total_guests': guests.count(),
            'total_rooms': rooms.count(),
            'occupied_rooms': rooms.filter(status='occupied').count(),
            'available_rooms': rooms.filter(status='available').count(),
            'total_departments': departments.count(),
            'active_stays': stays.filter(status='active').count(),
        }
        return Response(stats)

    def get_detailed_stats(self, hotel, stat_type, date_obj=None):
        if stat_type == 'rooms':
            stats = self.get_room_stats(hotel, date_obj)
        elif stat_type == 'guests':
            stats = self.get_guest_stats(hotel, date_obj)
        else:
            return Response({"error": "Invalid stat type."}, status=status.HTTP_400_BAD_REQUEST)

        return Response(stats)

    def get_room_stats(self, hotel, date_obj=None):
        rooms = Room.objects.filter(hotel=hotel)
        if date_obj:
            rooms = rooms.filter(created_at__date=date_obj)
        room_stats = rooms.values('status').annotate(count=Count('status'))
        return {
            'total_rooms': rooms.count(),
            'rooms_by_status': list(room_stats)
        }

    def get_guest_stats(self, hotel, date_obj=None):
        guests = Guest.objects.filter(stays__hotel=hotel)
        if date_obj:
            guests = guests.filter(first_contact_date__date=date_obj)
        guest_stats = guests.values('status').annotate(count=Count('status'))
        return {
            'total_guests': guests.distinct().count(),
            'guests_by_status': list(guest_stats)
        }
