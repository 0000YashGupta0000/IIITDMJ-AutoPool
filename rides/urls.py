from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("find/", views.ride_feed, name="ride_feed"),
    path("post/", views.create_ride, name="create_ride"),
    path("my-rides/", views.my_rides, name="my_rides"),
    path("rides/<int:ride_id>/join/", views.request_join, name="request_join"),
    path("rides/<int:ride_id>/delay/", views.delay_ride, name="delay_ride"),
    path("rides/<int:ride_id>/cancel/", views.cancel_ride, name="cancel_ride"),
    path("rides/<int:ride_id>/complete/", views.complete_ride, name="complete_ride"),
    path("rides/<int:ride_id>/leave/", views.leave_ride, name="leave_ride"),
    path("requests/<int:request_id>/handle/", views.handle_request, name="handle_request"),
    path("requests/<int:request_id>/cancel/", views.cancel_request, name="cancel_request"),
    path("report/<int:user_id>/", views.report_user, name="report_user"),
]
