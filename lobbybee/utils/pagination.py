from rest_framework.pagination import PageNumberPagination
from lobbybee.utils.responses import paginated_response

class StandardizedPagination(PageNumberPagination):
    """
    Standardized pagination class that wraps the response in the consistent
    {success, message, data} format.
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return paginated_response(
            data={
                'count': self.page.paginator.count,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'results': data
            }
        )
