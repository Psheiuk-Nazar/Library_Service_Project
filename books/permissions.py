from django.views import View
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request: Request, view: View) -> bool:
        return bool(request.method in SAFE_METHODS or request.user.is_staff)
