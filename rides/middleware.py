from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect

from .models import UserProfile


class SuspendedUserMiddleware:
    """Logs out any student an admin has suspended."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.path.startswith("/admin"):
            if UserProfile.objects.filter(user=request.user, is_suspended=True).exists():
                logout(request)
                messages.error(request, "Your account has been suspended by an administrator.")
                return redirect("login")
        return self.get_response(request)
