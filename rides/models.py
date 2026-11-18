import math
from datetime import datetime

from django.contrib.auth.models import User
from django.db import models

TOTAL_SEATS = 3  # standard auto-rickshaw


class UserProfile(models.Model):
    GENDER_CHOICES = [("M", "Male"), ("F", "Female"), ("O", "Other / prefer not to say")]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    roll_number = models.CharField(max_length=20, unique=True)
    phone_number = models.CharField(max_length=10)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    department = models.CharField(max_length=80, blank=True, default="")
    is_suspended = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.roll_number} ({self.user.first_name})"


class Ride(models.Model):
    INBOUND, OUTBOUND = "INBOUND", "OUTBOUND"
    DIRECTION_CHOICES = [(INBOUND, "To campus"), (OUTBOUND, "From campus")]
    OPEN, FULL, COMPLETED, CANCELLED, EXPIRED = "OPEN", "FULL", "COMPLETED", "CANCELLED", "EXPIRED"
    STATUS_CHOICES = [(OPEN, "Open"), (FULL, "Full"), (COMPLETED, "Completed"),
                      (CANCELLED, "Cancelled"), (EXPIRED, "Expired")]

    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="rides_created")
    direction = models.CharField(max_length=8, choices=DIRECTION_CHOICES)
    location = models.CharField(max_length=60)
    pickup_point = models.CharField(max_length=60, blank=True, default="")
    travel_date = models.DateField()
    travel_time = models.TimeField()
    seats_available = models.PositiveSmallIntegerField(default=2)
    has_luggage_space = models.BooleanField(default=False)
    female_only = models.BooleanField(default=False)
    estimated_total_fare = models.PositiveIntegerField()
    notes = models.TextField(blank=True, default="", max_length=200)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["travel_date", "travel_time"]

    @property
    def ride_no(self):
        return 100 + self.pk          # friendly "Ride #101" style number

    @property
    def is_active(self):
        return self.status in (self.OPEN, self.FULL)

    @property
    def departure(self):
        return datetime.combine(self.travel_date, self.travel_time)  # naive, campus-local time

    @property
    def confirmed_riders(self):
        return TOTAL_SEATS - self.seats_available  # creator + accepted

    @property
    def fare_now(self):
        return math.ceil(self.estimated_total_fare / max(self.confirmed_riders, 1))

    @property
    def fare_full(self):
        return math.ceil(self.estimated_total_fare / TOTAL_SEATS)

    def __str__(self):
        return f"#{self.ride_no} {self.get_direction_display()} {self.location} {self.travel_date} {self.travel_time:%H:%M}"


class RideRequest(models.Model):
    PENDING, ACCEPTED, REJECTED, CANCELLED = "PENDING", "ACCEPTED", "REJECTED", "CANCELLED"
    STATUS_CHOICES = [(PENDING, "Pending"), (ACCEPTED, "Accepted"), (REJECTED, "Rejected"), (CANCELLED, "Cancelled")]

    ride = models.ForeignKey(Ride, on_delete=models.CASCADE)   # reverse name: riderequest_set
    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ride_requests")
    status = models.CharField(max_length=9, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["ride", "requester"], name="one_request_per_ride")]

    def __str__(self):
        return f"{self.requester} -> {self.ride} [{self.status}]"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=240)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Report(models.Model):
    PENDING, INVESTIGATING, RESOLVED, DISMISSED = "PENDING", "INVESTIGATING", "RESOLVED", "DISMISSED"
    STATUS_CHOICES = [(PENDING, "Pending"), (INVESTIGATING, "Investigating"), (RESOLVED, "Resolved"), (DISMISSED, "Dismissed")]
    REASONS = [("NO_SHOW", "Did not show up"), ("UNSAFE", "Unsafe behaviour"), ("HARASSMENT", "Harassment"),
               ("FARE", "Fare dispute"), ("OTHER", "Other")]

    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reports_made")
    reported_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reports_received")
    ride = models.ForeignKey(Ride, on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.CharField(max_length=12, choices=REASONS)
    description = models.TextField(blank=True, max_length=500)
    status = models.CharField(max_length=14, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
