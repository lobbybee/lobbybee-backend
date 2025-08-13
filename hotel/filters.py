from django_filters import rest_framework as filters
from .models import Room

class RoomFilter(filters.FilterSet):
    occupied = filters.BooleanFilter(method='filter_occupied')

    class Meta:
        model = Room
        fields = ['status', 'floor', 'category']

    def filter_occupied(self, queryset, name, value):
        if value is True:
            return queryset.filter(status='occupied')
        elif value is False:
            return queryset.exclude(status='occupied')
        return queryset
