from rest_framework import status as drf_status
from rest_framework.response import Response


class ApiResponseMixin:
    def success_response(self, data, status=drf_status.HTTP_200_OK, headers=None, meta=None):
        """
        Standard success envelope used across the project.
        Returns:
            {
              "data": <payload>,
              "meta": {"success": true, ...}
            }
        """
        meta_payload = {"success": True}
        if meta:
            meta_payload.update(meta)

        resp = Response({"data": data, "meta": meta_payload}, status=status)
        if headers:
            for k, v in headers.items():
                resp[k] = v
        return resp

    def list(self, request, *args, **kwargs):
        """
        Override DRF's ListModelMixin.list to always wrap paginated responses
        inside the standard success envelope, with a nested payload containing
        {count, next, previous, results}.
        This allows any ListAPIView that mixes in ApiResponseMixin to get the
        unified response shape without per-view changes.
        """
        # Apply filters the same way DRF does
        queryset = self.filter_queryset(self.get_queryset())

        # Attempt pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            # Build the paginated payload
            count = getattr(self.paginator.page.paginator, "count", None)
            next_link = self.paginator.get_next_link()
            prev_link = self.paginator.get_previous_link()
            page_number = getattr(getattr(self.paginator, "page", None), "number", None)
            page_size = None
            if hasattr(self.paginator, "get_page_size"):
                try:
                    page_size = self.paginator.get_page_size(request)
                except Exception:
                    page_size = None

            payload = {
                "count": count,
                "next": next_link,
                "previous": prev_link,
                "results": serializer.data,
            }
            return self.success_response(payload, meta={"page": page_number, "page_size": page_size})

        # If pagination is disabled, still provide a consistent structure
        serializer = self.get_serializer(queryset, many=True)
        payload = {
            "count": len(serializer.data) if hasattr(serializer.data, "__len__") else None,
            "next": None,
            "previous": None,
            "results": serializer.data,
        }
        return self.success_response(payload)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)

        if 200 <= response.status_code < 300:
            data = getattr(response, "data", None)

            if isinstance(data, dict) and "data" in data and "meta" in data:
                return response

            if isinstance(data, (dict, list)):
                response.data = {
                    "data": data,
                    "meta": {"success": True},
                }
                response._is_rendered = False

        return response
