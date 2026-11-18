from django.conf import settings


def globals(request):
    ctx = {"UI_THEME": settings.UI_THEME}
    if request.user.is_authenticated:
        from .models import Notification
        ctx["unread_count"] = Notification.objects.filter(user=request.user, read=False).count()
    return ctx
