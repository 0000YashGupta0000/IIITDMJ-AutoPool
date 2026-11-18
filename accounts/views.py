from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.core import signing
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from rides.models import UserProfile
from .forms import RegistrationForm

SALT = "autopool-email-verify"


def _send_verification(request, user):
    token = signing.dumps(user.pk, salt=SALT)
    link = request.build_absolute_uri(reverse("verify_email", args=[token]))
    send_mail("Verify your IIITDMJ Auto Pool account",
              f"Hi {user.first_name},\n\nOpen this link to verify your email (valid for 24 hours):\n{link}\n",
              settings.DEFAULT_FROM_EMAIL, [user.email])
    return link


def register(request):
    if request.user.is_authenticated:
        return redirect("ride_feed")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        if settings.EMAIL_VERIFICATION_REQUIRED:
            link = _send_verification(request, user)
            request.session["pending_email"] = user.email
            request.session["dev_link"] = link if settings.DEBUG else ""
            return redirect("check_email")
        login(request, user)
        messages.success(request, "You're in. Find an auto or post your own.")
        return redirect("ride_feed")
    return render(request, "registration/register.html", {"form": form})


def check_email(request):
    return render(request, "registration/check_email.html", {
        "email": request.session.get("pending_email", ""),
        "dev_link": request.session.get("dev_link", ""),
    })


@require_POST
def resend_verification(request):
    email = (request.POST.get("email") or "").strip().lower()
    user = User.objects.filter(username=email).first()
    p = UserProfile.objects.filter(user=user).first() if user else None
    if p and not p.email_verified:
        request.session["dev_link"] = _send_verification(request, user) if settings.DEBUG else ""
    request.session["pending_email"] = email
    messages.info(request, "If that account needs verification, a new link has been sent.")
    return redirect("check_email")


def verify_email(request, token):
    try:
        pk = signing.loads(token, salt=SALT, max_age=60 * 60 * 24)
    except signing.BadSignature:
        messages.error(request, "That verification link is invalid or expired. Request a new one.")
        return redirect("check_email")
    UserProfile.objects.filter(user_id=pk).update(email_verified=True)
    messages.success(request, "Email verified. You can log in now.")
    return redirect("login")
