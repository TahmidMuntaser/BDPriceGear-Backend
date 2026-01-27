from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class FlexiblePagination(PageNumberPagination):
 
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 1000  # Max per page (when not using 'all')
    
    def paginate_queryset(self, queryset, request, view=None):
        
        page_size_param = request.query_params.get(self.page_size_query_param, '')
        
        if page_size_param.lower() == 'all':
            # Return None to indicate no pagination
            self._no_pagination = True
            self._all_results = list(queryset)
            self._count = len(self._all_results)
            return self._all_results
        
        self._no_pagination = False
        return super().paginate_queryset(queryset, request, view)
    
    def get_paginated_response(self, data):
        """Return response with or without pagination metadata."""
        if getattr(self, '_no_pagination', False):
            return Response({
                'count': self._count,
                'next': None,
                'previous': None,
                'results': data
            })
        return super().get_paginated_response(data)
