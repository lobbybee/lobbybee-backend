from django_filters import rest_framework as filters
from .models import Room

class RoomFilter(filters.FilterSet):
    occupied = filters.BooleanFilter(method='filter_occupied')
    category = filters.CharFilter(method='filter_by_category')

    class Meta:
        model = Room
        fields = ['status', 'floor', 'category']

    def filter_by_category(self, queryset, name, value):
        if value:
            return queryset.filter(category__id=value)
        return queryset

    def filter_occupied(self, queryset, name, value):
        if value is True:
            return queryset.filter(status='occupied')
        elif value is False:
            return queryset.exclude(status='occupied')
        return queryset
