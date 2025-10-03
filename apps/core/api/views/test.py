from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api.permissions import RoleBasedPermission
from apps.core.utils import register_permission


class TestView(APIView):
    permission_classes = [RoleBasedPermission]

    @register_permission("test.get", "Test get")
    def get(self, request):
        return Response({"message": "Get"})

    @register_permission("test.post", "Test post")
    def post(self, request):
        return Response({"message": "Created"})
