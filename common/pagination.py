from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class CustomPageNumberPagination(PageNumberPagination):
    def get_paginated_response(self, data):
        total_pages = self.page.paginator.num_pages if self.page else 1
        page_size = self.page.paginator.per_page if self.page else self.page_size

        return Response({
            "count": self.page.paginator.count if self.page else len(data),
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "total_pages": total_pages,
            "page_size": page_size,
            "results": data
        })


class CustomPagePermissionPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 500

    def get_paginated_response(self, data):
        total_pages = self.page.paginator.num_pages if self.page else 1
        page_size = self.page.paginator.per_page if self.page else self.page_size

        return Response({
            "count": self.page.paginator.count if self.page else len(data),
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "total_pages": total_pages,
            "page_size": page_size,
            "results": data
        })
