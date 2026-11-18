import re
from django import forms
from django.contrib.auth import password_validation
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.db import transaction

from rides.models import UserProfile

ALLOWED_DOMAIN = "@iiitdmj.ac.in"
GENDER_CHOICES = [("M", "Male"), ("F", "Female"), ("O", "Other / prefer not to say")]
# ^ keep these keys identical to UserProfile.gender choices


class EmailLoginForm(AuthenticationForm):
    username = forms.EmailField(label="Institute email",
                                widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "21bcs001@iiitdmj.ac.in"}))

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        p = UserProfile.objects.filter(user=user).first()
        if p and p.is_suspended:
            raise forms.ValidationError("Your account has been suspended by an administrator.", code="suspended")
        if p and not p.email_verified:
            raise forms.ValidationError("Please verify your email first. Open the link we sent to your institute inbox.", code="unverified")


class RegistrationForm(forms.Form):
    first_name = forms.CharField(max_length=60, label="Your name")
    email = forms.EmailField(label="Institute email")
    roll_number = forms.CharField(max_length=20, label="Roll number")
    department = forms.CharField(max_length=80, required=False, label="Department (optional)")
    gender = forms.ChoiceField(choices=GENDER_CHOICES)
    phone_number = forms.CharField(max_length=10, label="WhatsApp number",
                                   help_text="10 digits. Only shared with riders you are matched with.")
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if not email.endswith(ALLOWED_DOMAIN):
            raise forms.ValidationError(f"Use your institute email ending in {ALLOWED_DOMAIN}.")
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("An account with this email already exists. Log in instead.")
        return email

    def clean_roll_number(self):
        roll = self.cleaned_data["roll_number"].strip().upper()
        if UserProfile.objects.filter(roll_number=roll).exists():
            raise forms.ValidationError("This roll number is already registered.")
        return roll

    def clean_phone_number(self):
        phone = re.sub(r"\D", "", self.cleaned_data["phone_number"])[-10:]
        if not re.fullmatch(r"[6-9]\d{9}", phone):
            raise forms.ValidationError("Enter a valid 10-digit Indian mobile number.")
        return phone

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "Passwords do not match.")
            else:
                try:
                    password_validation.validate_password(p1)
                except forms.ValidationError as e:
                    self.add_error("password1", e)
        return data

    @transaction.atomic
    def save(self):
        d = self.cleaned_data
        user = User.objects.create_user(username=d["email"], email=d["email"],
                                        password=d["password1"], first_name=d["first_name"].strip())
        UserProfile.objects.create(user=user, roll_number=d["roll_number"],
                                   phone_number=d["phone_number"], gender=d["gender"],
                                   department=d.get("department", "").strip(),
                                   email_verified=not settings.EMAIL_VERIFICATION_REQUIRED)
        return user
