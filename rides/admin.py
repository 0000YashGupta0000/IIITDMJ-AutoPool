from django.contrib import admin

from .models import Notification, Report, Ride, RideRequest, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("roll_number", "user", "gender", "department", "is_suspended", "email_verified")
    list_filter = ("is_suspended", "email_verified", "gender")
    search_fields = ("roll_number", "user__email", "user__first_name")
    actions = ["suspend", "unsuspend"]

    @admin.action(description="Suspend selected students")
    def suspend(self, request, qs):
        qs.update(is_suspended=True)

    @admin.action(description="Un-suspend selected students")
    def unsuspend(self, request, qs):
        qs.update(is_suspended=False)


@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    list_display = ("id", "creator", "direction", "location", "travel_date", "travel_time", "seats_available", "status")
    list_filter = ("status", "direction", "female_only")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "reporter", "reported_user", "reason", "status", "created_at")
    list_filter = ("status", "reason")
    actions = ["investigate", "resolve", "dismiss"]

    @admin.action(description="Mark as investigating")
    def investigate(self, request, qs):
        qs.update(status=Report.INVESTIGATING)

    @admin.action(description="Mark as resolved")
    def resolve(self, request, qs):
        qs.update(status=Report.RESOLVED)

    @admin.action(description="Dismiss")
    def dismiss(self, request, qs):
        qs.update(status=Report.DISMISSED)


admin.site.register(RideRequest)
admin.site.register(Notification)
